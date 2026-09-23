# Tarefa: implementar o backend do bot de atendimento WhatsApp (Evolution API)

## Contexto

Projeto: `C:/Users/Bruno/Desktop/programacao/Projetos/whatsapp-bot/`. Já existe `docker/docker-compose.yml` (Evolution API v2.3.7 em http://localhost:8080 + Postgres + Redis) e `docker/.env` com `AUTHENTICATION_API_KEY`. O container expõe `host.docker.internal` para alcançar serviços do host.

Objetivo: demo de portfólio de atendimento automatizado no WhatsApp, reaproveitando as regras do projeto `auto_whatsapp` (academia fictícia "Studio Fit": horário, planos, endereço, fallback → humano). Deve ser genérico o bastante para trocar as regras por cliente via arquivo de config.

## Entregar em `bot/`

Python 3.11, FastAPI + uvicorn, httpx, pydantic, python-dotenv, pyyaml, sqlite3 (stdlib). Gerenciar com `uv` (criar `pyproject.toml`; `uv sync`).

Arquivos:

1. `bot/config/studio_fit.yaml` — regras do negócio: nome, mensagem de boas-vindas, lista de intenções com `keywords` e `reply` (portar as 3 regras + fallback do `C:/Users/Bruno/Desktop/programacao/Projetos/auto_whatsapp/script.js`), número do atendente humano para handoff (placeholder `HANDOFF_NUMBER` lido do `.env`), horário de atendimento humano, `llm.enabled: false` por padrão.
2. `bot/app/main.py` — FastAPI:
   - `POST /webhook` — recebe eventos da Evolution API (`messages.upsert`). Ignorar mensagens `fromMe`, grupos (`@g.us`), status e mensagens sem texto (`conversation` ou `extendedTextMessage.text`). Extrair `remoteJid`, texto, `pushName`.
   - `GET /health`.
   - `GET /conversations` — últimas conversas e estado (para demo).
3. `bot/app/engine.py` — máquina de estados por contato: `menu`, `aguardando_humano`, `humano_ativo`. Fluxo: primeira mensagem → boas-vindas + menu numerado (1 Horário / 2 Planos / 3 Endereço / 4 Falar com atendente). Aceitar número OU palavra-chave (normalizar acentos/caixa). Opção 4 ou fallback duas vezes seguidas → estado `aguardando_humano`, responder ao cliente e notificar `HANDOFF_NUMBER` com nome, número e últimas 5 mensagens. Comando do atendente `#assumir <numero>` / `#liberar <numero>` alterna `humano_ativo`; em `humano_ativo` o bot não responde. Comando `#menu` do cliente volta ao menu. Timeout: 30 min sem mensagem volta a `menu`.
4. `bot/app/evolution.py` — cliente httpx da Evolution API: `send_text(instance, number, text)` (`POST /message/sendText/{instance}` com header `apikey`), `set_presence_typing` opcional, `create_instance`, `get_qr`, `set_webhook(instance, url, events=["MESSAGES_UPSERT"])`. Ler `EVOLUTION_URL`, `EVOLUTION_API_KEY`, `EVOLUTION_INSTANCE` do `.env`. Consultar a doc v2 em https://doc.evolution-api.com/v2 se precisar confirmar payloads.
5. `bot/app/store.py` — SQLite em `bot/data/bot.db`: tabelas `contacts(jid, name, state, updated_at)` e `messages(id, jid, direction, text, ts)`.
6. `bot/app/llm.py` — opcional: se `llm.enabled` e `OPENROUTER_API_KEY` existirem, responder perguntas fora do script com um modelo barato usando o YAML como contexto; senão, fallback padrão. Não obrigatório para a demo, mas deixar plugado.
7. `bot/scripts/setup_instance.py` — cria a instância na Evolution (`POST /instance/create` com `integration: "WHATSAPP-BAILEYS"`, `qrcode: true`), registra o webhook apontando para `http://host.docker.internal:8000/webhook` com `webhook_by_events: false`, `events: ["MESSAGES_UPSERT"]`, e salva o QR code em `bot/data/qr.png` (o base64 vem na resposta) e também imprime o link `http://localhost:8080/instance/connect/{instance}`.
8. `bot/.env.example` e `bot/README.md` — como subir (docker compose up -d; uv sync; uv run python scripts/setup_instance.py; escanear QR; uv run uvicorn app.main:app --port 8000), como trocar regras por cliente, limitações (Baileys não é API oficial; para produção migrar para Meta Cloud API).
9. `bot/tests/test_engine.py` — pytest para a máquina de estados (menu, keywords, handoff, comandos #assumir/#liberar/#menu) sem rede. Rodar e deixar passando.

## Restrições

- Não commitar segredos; `.env` já está no `.gitignore`.
- Código em português nos textos ao usuário; nomes de código em inglês.
- Não modificar nada fora de `whatsapp-bot/`.
- Ao terminar, rodar `uv run pytest -q` e `uv run python -c "import app.main"` e reportar resultado.
