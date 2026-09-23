"""Máquina de estados do atendimento."""
from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass

from app.config import BusinessConfig
from app.store import Store

STATE_MENU = "menu"
STATE_AGUARDANDO_HUMANO = "aguardando_humano"
STATE_HUMANO_ATIVO = "humano_ativo"

ASSUMIR_RE = re.compile(r"^#assumir\s+(\d+)$", re.IGNORECASE)
LIBERAR_RE = re.compile(r"^#liberar\s+(\d+)$", re.IGNORECASE)
MENU_RE = re.compile(r"^#menu$", re.IGNORECASE)


def normalize_text(text: str) -> str:
    text = text.strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text


def digits_only(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def jid_digits(jid: str) -> str:
    return digits_only(jid.split("@")[0])


@dataclass
class EngineResult:
    """Resultado do processamento de uma mensagem."""

    reply_to_sender: str | None = None
    notify_handoff: dict | None = None
    notify_target: dict | None = None  # {"jid": ..., "text": ...} resposta a outro jid (ex.: atendente)


class Engine:
    def __init__(self, config: BusinessConfig, store: Store, handoff_number: str = ""):
        self.config = config
        self.store = store
        self.handoff_number = digits_only(handoff_number)

    def _is_attendant(self, jid: str) -> bool:
        return bool(self.handoff_number) and jid_digits(jid) == self.handoff_number

    def _match_intent(self, text: str):
        normalized = normalize_text(text)
        for intent in self.config.intents:
            if intent.option and normalized == intent.option:
                return intent
        for intent in self.config.intents:
            if any(normalize_text(kw) in normalized for kw in intent.keywords):
                return intent
        return None

    def _find_jid_by_digits(self, number: str) -> str | None:
        for row in self.store.list_conversations(limit=1000):
            if jid_digits(row["jid"]) == number:
                return row["jid"]
        return None

    def handle_attendant_command(self, jid: str, text: str) -> EngineResult:
        stripped = text.strip()

        m = ASSUMIR_RE.match(stripped)
        if m:
            number = m.group(1)
            target_jid = self._find_jid_by_digits(number)
            if target_jid is None:
                return EngineResult(notify_target={"jid": jid, "text": f"Contato {number} não encontrado."})
            self.store.upsert_contact(target_jid, state=STATE_HUMANO_ATIVO)
            return EngineResult(notify_target={"jid": jid, "text": f"Você assumiu a conversa com {number}."})

        m = LIBERAR_RE.match(stripped)
        if m:
            number = m.group(1)
            target_jid = self._find_jid_by_digits(number)
            if target_jid is None:
                return EngineResult(notify_target={"jid": jid, "text": f"Contato {number} não encontrado."})
            self.store.upsert_contact(target_jid, state=STATE_MENU, fallback_count=0)
            return EngineResult(notify_target={"jid": jid, "text": f"Conversa com {number} liberada para o bot."})

        return EngineResult()

    def handle_message(self, jid: str, text: str, name: str | None = None) -> EngineResult:
        if self._is_attendant(jid):
            return self.handle_attendant_command(jid, text)

        self.store.add_message(jid, "in", text)
        contact = self.store.get_contact(jid)

        if contact is None:
            self.store.upsert_contact(jid, name=name, state=STATE_MENU, fallback_count=0)
            reply = self.config.full_welcome_message
            self.store.add_message(jid, "out", reply)
            return EngineResult(reply_to_sender=reply)

        timeout_seconds = self.config.session_timeout_minutes * 60
        state = contact["state"]
        session_expired = False
        if state != STATE_HUMANO_ATIVO and (time.time() - contact["updated_at"]) > timeout_seconds:
            state = STATE_MENU
            session_expired = True
            self.store.upsert_contact(jid, name=name, state=STATE_MENU, fallback_count=0)

        if MENU_RE.match(text.strip()):
            self.store.upsert_contact(jid, name=name, state=STATE_MENU, fallback_count=0)
            reply = self.config.menu_message
            self.store.add_message(jid, "out", reply)
            return EngineResult(reply_to_sender=reply)

        if state == STATE_HUMANO_ATIVO:
            self.store.upsert_contact(jid, name=name)
            return EngineResult()

        if state == STATE_AGUARDANDO_HUMANO:
            self.store.upsert_contact(jid, name=name)
            return EngineResult()

        intent = self._match_intent(text)

        if intent is not None and intent.id == "humano":
            return self._start_handoff(jid, name, contact)
        if intent is not None:
            self.store.upsert_contact(jid, name=name, state=STATE_MENU, fallback_count=0)
            reply = intent.reply
            self.store.add_message(jid, "out", reply)
            return EngineResult(reply_to_sender=reply)

        fallback_count = (0 if session_expired else contact["fallback_count"]) + 1
        if fallback_count >= self.config.fallback_attempts_before_handoff:
            return self._start_handoff(jid, name, contact)

        self.store.upsert_contact(jid, name=name, state=STATE_MENU, fallback_count=fallback_count)
        reply = self.config.menu_message if session_expired else self.config.fallback_message
        self.store.add_message(jid, "out", reply)
        return EngineResult(reply_to_sender=reply)

    def _start_handoff(self, jid: str, name: str | None, contact) -> EngineResult:
        self.store.upsert_contact(jid, name=name, state=STATE_AGUARDANDO_HUMANO, fallback_count=0)
        reply = self.config.handoff_message
        self.store.add_message(jid, "out", reply)
        history = self.store.last_messages(jid, limit=5)
        notify = {
            "jid": jid,
            "name": name or (contact["name"] if contact else None) or jid,
            "history": [{"direction": m["direction"], "text": m["text"]} for m in history],
        }
        return EngineResult(reply_to_sender=reply, notify_handoff=notify)
