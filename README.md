# Glam Telefonista IA (Flask + Twilio + OpenAI)

Telefonista por voz que liga para clientes, segue um roteiro inteligente e usa OpenAI para humanizar a conversa e fazer comentários curtos por cidade.

## Como funciona
- Frontend simples (`/`) com campo de telefone e botão **Ligar**.
- Backend inicia a chamada pela Twilio (`/call`).
- A Twilio busca o diálogo em `/voice` usando TwiML com `Gather input="speech"` (pt-BR).
- A conversa segue o fluxo:
  1) Apresentação → 2) "Você já é extensionista?"
  - Se **sim**: pergunta cidade → comenta algo curto sobre a cidade (OpenAI) → pede permissão de WhatsApp → encerra.
  - Se **não**: pergunta interesse em aprender → se sim, pede WhatsApp → encerra; se não, agradece e encerra.
- Estados ficam em memória por `CallSid` (simples, sem banco).

## Variáveis de Ambiente (Render)
- `OPENAI_API_KEY` (required)
- `OPENAI_MODEL` (default: `gpt-4o-mini`)
- `TWILIO_ACCOUNT_SID` (required)
- `TWILIO_AUTH_TOKEN` (required)
- `TWILIO_FROM_NUMBER` (required, ex: `+17752615122`)

## Rodando localmente
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY=...
export TWILIO_ACCOUNT_SID=...
export TWILIO_AUTH_TOKEN=...
export TWILIO_FROM_NUMBER=+1...
flask --app app run
```
Abra http://localhost:5000 e dispare a ligação.

## Observações
- Se sua conta Twilio estiver em **trial**, o número de destino precisa estar **verificado** no console.
- O uso de OpenAI é apenas para gerar a frase curtinha da cidade; todo o resto é controlado pelo fluxo.
- Para produção, considere persistir os leads (ex.: Postgres, Sheet, CRM) na parte marcada `[LEAD]` no `app.py`.
