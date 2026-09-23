from pathlib import Path

import pytest

from app.config import load_config
from app.engine import STATE_AGUARDANDO_HUMANO, STATE_HUMANO_ATIVO, STATE_MENU, Engine
from app.store import Store

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "studio_fit.yaml"
JID = "5511988887777@s.whatsapp.net"
ATTENDANT_NUMBER = "5511999999999"
ATTENDANT_JID = f"{ATTENDANT_NUMBER}@s.whatsapp.net"


@pytest.fixture
def engine(tmp_path):
    store = Store(db_path=tmp_path / "test.db")
    config = load_config(CONFIG_PATH)
    return Engine(config=config, store=store, handoff_number=ATTENDANT_NUMBER)


def test_first_message_sends_welcome_and_menu(engine):
    result = engine.handle_message(JID, "oi", "Cliente Teste")
    assert "Studio Fit" in result.reply_to_sender
    assert "1" in result.reply_to_sender
    contact = engine.store.get_contact(JID)
    assert contact["state"] == STATE_MENU


def test_menu_option_by_number(engine):
    engine.handle_message(JID, "oi", "Cliente")
    result = engine.handle_message(JID, "1", "Cliente")
    assert "6h às 22h" in result.reply_to_sender


def test_menu_option_by_keyword(engine):
    engine.handle_message(JID, "oi", "Cliente")
    result = engine.handle_message(JID, "quanto custa o plano?", "Cliente")
    assert "129,90" in result.reply_to_sender


def test_keyword_ignores_accents_and_case(engine):
    engine.handle_message(JID, "oi", "Cliente")
    result = engine.handle_message(JID, "ONDE FICA o endereço?", "Cliente")
    assert "Av. das Nações" in result.reply_to_sender


def test_option_4_triggers_handoff(engine):
    engine.handle_message(JID, "oi", "Cliente")
    result = engine.handle_message(JID, "4", "Cliente")
    assert result.notify_handoff is not None
    assert result.notify_handoff["jid"] == JID
    contact = engine.store.get_contact(JID)
    assert contact["state"] == STATE_AGUARDANDO_HUMANO


def test_fallback_twice_triggers_handoff(engine):
    engine.handle_message(JID, "oi", "Cliente")
    result1 = engine.handle_message(JID, "blablabla", "Cliente")
    assert result1.notify_handoff is None
    assert engine.store.get_contact(JID)["state"] == STATE_MENU

    result2 = engine.handle_message(JID, "xyzxyz", "Cliente")
    assert result2.notify_handoff is not None
    assert engine.store.get_contact(JID)["state"] == STATE_AGUARDANDO_HUMANO


def test_handoff_notification_contains_last_messages(engine):
    engine.handle_message(JID, "oi", "Cliente")
    engine.handle_message(JID, "1", "Cliente")
    result = engine.handle_message(JID, "4", "Cliente")
    assert len(result.notify_handoff["history"]) <= 5
    assert any(m["text"] == "1" for m in result.notify_handoff["history"])


def test_attendant_assumir_sets_humano_ativo(engine):
    engine.handle_message(JID, "oi", "Cliente")
    result = engine.handle_message(ATTENDANT_JID, f"#assumir {JID.split('@')[0]}", None)
    assert result.notify_target is not None
    assert engine.store.get_contact(JID)["state"] == STATE_HUMANO_ATIVO


def test_bot_silent_while_humano_ativo(engine):
    engine.handle_message(JID, "oi", "Cliente")
    engine.handle_message(ATTENDANT_JID, f"#assumir {JID.split('@')[0]}", None)
    result = engine.handle_message(JID, "alguma pergunta qualquer", "Cliente")
    assert result.reply_to_sender is None
    assert result.notify_handoff is None


def test_attendant_liberar_returns_to_menu(engine):
    engine.handle_message(JID, "oi", "Cliente")
    engine.handle_message(ATTENDANT_JID, f"#assumir {JID.split('@')[0]}", None)
    result = engine.handle_message(ATTENDANT_JID, f"#liberar {JID.split('@')[0]}", None)
    assert result.notify_target is not None
    assert engine.store.get_contact(JID)["state"] == STATE_MENU


def test_client_menu_command_resets_state(engine):
    engine.handle_message(JID, "oi", "Cliente")
    engine.handle_message(JID, "4", "Cliente")
    assert engine.store.get_contact(JID)["state"] == STATE_AGUARDANDO_HUMANO

    result = engine.handle_message(JID, "#menu", "Cliente")
    assert engine.store.get_contact(JID)["state"] == STATE_MENU
    assert result.reply_to_sender is not None


def test_timeout_resets_state_to_menu(engine):
    engine.handle_message(JID, "oi", "Cliente")
    engine.handle_message(JID, "4", "Cliente")
    assert engine.store.get_contact(JID)["state"] == STATE_AGUARDANDO_HUMANO

    old_ts = engine.store.get_contact(JID)["updated_at"] - (31 * 60)
    with engine.store._conn() as conn:
        conn.execute("UPDATE contacts SET updated_at = ? WHERE jid = ?", (old_ts, JID))

    result = engine.handle_message(JID, "1", "Cliente")
    assert "6h às 22h" in result.reply_to_sender
