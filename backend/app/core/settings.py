from __future__ import annotations

import os
from dataclasses import dataclass

from backend.app.core.paths import ROOT


@dataclass(frozen=True)
class Settings:
    app_name: str = "Virtual Fitting Studio"
    version: str = "1.0"
    conda_env: str = "bys"
    max_upload_bytes: int = 30 * 1024 * 1024


settings = Settings()


def load_runtime_env() -> tuple[dict[str, str], list[str]]:
    env = os.environ.copy()
    secrets: list[str] = []
    env_path = ROOT / ".env"
    if not env_path.exists():
        return env, secrets

    for raw in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            continue
        env.setdefault(key, value)
        if value:
            secrets.append(value)
    return env, secrets


def redact_secrets(text: str, secrets: list[str]) -> str:
    redacted = text
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    return redacted
