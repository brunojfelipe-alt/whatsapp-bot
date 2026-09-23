"""Cria a instância na Evolution API, registra o webhook e salva o QR code.

Uso: uv run python scripts/setup_instance.py
"""
from __future__ import annotations

import asyncio
import base64
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from app.evolution import EvolutionClient  # noqa: E402

QR_PATH = ROOT / "data" / "qr.png"


def _save_qr(qr_data: dict) -> bool:
    base64_str = qr_data.get("base64") or qr_data.get("qrcode", {}).get("base64")
    if not base64_str:
        return False
    if "," in base64_str:
        base64_str = base64_str.split(",", 1)[1]
    QR_PATH.parent.mkdir(parents=True, exist_ok=True)
    QR_PATH.write_bytes(base64.b64decode(base64_str))
    return True


async def main() -> None:
    evolution = EvolutionClient()
    webhook_url = os.getenv("WEBHOOK_URL", "http://host.docker.internal:8000/webhook")

    print(f"Criando instância '{evolution.instance}' em {evolution.base_url} ...")
    create_resp = await evolution.create_instance(qrcode=True)
    print("Instância criada.")

    saved = False
    qrcode_field = create_resp.get("qrcode")
    if isinstance(qrcode_field, dict):
        saved = _save_qr(qrcode_field)

    print(f"Configurando webhook -> {webhook_url}")
    await evolution.set_webhook(webhook_url, events=["MESSAGES_UPSERT"])
    print("Webhook configurado.")

    if not saved:
        print("QR code não veio na resposta de criação; buscando via /instance/connect ...")
        qr_resp = await evolution.get_qr()
        saved = _save_qr(qr_resp)

    if saved:
        print(f"QR code salvo em {QR_PATH}")
    else:
        print("Não foi possível salvar o QR code automaticamente. Use o link abaixo.")

    print(f"Escaneie o QR code em: {evolution.base_url}/instance/connect/{evolution.instance}")


if __name__ == "__main__":
    asyncio.run(main())
