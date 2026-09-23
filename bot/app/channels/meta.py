"""Cliente para a Meta WhatsApp Cloud API (Graph API) — https://developers.facebook.com/docs/whatsapp/cloud-api"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class MetaCloudChannel:
    def __init__(self, access_token: str | None = None, phone_number_id: str | None = None,
                 app_secret: str | None = None, graph_version: str | None = None,
                 timeout: float = 10.0):
        self.access_token = access_token or os.getenv("META_ACCESS_TOKEN", "")
        self.phone_number_id = phone_number_id or os.getenv("META_PHONE_NUMBER_ID", "")
        self.app_secret = app_secret if app_secret is not None else os.getenv("META_APP_SECRET", "")
        self.graph_version = graph_version or os.getenv("META_GRAPH_VERSION", "v23.0")
        self.timeout = timeout

    def _url(self) -> str:
        return f"https://graph.facebook.com/{self.graph_version}/{self.phone_number_id}/messages"

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}

    async def send_text(self, to: str, text: str) -> dict:
        """Envia texto. Falhas de rede/API são logadas e não propagam,
        para que o webhook responda 200 e a Meta não fique reenviando o evento."""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(self._url(), json=payload, headers=self._headers())
                resp.raise_for_status()
                return resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("send_text falhou para %s: %s", to, exc)
            return {"error": str(exc)}

    async def mark_read(self, message_id: str) -> dict:
        """Marca mensagem como lida. Best-effort: falhas são logadas e não propagam."""
        payload = {"messaging_product": "whatsapp", "status": "read", "message_id": message_id}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(self._url(), json=payload, headers=self._headers())
                resp.raise_for_status()
                return resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("mark_read falhou para %s: %s", message_id, exc)
            return {"error": str(exc)}

    def verify_signature(self, raw_body: bytes, header: str | None) -> bool:
        if not self.app_secret:
            return True
        if not header or not header.startswith("sha256="):
            return False
        expected = hmac.new(self.app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        received = header[len("sha256="):]
        return hmac.compare_digest(expected, received)

    def parse_webhook(self, payload: dict) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        for entry in payload.get("entry", []) or []:
            for change in entry.get("changes", []) or []:
                value = change.get("value", {}) or {}
                contacts = value.get("contacts") or []
                name = None
                if contacts:
                    name = (contacts[0].get("profile") or {}).get("name")
                for msg in value.get("messages", []) or []:
                    if msg.get("type") != "text":
                        continue
                    from_ = msg.get("from")
                    if not from_:
                        continue
                    body = (msg.get("text") or {}).get("body")
                    if not body:
                        continue
                    messages.append({
                        "jid": from_,
                        "text": body,
                        "name": name,
                        "message_id": msg.get("id"),
                    })
        return messages
