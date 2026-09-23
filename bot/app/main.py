"""API do bot de atendimento WhatsApp."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from app.channels.base import Channel
from app.channels.evolution import EvolutionClient
from app.channels.meta import MetaCloudChannel
from app.config import load_config
from app.engine import Engine, EngineResult
from app.store import Store

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

app = FastAPI(title="WhatsApp Bot")

config = load_config()
store = Store()

CHANNEL_NAME = os.getenv("CHANNEL", "evolution")
evolution = EvolutionClient()
meta = MetaCloudChannel()
channel: Channel = meta if CHANNEL_NAME == "meta" else evolution

engine = Engine(config=config, store=store, handoff_number=os.getenv(config.handoff_number_env, ""))


def extract_message(data: dict[str, Any]) -> dict[str, Any] | None:
    """Extrai remoteJid/texto/pushName de um item `data` de messages.upsert; None se deve ser ignorado."""
    key = data.get("key", {}) or {}
    remote_jid = key.get("remoteJid", "")

    if key.get("fromMe"):
        return None
    if not remote_jid or remote_jid.endswith("@g.us") or remote_jid == "status@broadcast":
        return None

    message = data.get("message", {}) or {}
    text = message.get("conversation") or (message.get("extendedTextMessage") or {}).get("text")
    if not text:
        return None

    return {
        "jid": remote_jid,
        "text": text,
        "name": data.get("pushName"),
    }


async def dispatch_result(result: EngineResult, jid: str, name: str | None) -> None:
    """Envia as respostas produzidas pelo engine (resposta ao remetente, resposta a
    outro jid, notificação de handoff) pelo canal ativo."""
    if result.reply_to_sender:
        await channel.send_text(jid, result.reply_to_sender)
    if result.notify_target:
        await channel.send_text(result.notify_target["jid"], result.notify_target["text"])
    if result.notify_handoff:
        handoff_number = os.getenv(config.handoff_number_env, "")
        if handoff_number:
            history_lines = "\n".join(
                f"[{m['direction']}] {m['text']}" for m in result.notify_handoff["history"]
            )
            text = (
                f"🔔 Cliente {result.notify_handoff['name']} ({jid}) pediu atendimento humano.\n\n"
                f"Últimas mensagens:\n{history_lines}\n\n"
                f"Envie #assumir {jid.split('@')[0]} para assumir a conversa."
            )
            await channel.send_text(handoff_number, text)


@app.post("/webhook")
async def webhook(request: Request):
    payload = await request.json()
    event = payload.get("event", "")
    if event and event.replace("_", ".") != "messages.upsert" and event != "MESSAGES_UPSERT":
        return JSONResponse({"ignored": True, "reason": "event"})

    raw_data = payload.get("data")
    items = raw_data if isinstance(raw_data, list) else [raw_data] if raw_data else []

    results = []
    for item in items:
        parsed = extract_message(item)
        if parsed is None:
            continue

        result = engine.handle_message(parsed["jid"], parsed["text"], parsed["name"])
        await dispatch_result(result, parsed["jid"], parsed["name"])

        results.append({"jid": parsed["jid"], "replied": bool(result.reply_to_sender)})

    return {"processed": len(results), "results": results}


@app.get("/webhook/meta")
async def webhook_meta_verify(request: Request):
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge", "")
    verify_token = os.getenv("META_VERIFY_TOKEN", "")

    if mode == "subscribe" and verify_token and token == verify_token:
        return PlainTextResponse(challenge, status_code=200)
    return PlainTextResponse("Forbidden", status_code=403)


@app.post("/webhook/meta")
async def webhook_meta(request: Request):
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    if not meta.verify_signature(raw_body, signature):
        return PlainTextResponse("Forbidden", status_code=403)

    payload = json.loads(raw_body or b"{}")

    messages = meta.parse_webhook(payload)
    results = []
    for msg in messages:
        result = engine.handle_message(msg["jid"], msg["text"], msg["name"])
        await dispatch_result(result, msg["jid"], msg["name"])
        if msg.get("message_id"):
            await meta.mark_read(msg["message_id"])
        results.append({"jid": msg["jid"], "replied": bool(result.reply_to_sender)})

    return {"processed": len(results), "results": results}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/conversations")
async def conversations():
    rows = store.list_conversations()
    return [
        {
            "jid": row["jid"],
            "name": row["name"],
            "state": row["state"],
            "fallback_count": row["fallback_count"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]
