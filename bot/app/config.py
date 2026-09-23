"""Carregamento do arquivo de regras de negócio (YAML)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "studio_fit.yaml"


@dataclass
class Intent:
    id: str
    option: str
    keywords: list[str]
    reply: str


@dataclass
class BusinessConfig:
    business_name: str
    welcome_message: str
    menu_message: str
    fallback_message: str
    handoff_message: str
    intents: list[Intent]
    handoff_number_env: str
    business_hours: str
    fallback_attempts_before_handoff: int
    session_timeout_minutes: int
    llm_enabled: bool
    llm_model: str
    llm_system_prompt: str
    raw: dict = field(default_factory=dict)

    @property
    def full_welcome_message(self) -> str:
        return f"{self.welcome_message.strip()}\n\n{self.menu_message.strip()}"


def load_config(path: str | Path | None = None) -> BusinessConfig:
    config_path = Path(path) if path else Path(os.getenv("BUSINESS_CONFIG", DEFAULT_CONFIG_PATH))
    if not config_path.is_absolute():
        config_path = Path(__file__).resolve().parent.parent / config_path
    with open(config_path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    intents = [
        Intent(
            id=item["id"],
            option=str(item.get("option", "")),
            keywords=list(item.get("keywords", [])),
            reply=item.get("reply", ""),
        )
        for item in data.get("intents", [])
    ]

    handoff = data.get("handoff", {})
    session = data.get("session", {})
    llm = data.get("llm", {})

    return BusinessConfig(
        business_name=data["business_name"],
        welcome_message=data["welcome_message"],
        menu_message=data["menu_message"],
        fallback_message=data["fallback_message"],
        handoff_message=data["handoff_message"],
        intents=intents,
        handoff_number_env=handoff.get("number_env", "HANDOFF_NUMBER"),
        business_hours=handoff.get("business_hours", ""),
        fallback_attempts_before_handoff=int(handoff.get("fallback_attempts_before_handoff", 2)),
        session_timeout_minutes=int(session.get("timeout_minutes", 30)),
        llm_enabled=bool(llm.get("enabled", False)),
        llm_model=llm.get("model", ""),
        llm_system_prompt=llm.get("system_prompt", ""),
        raw=data,
    )
