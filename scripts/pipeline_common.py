from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
PIPELINE = ASSETS / "pipeline"
INPUT_SLOT_DIRS = {
    "person": "person",
    "top_front": "top-front",
    "top_back": "top-back",
    "pants_front": "pants-front",
    "pants_back": "pants-back",
}
LEGACY_INPUTS = {
    "person": ROOT / "image" / "은수형 사진.jpg",
    "top_front": ROOT / "image" / "top_front.png",
    "top_back": ROOT / "image" / "top_back.png",
    "pants_front": ROOT / "image" / "front_pants.png",
    "pants_back": ROOT / "image" / "back_pants.png",
}
ASSET_INPUTS = {
    "person": ASSETS / "processed" / "person-oriented.jpg",
    "top_front": ASSETS / "processed" / "top-front-cutout.png",
    "top_back": ASSETS / "processed" / "top-back-cutout.png",
    "pants_front": ASSETS / "processed" / "pants-front-cutout.png",
    "pants_back": ASSETS / "processed" / "pants-back-cutout.png",
}


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def latest_file(directory: Path) -> Path | None:
    if not directory.exists():
        return None
    files = [path for path in directory.iterdir() if path.is_file()]
    if not files:
        return None
    return max(files, key=lambda path: path.stat().st_mtime)


def resolve_input_path(key: str) -> Path:
    if key not in INPUT_SLOT_DIRS:
        raise KeyError(key)
    candidates = [
        latest_file(ROOT / "runtime" / "inputs" / INPUT_SLOT_DIRS[key]),
        LEGACY_INPUTS[key],
        ASSET_INPUTS[key],
    ]
    for candidate in candidates:
        if candidate is not None and candidate.exists():
            return candidate
    raise FileNotFoundError(f"Missing input for {key}; upload it through the UI or provide the matching sample file.")


def read_env_keys(env_path: Path = ROOT / ".env") -> dict[str, str]:
    values: dict[str, str] = {}
    if not env_path.exists():
        return values
    for raw in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def load_env_without_printing(env_path: Path = ROOT / ".env") -> dict[str, str]:
    values = read_env_keys(env_path)
    for key, value in values.items():
        os.environ.setdefault(key, value)
    return values


def redact_secret(text: str, secrets: list[str]) -> str:
    redacted = text
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    return redacted


def write_json(path: Path, data: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


@dataclass
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str


def run_command(command: list[str], secrets: list[str] | None = None, cwd: Path = ROOT, timeout: int | None = None) -> CommandResult:
    secrets = secrets or []
    proc = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return CommandResult(
        command=command,
        returncode=proc.returncode,
        stdout=redact_secret(proc.stdout, secrets),
        stderr=redact_secret(proc.stderr, secrets),
    )


def import_optional(name: str) -> bool:
    try:
        __import__(name)
        return True
    except Exception:
        return False


def image_info(path: Path) -> dict[str, Any]:
    from PIL import Image

    with Image.open(path) as im:
        return {
            "path": str(path.relative_to(ROOT)),
            "width": im.width,
            "height": im.height,
            "mode": im.mode,
        }


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def python_executable() -> str:
    return sys.executable
