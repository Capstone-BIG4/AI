from __future__ import annotations

from fastapi import APIRouter, File, UploadFile

from backend.app.schemas.uploads import UploadResponse
from backend.app.services.uploads import save_upload


router = APIRouter()


@router.post("/uploads/{slot}", response_model=UploadResponse)
async def upload(slot: str, file: UploadFile = File(...)) -> UploadResponse:
    return await save_upload(slot, file)
