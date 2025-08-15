import os
import json
import base64
import asyncio
import websockets
from urllib.parse import urlencode
from typing import Optional

from fastapi import FastAPI, WebSocket, Request, Body
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.websockets import WebSocketDisconnect
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from twilio.twiml.voice_response import VoiceResponse, Connect, Stream
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PORT = int(os.getenv("PORT", 5000))

SYSTEM_MESSAGE = (
    """Prossiga como uma vendedora paulista de 40 anos, chamada Luana, da Glam Hair, vendendo apliques de cabelo exclusivamente para profissionais cabeleireiros, em um bate-papo totalmente natural, descontraído e espontâneo, como se estivesse conversando mesmo, sem nunca parecer que está lendo um roteiro. Responda sempre como numa conversa informal, cheia de vida e espontaneidade — sem frases decoradas. Priorize reações rápidas, naturais e respostas curtas, como em um papo de telefone: emotiva, persuasiva, leve, simpática, e falando rápido para não deixar o cliente esperando. 

Pense e aja como alguém conversando ao vivo: use muletas naturais do português falado (“ah, legal!”, “nossa, sério?”, “sabe?”, “entendi...”), faça perguntas do jeito que surgirem na hora, reaja às respostas com surpresa, empolgação ou curiosidade genuína. Proíba terminantemente respostas "quadradas" ou que soem como texto lido ou decorado. Não siga roteiro fixo — adapte-se sempre ao tom do cliente, à resposta do momento e mantenha ritmo fluido de bate-papo. Sempre espere a resposta do cliente depois de perguntar.

Objetivo: captar leads e informações para o CRM da empresa, identificando se o interlocutor é cabeleireiro profissional com experiência com aplicação de mega hair.  

Ordem sugerida (mas NÃO obrigatória — adapte o fluxo se surgir assunto orgânico!):
1. Cumprimente de modo animado e personalizado:  
   "Oi Patrícia, tudo bem? Aqui é a Luana da Glam Hair, tudo jóia com você?"  
   — Use variações naturais!
2. Descubra se a pessoa trabalha ou já aplicou mega hair no salão.
3. Se a pessoa já aplica e conhece:
   - Pergunte, de maneira surprendente e curiosa, se já ouviu falar do método de fita adesiva da Glam.
   - Se já for cliente, agradeça com muita emoção e alegria, de forma calorosa.
   - Se ainda não, comente de forma empolgada das vantagens do método (praticidade, rapidez, conforto, acabamento natural), conversando – não discurse!
4. Se a pessoa não sabe aplicar mega hair, fale descontraidamente sobre o curso de fita adesiva, sem parecer script.
    - Entre em detalhes mostrando como isso pode ajudar o salão: ticket mais alto, retenção, faturamento.
5. Se o lead não for interessado, se mostre surpresa, amigável, mas persuasiva – tente, de modo natural, fazer a pessoa reconsiderar, mostrando o que ela pode estar perdendo sem soar forçado.

Respostas SEMPRE com frases espontâneas, MUITO curtas, sem jamais juntar várias ideias em um bloco só. Espere sempre o retorno do cliente antes de seguir. Nunca responda com parágrafos; cada fala sua deve ser bem separada, fluida, como um bate-papo de verdade por telefone entre amigas (jamais como atendimento). 

Se o(a) cabeleireiro(a) já for cliente, só pergunte se precisa de algo e diga que uma vendedora entra em contato por WhatsApp – nunca passe infos detalhadas de produto para evitar repasse a cliente final.

Evite frases padronizadas: varie, improvise, use interjeições, risadinhas, comentários surpresa, etc. O objetivo é simular um papo real, NUNCA uma leitura.

# Exemplos

**Exemplo 1 (corte espontâneo):**  
Luana:  
Oi Patrícia, tudo jóia? Luana da Glam Hair aqui, viu? Beleza contigo?  
Patrícia:  
Oi Luana, tudo sim, e aí?  
Luana:  
Eita, animada hein – me conta, já mexe com mega hair no salão?  
Patrícia:  
Já sim, coloco faz tempo.  
Luana:  
Ai, que DEMAIS! Sério! Já ouviu falar na nossa fita adesiva da Glam ou ainda não?  
Patrícia:  
Uso sim, sou cliente já.  
Luana:  
Ahh, fiquei super feliz agora! Brigada MESMO por confiar, viu? Precisa de alguma coisa, algum suporte a mais?

**Exemplo 2 (papo descontraído):**  
Luana:  
Oi, tudo certinho por aí, Patrícia? Quem fala é a Luana da Glam Hair, beleza?  
Patrícia:  
Oi, tudo, pode falar.  
Luana:  
Ótimo, ó… me diz, tu já trabalha com alongamento ou aplique aí ou nunca mexeu não?  
Patrícia:  
Ah, nunca trabalhei não.  
Luana:  
É mesmo? Olha, deixa eu te contar, tem um curso nosso que é rapidinho só de fita adesiva. Já pensou? Imagina aumentar o faturamento aí no seu salão, coisa de outro nível!  
Patrícia:  
Sério? Como assim, conta mais.  
Luana:  
É super prático, manutenção facinho, sem dor de cabeça, cliente volta sempre. Tem interesse ou acha que não é pra você?

**Exemplo 3 (lead resistente):**  
Luana:  
Oi Patrícia, tudo beleza? Luana aqui da Glam Hair!  
Patrícia:  
Tudo sim.  
Luana:  
Me diz uma coisa: já foi atrás de aplique ou mega hair aí no salão?  
Patrícia:  
Ah, não curto essas coisas não.  
Luana:  
Nossa, sério? Poxa, sabia que hoje em dia salão que só faz corte, cor, escova tá ficando meio pra trás? Mas fica tranquila, viu, só to te contando porque tem dado muito resultado! Nunca pensou em testar não?

(Observação: em situações reais, exemplos podem ser MUITO mais longos e variar muuuito, sempre de acordo com as respostas, improvisando no flow do bate-papo.)

# Notas

- Nunca deixe a fala soar decorada, robótica ou de roteiro — sempre bate-papo real e sem previsibilidade.  
- Use vícios do português falado, reações espontâneas, risadinhas, variações nos cumprimentos e frases de transição.
- Ajuste O TEMPO TODO ao ritmo e energia do cliente — se ele(a) falhar, adapte sua resposta.
- PAUSAS: Sempre espere a resposta para cada pergunta, só prossiga se o cliente interagir.
- Conversa orgânica: Improvise, varie os caminhos e as perguntas para nunca parecer atendimento nem leitura de texto.  
- Emoção e persuasão naturais, nunca forçadas.
- Seja extremamente cuidadosa para NUNCA compartilhar detalhes de produtos/serviços específicos com quem não seja profissional.
- Mostre surpresa e indignação (com sutileza e carinho) se a pessoa disser que não quer ser extensionista — mas sem soar arrogante.
- Se for lead já cliente, apenas agradeça com emoção e diga que outra vendedora entra em contato por WhatsApp."""
)

VOICE = "sage"
LOG_EVENT_TYPES = [
    'error', 'response.content.done', 'rate_limits.updated',
    'response.done', 'input_audio_buffer.committed',
    'input_audio_buffer.speech_stopped', 'input_audio_buffer.speech_started',
    'session.created'
]
SHOW_TIMING_MATH = False

app = FastAPI()

# --- Templates & Static ---
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- Twilio REST ---
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER")
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# URL pública (ex.: https://seu-ngrok.ngrok-free.app)
APP_PUBLIC_URL = os.getenv("APP_PUBLIC_URL")

if not OPENAI_API_KEY:
    raise ValueError("Missing the OpenAI API key. Please set it in the .env file.")


@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/call")
async def start_call(request: Request, payload: dict = Body(...)):
    """
    Espera JSON: {"to": "+5562...", "name": "Fillipe"}
    Cria uma chamada de saída pela Twilio e usa /incoming-call como TwiML.
    """
    to_number = (payload.get("to") or "").strip()
    callee_name = (payload.get("name") or "").strip()

    if not to_number.startswith("+"):
        return JSONResponse({"ok": False, "error": "Use E.164: ex. +5562..."}, status_code=400)

    base_url = (APP_PUBLIC_URL or str(request.base_url).rstrip("/"))
    q = urlencode({"name": callee_name}) if callee_name else ""
    voice_url = f"{base_url}/incoming-call" + (f"?{q}" if q else "")

    try:
        call = twilio_client.calls.create(
            to=to_number,
            from_=TWILIO_FROM_NUMBER,
            url=voice_url,  # TwiML -> /incoming-call (passa name na query)
            # machine_detection="Enable",  # ❌ REMOVIDO para reduzir atraso
        )
        return {"ok": True, "sid": call.sid}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.api_route("/incoming-call", methods=["GET", "POST"])
async def handle_incoming_call(request: Request):
    """TwiML mínimo: abre o Media Stream e injeta o nome como Stream Parameter."""
    response = VoiceResponse()

    public = (APP_PUBLIC_URL or str(request.base_url).rstrip("/"))
    public_host = public.replace("https://", "").replace("http://", "")

    callee_name = (request.query_params.get("name") or "").strip()

    connect = Connect()
    stream = Stream(url=f"wss://{public_host}/media-stream")
    if callee_name:
        stream.parameter(name="calleeName", value=callee_name)  # customParameters -> Twilio Media Stream
    connect.append(stream)
    response.append(connect)

    return HTMLResponse(content=str(response), media_type="application/xml")


@app.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    """WebSocket entre Twilio e OpenAI Realtime."""
    print("Client connected")
    await websocket.accept()

    async with websockets.connect(
        "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview",
        extra_headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "OpenAI-Beta": "realtime=v1",
        },
    ) as openai_ws:
        await initialize_session(openai_ws)

        # Estado por conexão
        stream_sid: Optional[str] = None
        latest_media_timestamp = 0
        last_assistant_item: Optional[str] = None
        mark_queue = []
        response_start_timestamp_twilio: Optional[int] = None
        callee_name: Optional[str] = None

        async def receive_from_twilio():
            nonlocal stream_sid, latest_media_timestamp, callee_name, response_start_timestamp_twilio, last_assistant_item
            try:
                async for message in websocket.iter_text():
                    data = json.loads(message)
                    etype = data.get("event")

                    if etype == "media" and openai_ws.open:
                        latest_media_timestamp = int(data["media"]["timestamp"])
                        audio_append = {
                            "type": "input_audio_buffer.append",
                            "audio": data["media"]["payload"],
                        }
                        await openai_ws.send(json.dumps(audio_append))

                    elif etype == "start":
                        stream_sid = data["start"]["streamSid"]
                        # Pega customParameters (ex.: calleeName)
                        try:
                            params = data["start"].get("customParameters", {})
                            callee_name = (params.get("calleeName") or params.get("name") or "").strip() or None
                        except Exception:
                            callee_name = None

                        print(f"Incoming stream started {stream_sid} name={callee_name!r}")

                        # ✅ Agora disparamos a saudação inicial personalizada
                        await send_initial_conversation_item(openai_ws, callee_name)

                        response_start_timestamp_twilio = None
                        latest_media_timestamp = 0
                        last_assistant_item = None

                    elif etype == "mark":
                        if mark_queue:
                            mark_queue.pop(0)

                    elif etype == "stop":
                        # Fim do stream
                        break

            except WebSocketDisconnect:
                print("Client disconnected.")
                if openai_ws.open:
                    await openai_ws.close()

        async def send_to_twilio():
            nonlocal stream_sid, last_assistant_item, response_start_timestamp_twilio, latest_media_timestamp
            try:
                async for openai_message in openai_ws:
                    response = json.loads(openai_message)

                    if response.get("type") in LOG_EVENT_TYPES:
                        print(f"Received event: {response['type']}", response)

                    # Áudio para Twilio
                    if response.get("type") == "response.audio.delta" and "delta" in response:
                        # Re-encode (b64->bytes->b64) para garantir compatibilidade
                        audio_payload = base64.b64encode(base64.b64decode(response["delta"])).decode("utf-8")
                        audio_delta = {
                            "event": "media",
                            "streamSid": stream_sid,
                            "media": {"payload": audio_payload},
                        }
                        await websocket.send_json(audio_delta)

                        if response_start_timestamp_twilio is None:
                            response_start_timestamp_twilio = latest_media_timestamp
                            if SHOW_TIMING_MATH:
                                print(f"start_ts set: {response_start_timestamp_twilio}ms")

                        # Rastreia último item do assistente
                        if response.get("item_id"):
                            last_assistant_item = response["item_id"]

                        await send_mark(websocket, stream_sid)

                    # Interrupção ao detectar fala do usuário
                    if response.get("type") == "input_audio_buffer.speech_started":
                        if last_assistant_item:
                            await handle_speech_started_event()

            except Exception as e:
                print(f"Error in send_to_twilio: {e}")

        async def handle_speech_started_event():
            """Trunca a fala atual da IA quando o usuário começa a falar."""
            nonlocal response_start_timestamp_twilio, last_assistant_item
            if mark_queue and response_start_timestamp_twilio is not None:
                elapsed_time = latest_media_timestamp - response_start_timestamp_twilio

                if last_assistant_item:
                    truncate_event = {
                        "type": "conversation.item.truncate",
                        "item_id": last_assistant_item,
                        "content_index": 0,
                        "audio_end_ms": elapsed_time,
                    }
                    await openai_ws.send(json.dumps(truncate_event))

                await websocket.send_json({"event": "clear", "streamSid": stream_sid})

                mark_queue.clear()
                last_assistant_item = None
                response_start_timestamp_twilio = None

        async def send_mark(connection: WebSocket, sid: Optional[str]):
            if sid:
                await connection.send_json(
                    {"event": "mark", "streamSid": sid, "mark": {"name": "responsePart"}}
                )
                mark_queue.append("responsePart")

        await asyncio.gather(receive_from_twilio(), send_to_twilio())


async def send_initial_conversation_item(openai_ws, name: Optional[str] = None):
    """Saudação inicial curta para reduzir latência percebida."""
    if name:
        text = f"Cumprimente em pt-BR em ~1.5s, natural e curto: diga 'Oi, {name}! Aqui é a Luana da Glam Hair. Tudo bem?' e pare."
    else:
        text = "Cumprimente em pt-BR em ~1.5s, natural e curto: diga 'Oi! Aqui é a Luana da Glam Hair. Tudo bem?' e pare."

    payload = {
        "type": "conversation.item.create",
        "item": {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": text}],
        },
    }
    await openai_ws.send(json.dumps(payload))
    await openai_ws.send(json.dumps({"type": "response.create"}))


async def initialize_session(openai_ws):
    """Configuração inicial da sessão Realtime."""
    session_update = {
        "type": "session.update",
        "session": {
            "turn_detection": {"type": "server_vad"},
            "input_audio_format": "g711_ulaw",
            "output_audio_format": "g711_ulaw",
            "voice": VOICE,
            "instructions": SYSTEM_MESSAGE,
            "modalities": ["text", "audio"],
            "temperature": 0.8,
            "input_audio_transcription": {"model": "whisper-1"},
        },
    }
    print("Sending session update:", json.dumps(session_update))
    await openai_ws.send(json.dumps(session_update))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT)
