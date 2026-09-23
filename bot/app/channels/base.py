"""Interface comum aos canais de envio de WhatsApp (Evolution, Meta Cloud API)."""
from __future__ import annotations

from typing import Protocol


class Channel(Protocol):
    async def send_text(self, to: str, text: str) -> dict: ...
