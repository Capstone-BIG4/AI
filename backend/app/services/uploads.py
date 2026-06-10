from __future__ import annotations

import re
from pathlib import Path

from fastapi import HTTPException, UploadFile

from backend.app.core.paths import CURRENT_INPUTS, UPLOADS
from backend.app.core.settings import settings
from backend.app.schemas.uploads import UploadResponse


ALLOWED_UPLOAD_SLOTS = {
    "person",
    "top-front",
    "top-back",
    "pants-front",
    "pants-back",
}

CANONICAL_INPUT_SLOTS = {
    "person": "person",
    "top-front": "top-front",
    "top-back": "top-back",
    "pants-front": "pants-front",
    "pants-back": "pants-back",
}


def safe_filename(name: str) -> str:
    base = Path(name).name
    cleaned = re.sub(r"[^0-9A-Za-z._가-힣-]+", "_", base).strip("._")
    return cleaned or "upload.bin"


def replace_canonical_input(slot: str, filename: str, content: bytes) -> Path:
    canonical_dir = CURRENT_INPUTS / CANONICAL_INPUT_SLOTS[slot]
    canonical_dir.mkdir(parents=True, exist_ok=True)
    for old_file in canonical_dir.iterdir():
        if old_file.is_file():
            old_file.unlink()
    path = canonical_dir / filename
    path.write_bytes(content)
    return path


def required_inputs_ready() -> bool:
    for slot in CANONICAL_INPUT_SLOTS:
        slot_dir = CURRENT_INPUTS / slot
        if not slot_dir.exists() or not any(path.is_file() for path in slot_dir.iterdir()):
            return False
    return True


async def save_upload(slot: str, file: UploadFile) -> UploadResponse:
    if slot not in ALLOWED_UPLOAD_SLOTS:
        raise HTTPException(status_code=404, detail="unknown upload slot")

    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="file too large")

    slot_dir = UPLOADS / slot
    slot_dir.mkdir(parents=True, exist_ok=True)
    filename = safe_filename(file.filename or f"{slot}.png")
    path = slot_dir / filename
    path.write_bytes(content)
    replace_canonical_input(slot, filename, content)
    return UploadResponse(
        slot=slot,
        filename=filename,
        bytes=len(content),
        url=f"/runtime/uploads/{slot}/{filename}",
    )
