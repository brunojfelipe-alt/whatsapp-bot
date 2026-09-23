# Projeto: whatsapp-bot

Bot de atendimento WhatsApp para portfólio/demo, e base pra entregar a clientes.
Suporta dois canais intercambiáveis: Evolution API (Baileys, self-hosted, usado
na demo) e Meta Cloud API (oficial, para produção com cliente real).

## Arquitetura

- FastAPI (`app/main.py`), máquina de estados em `app/engine.py` (independente
  do canal — mesma lógica pra Evolution e Meta).
- Canais em `app/channels/`: `base.py` (interface), `evolution.py`, `meta.py`.
  Selecionado via `CHANNEL=evolution|meta` no `.env`.
- Regras de negócio por cliente em YAML (`config/*.yaml` — ver
  `config/studio_fit.yaml` como referência). Nunca hardcode regras de um
  cliente no código Python.
- Estado de conversa em SQLite local (`app/store.py`), sem fila/retry.
- LLM de fallback opcional (`app/llm.py`), desligado por padrão.

## Comandos-chave

```bash
cd bot
uv sync
uv run pytest -q                          # suite de testes
uv run uvicorn app.main:app --port 8000   # subir a API (fica em foreground — usar background=true)
uv run python scripts/setup_instance.py   # criar instância Evolution + QR code
```

Docker (Evolution API + Postgres + Redis): `cd ../docker && docker compose up -d`.
Docker Desktop precisa estar aberto manualmente antes (Windows) — não sobe sozinho via CLI headless.

## Convenções

- Português nas mensagens do bot e nos YAMLs de regras (cliente final é BR).
- Inglês/português neutro no código e nos testes — sem regra rígida, seguir o
  arquivo que está sendo editado.
- Toda integração de canal nova implementa `app/channels/base.py`.
- Testes cobrem `app/engine.py` (máquina de estados) e adapters de canal
  (`tests/test_engine.py`, `tests/test_meta_channel.py`) — qualquer mudança de
  comportamento do bot precisa de teste correspondente.

## Limitações conhecidas (não "corrigir" sem discutir)

- Evolution API usa Baileys (engenharia reversa do WhatsApp Web) — arriscado
  pra produção, adequado só pra demo/portfólio. Produção real = Meta Cloud API.
- Sem fila/retry de envio — falha de rede na Evolution API perde a mensagem.
- Cliente final gera as próprias credenciais Meta Cloud API (Bruno não tem
  conta Business própria verificada) — o vídeo tutorial de setup é entregável
  separado, não faz parte deste código.

## Ao pedir mudanças aqui

Rodar `uv run pytest -q` sempre antes de reportar concluído. Nunca editar
`app/engine.py` sem rodar os testes de máquina de estados — regressão aqui
quebra o handoff humano, que é a feature mais sensível do produto.
