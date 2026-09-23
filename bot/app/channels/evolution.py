"""Cliente HTTP para a Evolution API v2 (https://doc.evolution-api.com/v2)."""
from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)


class EvolutionClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None,
                 instance: str | None = None, timeout: float = 10.0):
        self.base_url = (base_url or os.getenv("EVOLUTION_URL", "http://localhost:8080")).rstrip("/")
        self.api_key = api_key or os.getenv("EVOLUTION_API_KEY", "")
        self.instance = instance or os.getenv("EVOLUTION_INSTANCE", "")
        self.timeout = timeout

    def _headers(self) -> dict:
        return {"apikey": self.api_key, "Content-Type": "application/json"}

    async def send_text(self, number: str, text: str, instance: str | None = None) -> dict:
        """Envia texto. Falhas de rede/instância desconectada são logadas e não propagam,
        para que o webhook responda 200 e a Evolution não fique reenviando o evento."""
        instance = instance or self.instance
        url = f"{self.base_url}/message/sendText/{instance}"
        payload = {"number": number, "text": text}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload, headers=self._headers())
                resp.raise_for_status()
                return resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("send_text falhou para %s: %s", number, exc)
            return {"error": str(exc)}

    async def set_presence_typing(self, number: str, instance: str | None = None) -> dict:
        instance = instance or self.instance
        url = f"{self.base_url}/chat/sendPresence/{instance}"
        payload = {"number": number, "presence": "composing"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload, headers=self._headers())
            resp.raise_for_status()
            return resp.json()

    async def create_instance(self, instance: str | None = None, qrcode: bool = True) -> dict:
        instance = instance or self.instance
        url = f"{self.base_url}/instance/create"
        payload = {
            "instanceName": instance,
            "integration": "WHATSAPP-BAILEYS",
            "qrcode": qrcode,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload, headers=self._headers())
            resp.raise_for_status()
            return resp.json()

    async def get_qr(self, instance: str | None = None) -> dict:
        instance = instance or self.instance
        url = f"{self.base_url}/instance/connect/{instance}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url, headers=self._headers())
            resp.raise_for_status()
            return resp.json()

    async def set_webhook(self, webhook_url: str, instance: str | None = None,
                           events: list[str] | None = None) -> dict:
        instance = instance or self.instance
        events = events or ["MESSAGES_UPSERT"]
        url = f"{self.base_url}/webhook/set/{instance}"
        payload = {
            "webhook": {
                "enabled": True,
                "url": webhook_url,
                "webhookByEvents": False,
                "events": events,
            }
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload, headers=self._headers())
            resp.raise_for_status()
            return resp.json()
