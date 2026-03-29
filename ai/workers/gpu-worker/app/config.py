from __future__ import annotations

from dataclasses import dataclass
import os


def _env_str(name: str, default: str) -> str:
    return os.getenv(name, default).strip()


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class ReconstructionSettings:
    max_side: int = 1536
    crop_ratio: float = 0.72
    min_width_warning: int = 720
    min_height_warning: int = 960
    min_width_reject: int = 480
    min_height_reject: int = 640
    brightness_warning: float = 55.0
    brightness_reject: float = 35.0
    blur_warning: float = 120.0
    blur_reject: float = 45.0
    aspect_ratio_warning_min: float = 0.35
    aspect_ratio_warning_max: float = 0.85
    aspect_ratio_reject_min: float = 0.25
    aspect_ratio_reject_max: float = 1.10


@dataclass(frozen=True)
class Sam3DSettings:
    repo_path: str = "ai/third_party/sam-3d-body"
    checkpoint_path: str = ""
    mhr_path: str = ""
    hf_repo_id: str = ""
    device: str = "auto"
    detector_name: str = "vitdet"
    segmentor_name: str = "sam2"
    fov_name: str = "moge2"
    detector_path: str = ""
    segmentor_path: str = ""
    fov_path: str = ""
    bbox_thresh: float = 0.8
    use_mask: bool = False
    person_selection: str = "largest_bbox"

    @classmethod
    def from_env(cls) -> "Sam3DSettings":
        return cls(
            repo_path=_env_str("SAM3D_REPO_PATH", "ai/third_party/sam-3d-body"),
            checkpoint_path=_env_str("SAM3D_CHECKPOINT_PATH", ""),
            mhr_path=_env_str("SAM3D_MHR_PATH", ""),
            hf_repo_id=_env_str("SAM3D_HF_REPO_ID", ""),
            device=_env_str("SAM3D_DEVICE", "auto"),
            detector_name=_env_str("SAM3D_DETECTOR_NAME", "vitdet"),
            segmentor_name=_env_str("SAM3D_SEGMENTOR_NAME", "sam2"),
            fov_name=_env_str("SAM3D_FOV_NAME", "moge2"),
            detector_path=_env_str("SAM3D_DETECTOR_PATH", ""),
            segmentor_path=_env_str("SAM3D_SEGMENTOR_PATH", ""),
            fov_path=_env_str("SAM3D_FOV_PATH", ""),
            bbox_thresh=_env_float("SAM3D_BBOX_THRESH", 0.8),
            use_mask=_env_bool("SAM3D_USE_MASK", False),
            person_selection=_env_str("SAM3D_PERSON_SELECTION", "largest_bbox"),
        )

    def with_overrides(self, **overrides: object) -> "Sam3DSettings":
        values = {
            "repo_path": self.repo_path,
            "checkpoint_path": self.checkpoint_path,
            "mhr_path": self.mhr_path,
            "hf_repo_id": self.hf_repo_id,
            "device": self.device,
            "detector_name": self.detector_name,
            "segmentor_name": self.segmentor_name,
            "fov_name": self.fov_name,
            "detector_path": self.detector_path,
            "segmentor_path": self.segmentor_path,
            "fov_path": self.fov_path,
            "bbox_thresh": self.bbox_thresh,
            "use_mask": self.use_mask,
            "person_selection": self.person_selection,
        }
        for key, value in overrides.items():
            if value is not None:
                values[key] = value
        return Sam3DSettings(**values)
