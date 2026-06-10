from __future__ import annotations

from pydantic import BaseModel


class UploadResponse(BaseModel):
    slot: str
    filename: str
    bytes: int
    url: str
