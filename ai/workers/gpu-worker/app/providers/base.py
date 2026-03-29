from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from PIL import Image

from app.models import ValidationResult


@dataclass
class ProviderOutput:
    mask_image: Image.Image
    masked_preview_image: Image.Image
    keypoints: list[dict[str, Any]]
    body_params: dict[str, Any]
    raw_mesh_obj: str
    quality_scores: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


class BaseReconstructionProvider(ABC):
    name: str
    version: str

    @abstractmethod
    def run(self, image: Image.Image, sample_id: str, validation: ValidationResult) -> ProviderOutput:
        raise NotImplementedError
