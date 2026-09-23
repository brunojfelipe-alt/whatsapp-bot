# Tarefa 2: adapter Meta WhatsApp Cloud API + abstração de canal

## Contexto

Projeto `C:/Users/Bruno/Desktop/programacao/Projetos/whatsapp-bot/bot/` (FastAPI, uv, Python 3.12). Já funciona com Evolution API (Baileys): `app/main.py` (webhook `/webhook`), `app/engine.py` (máquina de estados, agnóstica de canal — usa `jid` string), `app/evolution.py` (cliente), `app/store.py`, `app/config.py`, `config/studio_fit.yaml`, `tests/test_engine.py` (12 testes passando). Leia esses arquivos antes de começar.

Objetivo: o mesmo bot funcionar também pela **Meta WhatsApp Cloud API oficial** (Graph API), sem Evolution no meio. O canal é escolhido por `.env` (`CHANNEL=evolution|meta`). A máquina de estados não muda.

## Entregar

### 1. `app/channels/base.py`
```python
class Channel(Protocol):
    async def send_text(self, to: str, text: str) -> dict: ...
```
`to` é o identificador do contato no formato do canal (Evolution: `5511...@s.whatsapp.net`; Meta: `5511...` só dígitos). O engine já trata ambos via `jid_digits()`.

### 2. `app/channels/evolution.py`
Mover `EvolutionClient` para cá (manter `app/evolution.py` como reexport para não quebrar `scripts/setup_instance.py`). Implementa `Channel`.

### 3. `app/channels/meta.py` — `MetaCloudChannel`
- Env: `META_ACCESS_TOKEN`, `META_PHONE_NUMBER_ID`, `META_VERIFY_TOKEN` (string que nós inventamos), `META_APP_SECRET` (opcional; se presente, validar assinatura), `META_GRAPH_VERSION` (default `v23.0`).
- `send_text(to, text)`: `POST https://graph.facebook.com/{ver}/{phone_number_id}/messages` com header `Authorization: Bearer {token}` e body `{"messaging_product":"whatsapp","recipient_type":"individual","to":to,"type":"text","text":{"preview_url":false,"body":text}}`. Timeout 10s. Erros logados, não propagam (mesmo padrão do `EvolutionClient.send_text`).
- `mark_read(message_id)`: `POST .../messages` com `{"messaging_product":"whatsapp","status":"read","message_id":id}` — chamar ao receber, best-effort.
- `verify_signature(raw_body: bytes, header: str) -> bool`: `X-Hub-Signature-256` = `sha256=` + HMAC-SHA256(app_secret, raw_body). Usar `hmac.compare_digest`. Se `META_APP_SECRET` vazio, retornar True.
- `parse_webhook(payload: dict) -> list[dict]`: percorre `entry[].changes[].value`; para cada `messages[]` com `type == "text"`, retorna `{"jid": msg["from"], "text": msg["text"]["body"], "name": contacts[0].profile.name (se houver), "message_id": msg["id"]}`. Ignorar `statuses`, tipos não-texto (por ora), e mensagens sem `from`.

### 4. `app/main.py`
- Selecionar canal por `CHANNEL` env (default `evolution`); instanciar um `channel: Channel` e usar em vez de `evolution` direto.
- Novas rotas:
  - `GET /webhook/meta`: verificação da Meta — se `hub.mode == "subscribe"` e `hub.verify_token == META_VERIFY_TOKEN`, responder `hub.challenge` como **texto puro** (PlainTextResponse, status 200); senão 403.
  - `POST /webhook/meta`: ler `await request.body()` (bytes) para validar assinatura ANTES de parsear JSON; 403 se inválida. Depois `parse_webhook`, `engine.handle_message` para cada mensagem, enviar respostas pelo canal, `mark_read`. Sempre responder 200 rápido (Meta reenvia se não receber 200).
- Manter `/webhook` (Evolution), `/health`, `/conversations`. Extrair a lógica comum "resultado do engine → envios" para uma função `dispatch_result(result, jid, name)` usada pelos dois webhooks (o handoff notify hoje está inline no `/webhook`; unificar).
- Handoff no canal Meta: `HANDOFF_NUMBER` já é só dígitos; enviar direto.

### 5. Túnel HTTPS para desenvolvimento
`scripts/tunnel.ps1` e `scripts/tunnel.sh`: sobem `cloudflared tunnel --url http://localhost:8000` (quick tunnel, sem conta) e imprimem a URL pública. Se `cloudflared` não estiver instalado, imprimir instrução: `winget install Cloudflare.cloudflared`. README explica: colar `https://<url>/webhook/meta` no painel Meta (WhatsApp → Configuration → Webhook), verify token = `META_VERIFY_TOKEN`, assinar o campo `messages`.

### 6. Testes — `tests/test_meta_channel.py`
Sem rede (mock `httpx.AsyncClient` ou usar `respx`/`pytest-httpx` se preferir; adicionar ao grupo dev):
- `parse_webhook` com payload real de exemplo da Meta (texto) → 1 mensagem com jid/text/name/message_id.
- `parse_webhook` com payload de `statuses` → lista vazia.
- `verify_signature` válida/inválida/sem secret.
- `GET /webhook/meta` retorna challenge com token certo; 403 com token errado (TestClient do FastAPI, `CHANNEL=meta` via env no teste).
- `POST /webhook/meta` com assinatura válida processa e chama `send_text` (mockado); com assinatura inválida → 403.
Manter os 12 testes existentes passando.

### 7. `.env.example` e `README.md`
Adicionar seção "Canal Meta Cloud API": variáveis, como obter Phone Number ID / WABA ID / token permanente (system user) no painel Meta, túnel, webhook, limitação do número de teste (5 destinatários), janela de 24h (respostas livres só dentro dela; fora, só templates — a demo sempre é iniciada pelo cliente, então ok).

## Restrições
- Não commitar segredos. Não modificar nada fora de `bot/`.
- Textos ao usuário em português; código em inglês.
- Ao terminar: `uv sync`, `uv run pytest -q`, `uv run python -c "import app.main"`, e reportar.
