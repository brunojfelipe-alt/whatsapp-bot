import hashlib
import hmac
import json
import os

os.environ["CHANNEL"] = "meta"
os.environ.setdefault("META_ACCESS_TOKEN", "test-token")
os.environ.setdefault("META_PHONE_NUMBER_ID", "123456123")
os.environ.setdefault("META_VERIFY_TOKEN", "test-verify-token")
os.environ.setdefault("META_APP_SECRET", "test-app-secret")

from fastapi.testclient import TestClient  # noqa: E402

from app import main as app_main  # noqa: E402
from app.channels.meta import MetaCloudChannel  # noqa: E402

client = TestClient(app_main.app)

VERIFY_TOKEN = os.environ["META_VERIFY_TOKEN"]
APP_SECRET = os.environ["META_APP_SECRET"]

SAMPLE_TEXT_PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [{
        "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
        "changes": [{
            "value": {
                "messaging_product": "whatsapp",
                "metadata": {"display_phone_number": "16505551111", "phone_number_id": "123456123"},
                "contacts": [{"profile": {"name": "Cliente Teste"}, "wa_id": "5511988887777"}],
                "messages": [{
                    "from": "5511988887777",
                    "id": "wamid.HBgLNTU5MTk4ODg4Nzc3NxUCABIYFjNBMjJCRjIzRkY1RTQ4RTQyRTQA",
                    "timestamp": "1690000000",
                    "text": {"body": "Olá"},
                    "type": "text",
                }],
            },
            "field": "messages",
        }],
    }],
}

SAMPLE_STATUS_PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [{
        "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
        "changes": [{
            "value": {
                "messaging_product": "whatsapp",
                "metadata": {"display_phone_number": "16505551111", "phone_number_id": "123456123"},
                "statuses": [{
                    "id": "wamid.xxx",
                    "status": "delivered",
                    "timestamp": "1690000000",
                    "recipient_id": "5511988887777",
                }],
            },
            "field": "messages",
        }],
    }],
}


def _sign(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _text_payload(jid: str, text: str) -> dict:
    payload = json.loads(json.dumps(SAMPLE_TEXT_PAYLOAD))
    msg = payload["entry"][0]["changes"][0]["value"]["messages"][0]
    msg["from"] = jid
    msg["text"]["body"] = text
    return payload


def test_parse_webhook_text_message():
    channel = MetaCloudChannel(app_secret="")
    messages = channel.parse_webhook(SAMPLE_TEXT_PAYLOAD)
    assert len(messages) == 1
    assert messages[0] == {
        "jid": "5511988887777",
        "text": "Olá",
        "name": "Cliente Teste",
        "message_id": "wamid.HBgLNTU5MTk4ODg4Nzc3NxUCABIYFjNBMjJCRjIzRkY1RTQ4RTQyRTQA",
    }


def test_parse_webhook_statuses_only():
    channel = MetaCloudChannel(app_secret="")
    assert channel.parse_webhook(SAMPLE_STATUS_PAYLOAD) == []


def test_verify_signature_valid():
    channel = MetaCloudChannel(app_secret="my-secret")
    body = b'{"a":1}'
    assert channel.verify_signature(body, _sign(body, "my-secret")) is True


def test_verify_signature_invalid():
    channel = MetaCloudChannel(app_secret="my-secret")
    body = b'{"a":1}'
    assert channel.verify_signature(body, "sha256=" + "0" * 64) is False


def test_verify_signature_no_secret():
    channel = MetaCloudChannel(app_secret="")
    assert channel.verify_signature(b"qualquer coisa", None) is True


def test_get_webhook_meta_verify_ok():
    resp = client.get("/webhook/meta", params={
        "hub.mode": "subscribe",
        "hub.verify_token": VERIFY_TOKEN,
        "hub.challenge": "12345",
    })
    assert resp.status_code == 200
    assert resp.text == "12345"


def test_get_webhook_meta_verify_wrong_token():
    resp = client.get("/webhook/meta", params={
        "hub.mode": "subscribe",
        "hub.verify_token": "token-errado",
        "hub.challenge": "12345",
    })
    assert resp.status_code == 403


def test_post_webhook_meta_valid_signature_processes_and_sends(monkeypatch):
    sent = {}

    async def fake_send_text(to, text):
        sent["to"] = to
        sent["text"] = text
        return {}

    async def fake_mark_read(message_id):
        sent["mark_read"] = message_id
        return {}

    monkeypatch.setattr(app_main.meta, "send_text", fake_send_text)
    monkeypatch.setattr(app_main.meta, "mark_read", fake_mark_read)

    body = json.dumps(_text_payload("5511977776666", "oi")).encode("utf-8")
    resp = client.post(
        "/webhook/meta",
        content=body,
        headers={"X-Hub-Signature-256": _sign(body, APP_SECRET), "Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    assert sent["to"] == "5511977776666"
    assert sent["mark_read"]


def test_post_webhook_meta_invalid_signature_returns_403():
    body = json.dumps(_text_payload("5511977776666", "oi")).encode("utf-8")
    resp = client.post(
        "/webhook/meta",
        content=body,
        headers={"X-Hub-Signature-256": "sha256=" + "0" * 64, "Content-Type": "application/json"},
    )
    assert resp.status_code == 403
