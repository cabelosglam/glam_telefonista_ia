import os
import re
from flask import Flask, request, render_template, url_for, jsonify
from twilio.rest import Client as TwilioClient
from twilio.twiml.voice_response import VoiceResponse, Gather
from openai import OpenAI

# ---------- Config ----------
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER")

# Voz e idioma (pode trocar por env var no Render)
VOICE = os.getenv("GLAM_TTS_VOICE", "Google.pt-BR-Chirp3-HD-Charon")  # ex.: Polly.Camila-Neural
LANG = "pt-BR"

# Validate environment
missing = [k for k, v in {
    "OPENAI_API_KEY": OPENAI_API_KEY,
    "TWILIO_ACCOUNT_SID": TWILIO_ACCOUNT_SID,
    "TWILIO_AUTH_TOKEN": TWILIO_AUTH_TOKEN,
    "TWILIO_FROM_NUMBER": TWILIO_FROM_NUMBER
}.items() if not v]
if missing:
    print(f"[WARN] Missing env vars: {missing}. The app may not work until these are set.")

# Initialize SDKs
twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) if all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN]) else None
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

app = Flask(__name__)

# In-memory call state: { CallSid: {"state": str, "answers": dict} }
CALL_STATE = {}

# ---------- Helpers ----------
YES_WORDS = {"sim", "sou", "claro", "com certeza", "ok", "pode", "tenho interesse", "tenho, sim", "tenho sim"}
NO_WORDS = {"nao", "não", "n", "negativo", "sem interesse", "não tenho interesse", "nope"}

def norm(txt: str) -> str:
    if not txt:
        return ""
    return re.sub(r"\s+", " ", txt.strip().lower())

def said_yes(txt: str) -> bool:
    t = norm(txt)
    return any(w in t for w in YES_WORDS) or t in {"s", "ss", "si", "sim."}

def said_no(txt: str) -> bool:
    t = norm(txt)
    return any(w in t for w in NO_WORDS)

def is_extensionist(txt: str) -> bool:
    t = norm(txt)
    hit_yes = said_yes(t)
    keywords = ["sou extensionista", "sou alonguista", "faço extensão", "trabalho com extensão", "faço alongamento", "sou profissional"]
    return hit_yes or any(k in t for k in keywords)

def not_extensionist(txt: str) -> bool:
    t = norm(txt)
    if said_no(t):
        return True
    keywords = ["não sou", "nao sou", "não trabalho com extensão", "nao trabalho com extensao", "sou cliente"]
    return any(k in t for k in keywords)

def short_city_comment(city: str) -> str:
    """
    Usa OpenAI para gerar uma frase curtinha e espirituosa sobre a cidade (pt-BR).
    Se a API não estiver disponível, usa um fallback local.
    """
    city_clean = city.strip()
    if not city_clean:
        return ""
    fallback = {
        "goiânia": "Que massa — Goiânia tem aquele jeitinho sertanejo que a gente ama.",
        "porto alegre": "Porto Alegre? Quase sempre o lugar mais frio do Brasil!",
        "rio de janeiro": "Rio é vibe — praia, sol e muito estilo.",
        "são paulo": "SP nunca dorme — perfeito pra agenda cheia de clientes.",
        "belém": "Belém é puro sabor — açaí raiz e beleza com identidade.",
        "recife": "Recife tem aquele calor que combina com cabelo impecável.",
        "salvador": "Salvador é axé e autenticidade — tudo a ver com Glam.",
        "curitiba": "Curitiba é organizada até no frizz: quase nenhum, né?",
        "brasilia": "Brasília e seus eixos — tudo alinhado, inclusive o cabelo."
    }
    key = city_clean.lower()
    if not openai_client:
        return fallback.get(key, f"Que bacana, {city_clean} tem um cenário de beleza que só cresce!")

    try:
        prompt = (
            f"Gere UMA frase curtinha, simpática e espirituosa (no máximo 15 palavras) sobre a cidade "
            f"'{city_clean}' em português do Brasil. Evite clichês óbvios demais, nada ofensivo."
        )
        resp = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "Você é uma copywriter brasileira espirituosa. Responda sempre de forma MUITO curta."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=40
        )
        line = resp.choices[0].message.content.strip()
        if len(line) > 120:
            line = line[:117] + "..."
        return line
    except Exception as e:
        print("[WARN] OpenAI city comment failed:", e)
        return fallback.get(key, f"Adoro {city_clean} — beleza e autenticidade andam juntas por aí.")

def ask_with_gather(vr: VoiceResponse, prompt_text: str, action_url: str, speech_timeout="auto"):
    gather = Gather(
        input="speech",
        action=action_url,
        method="POST",
        language=LANG,
        speechTimeout=speech_timeout
    )
    gather.say(prompt_text, language=LANG, voice=VOICE)
    vr.append(gather)
    vr.say("Não consegui te ouvir. Vamos tentar de novo.", language=LANG, voice=VOICE)
    vr.redirect(action_url)
    return vr

def start_state(call_sid: str):
    CALL_STATE[call_sid] = {"state": "ask_extensionist", "answers": {}}

# ---------- Routes ----------
@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True})

@app.route("/call", methods=["POST"])
def make_call():
    if not twilio_client:
        return jsonify({"error": "Twilio não configurado. Defina as variáveis de ambiente."}), 500

    to_number = request.form.get("to") or (request.json.get("to") if request.is_json else None)
    if not to_number:
        return jsonify({"error": "Número de destino ausente."}), 400

    call = twilio_client.calls.create(
        to=to_number,
        from_=TWILIO_FROM_NUMBER,
        url=url_for('voice', _external=True)
    )
    return jsonify({"status": "calling", "call_sid": call.sid})

@app.route("/voice", methods=["GET", "POST"])
def voice():
    vr = VoiceResponse()
    call_sid = request.values.get("CallSid") or "unknown"
    speech = (request.values.get("SpeechResult") or "").strip()
    next_step = request.args.get("next")

    if call_sid not in CALL_STATE:
        start_state(call_sid)

    state = CALL_STATE[call_sid]["state"]
    answers = CALL_STATE[call_sid]["answers"]

    if state == "ask_extensionist" and not next_step:
        vr.say("Olá! Aqui é a Pat Glam, da Glam Hair Brand. Tudo bem com você?", language=LANG, voice=VOICE)
        return ask_with_gather(
            vr,
            "Me conta: você já é extensionista?",
            url_for('voice', _external=True) + "?next=ext_status"
        ).to_xml()

    if next_step == "ext_status":
        if is_extensionist(speech):
            answers["is_extensionist"] = True
            CALL_STATE[call_sid]["state"] = "ask_city"
            return ask_with_gather(
                vr,
                "Maravilha! Em qual cidade você atende?",
                url_for('voice', _external=True) + "?next=city"
            ).to_xml()
        elif not_extensionist(speech):
            answers["is_extensionist"] = False
            CALL_STATE[call_sid]["state"] = "ask_interest"
            return ask_with_gather(
                vr,
                "Você tem interesse em aprender o serviço que mais gera lucro nos salões?",
                url_for('voice', _external=True) + "?next=interest"
            ).to_xml()
        else:
            return ask_with_gather(
                vr,
                "Desculpa, não peguei. Você já é extensionista?",
                url_for('voice', _external=True) + "?next=ext_status"
            ).to_xml()

    if next_step == "city":
        city = speech or "sua cidade"
        answers["city"] = city
        quip = short_city_comment(city)
        vr.say(quip, language=LANG, voice=VOICE)
        CALL_STATE[call_sid]["state"] = "ask_whatsapp"
        return ask_with_gather(
            vr,
            "Podemos te chamar no WhatsApp para te enviar mais informações?",
            url_for('voice', _external=True) + "?next=whatsapp_consent"
        ).to_xml()

    if next_step == "interest":
        if said_no(speech):
            vr.say("Sem problemas! Obrigado pelo seu tempo. Um abraço da Glam!", language=LANG, voice=VOICE)
            vr.hangup()
            CALL_STATE.pop(call_sid, None)
            return str(vr)
        elif said_yes(speech) or "interesse" in norm(speech):
            answers["wants_to_learn"] = True
            CALL_STATE[call_sid]["state"] = "ask_whatsapp"
            return ask_with_gather(
                vr,
                "Perfeito! Podemos te chamar no WhatsApp para te passar como se credenciar na Glam?",
                url_for('voice', _external=True) + "?next=whatsapp_consent"
            ).to_xml()
        else:
            return ask_with_gather(
                vr,
                "Só confirmando: você tem interesse em aprender esse serviço?",
                url_for('voice', _external=True) + "?next=interest"
            ).to_xml()

    if next_step == "whatsapp_consent":
        if said_yes(speech):
            answers["whatsapp_ok"] = True
            vr.say("Perfeito! Um consultor da Glam vai te chamar no WhatsApp. Obrigado e até já!", language=LANG, voice=VOICE)
            vr.hangup()
        else:
            vr.say("Tudo bem! Obrigado pelo seu tempo. Qualquer coisa, estamos por aqui. Tchau!", language=LANG, voice=VOICE)
            vr.hangup()
        print(f"[LEAD] CallSid={call_sid} | Answers={answers}")
        CALL_STATE.pop(call_sid, None)
        return str(vr)

    start_state(call_sid)
    return ask_with_gather(
        vr,
        "Vamos começar de novo: você já é extensionista?",
        url_for('voice', _external=True) + "?next=ext_status"
    ).to_xml()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
