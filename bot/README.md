# Bot de atendimento WhatsApp (Evolution API + Meta Cloud API)

Demo de portfólio: atendimento automatizado no WhatsApp para uma academia
fictícia ("Studio Fit"), com menu, respostas por palavra-chave e handoff para
atendente humano. Backend em FastAPI. Funciona tanto via [Evolution API](https://doc.evolution-api.com/v2)
(engine Baileys) quanto via **Meta WhatsApp Cloud API** oficial — ver seção
"Canal Meta Cloud API" abaixo.

## Subir o ambiente

1. Suba Evolution API + Postgres + Redis:

   ```bash
   cd docker
   docker compose up -d
   ```

2. Instale as dependências do bot:

   ```bash
   cd bot
   uv sync
   cp .env.example .env
   # edite .env: EVOLUTION_API_KEY (mesma AUTHENTICATION_API_KEY do docker/.env),
   # EVOLUTION_INSTANCE, HANDOFF_NUMBER
   ```

3. Suba a API do bot (precisa estar de pé antes de registrar o webhook):

   ```bash
   uv run uvicorn app.main:app --port 8000
   ```

4. Em outro terminal, crie a instância na Evolution, registre o webhook e
   gere o QR code:

   ```bash
   uv run python scripts/setup_instance.py
   ```

   O QR code é salvo em `bot/data/qr.png` e também pode ser aberto em
   `http://localhost:8080/instance/connect/{EVOLUTION_INSTANCE}`.

5. Escaneie o QR code no WhatsApp (Aparelhos conectados). Pronto: mensagens
   recebidas no número conectado passam a ser respondidas pelo bot.

## Endpoints

- `POST /webhook` — recebido pela Evolution API (evento `messages.upsert`).
- `GET /webhook/meta` — verificação do webhook pela Meta.
- `POST /webhook/meta` — recebido pela Meta WhatsApp Cloud API.
- `GET /health` — checagem simples.
- `GET /conversations` — últimas conversas e estado, para acompanhar a demo.

## Canal Meta Cloud API

Além da Evolution API (Baileys), o bot também fala direto com a **Meta
WhatsApp Cloud API** (Graph API oficial), sem Evolution no meio. A máquina de
estados (`app/engine.py`) é a mesma para os dois canais.

### Escolher o canal

No `.env`, defina `CHANNEL=evolution` (padrão) ou `CHANNEL=meta`.

### Variáveis (`CHANNEL=meta`)

- `META_ACCESS_TOKEN` — token de acesso (para testes, o token temporário do
  painel; para demo mais estável, gere um token permanente de um
  [system user](https://developers.facebook.com/docs/whatsapp/business-management-api/get-started)).
- `META_PHONE_NUMBER_ID` — em Meta for Developers → seu app → WhatsApp →
  API Setup → "Phone number ID" (número de teste grátis já vem provisionado).
- `META_VERIFY_TOKEN` — string qualquer inventada por você; usada só para a
  Meta confirmar que o webhook é seu.
- `META_APP_SECRET` — opcional; em App Settings → Basic → "App secret". Se
  preenchido, o bot valida a assinatura `X-Hub-Signature-256` de cada webhook.
- `META_GRAPH_VERSION` — versão da Graph API (padrão `v23.0`).

O WABA ID (WhatsApp Business Account) aparece na mesma tela de API Setup;
não é necessário no `.env` para enviar/receber mensagens de texto.

### Túnel HTTPS para desenvolvimento

A Meta exige um webhook HTTPS público. Para expor o bot local:

```bash
# Windows
scripts/tunnel.ps1

# Linux/macOS
scripts/tunnel.sh
```

Sobe um `cloudflared tunnel --url http://localhost:8000` (quick tunnel, sem
precisar de conta Cloudflare) e imprime a URL pública (`https://algo.trycloudflare.com`).
Se `cloudflared` não estiver instalado: `winget install Cloudflare.cloudflared`.

### Configurar o webhook no painel Meta

Em Meta for Developers → seu app → WhatsApp → Configuration → Webhook:

1. Callback URL: `https://<url-do-tunel>/webhook/meta`.
2. Verify token: o mesmo valor de `META_VERIFY_TOKEN` no `.env`.
3. Clique "Verify and save".
4. Em "Webhook fields", assine (subscribe) o campo `messages`.

### Limitações do número de teste

- O número de teste grátis da Meta só envia/recebe de até **5 números
  destinatários** cadastrados na mesma tela de API Setup.
- **Janela de 24h**: o bot só pode responder livremente dentro de 24h desde a
  última mensagem do cliente; fora dela, só mensagens de template aprovadas
  pela Meta. Como nesta demo o cliente sempre inicia a conversa, a janela
  está sempre aberta na hora da resposta.

## Trocar as regras por cliente

As regras de negócio ficam em `config/studio_fit.yaml` (mensagens, menu,
intenções com `keywords`/`reply`, número de handoff, horário de atendimento
humano). Para outro cliente:

1. Copie o arquivo (`cp config/studio_fit.yaml config/outro_cliente.yaml`) e
   ajuste os campos.
2. Aponte `BUSINESS_CONFIG=config/outro_cliente.yaml` no `.env`.
3. Reinicie a API.

## Comandos do atendente

Enviando mensagens do número configurado em `HANDOFF_NUMBER` para o número do
bot:

- `#assumir <numero>` — assume a conversa com `<numero>`; o bot para de
  responder a esse contato.
- `#liberar <numero>` — devolve a conversa para o bot (volta ao menu).

O cliente pode digitar `#menu` a qualquer momento para voltar ao menu inicial.

## Testes

```bash
uv run pytest -q
```

## Limitações

- **Baileys não é a API oficial do WhatsApp** (WhatsApp Web via engenharia
  reversa). Sujeita a instabilidade, banimento de número e mudanças sem
  aviso da Meta. Adequado para demo/portfólio, não para produção crítica.
- Para produção, migrar para a **Meta Cloud API** oficial (a Evolution API
  também suporta essa integração, trocando `integration` na criação da
  instância).
- LLM de fallback (`app/llm.py`) é opcional e desligado por padrão
  (`llm.enabled: false` no YAML); requer `OPENROUTER_API_KEY` no `.env`.
- Estado de conversa é local (SQLite); não há fila/retry para envios que
  falharem na Evolution API.
