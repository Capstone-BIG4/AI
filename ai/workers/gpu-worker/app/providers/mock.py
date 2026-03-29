from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

from PIL import Image, ImageDraw

from app.models import ValidationResult
from app.providers.base import BaseReconstructionProvider, ProviderOutput


@dataclass
class MockReconstructionProvider(BaseReconstructionProvider):
    name: str = "mock"
    version: str = "mock-reconstruction-v1"

    def run(self, image: Image.Image, sample_id: str, validation: ValidationResult) -> ProviderOutput:
        width, height = image.size
        seed = int(hashlib.sha1(f"{sample_id}:{width}:{height}".encode("utf-8")).hexdigest()[:8], 16)
        rng = random.Random(seed)

        mask_image = self._build_mask(width=width, height=height)
        masked_preview = self._build_masked_preview(image=image, mask_image=mask_image)
        keypoints = self._build_keypoints(width=width, height=height)
        body_params = self._build_body_params(rng=rng, validation=validation)
        raw_mesh_obj = self._build_proxy_mesh(rng=rng)
        quality_scores = self._build_quality_scores(validation=validation)

        return ProviderOutput(
            mask_image=mask_image,
            masked_preview_image=masked_preview,
            keypoints=keypoints,
            body_params=body_params,
            raw_mesh_obj=raw_mesh_obj,
            quality_scores=quality_scores,
            notes=[
                "mock provider result",
                "synthetic body proxy output",
                "replace with sam3d provider when environment is ready",
            ],
        )

    def _build_mask(self, width: int, height: int) -> Image.Image:
        mask = Image.new("L", (width, height), 0)
        draw = ImageDraw.Draw(mask)

        draw.ellipse((width * 0.39, height * 0.05, width * 0.61, height * 0.19), fill=255)
        draw.rounded_rectangle((width * 0.34, height * 0.17, width * 0.66, height * 0.55), radius=30, fill=255)
        draw.rectangle((width * 0.26, height * 0.20, width * 0.36, height * 0.52), fill=255)
        draw.rectangle((width * 0.64, height * 0.20, width * 0.74, height * 0.52), fill=255)
        draw.rectangle((width * 0.40, height * 0.55, width * 0.49, height * 0.93), fill=255)
        draw.rectangle((width * 0.51, height * 0.55, width * 0.60, height * 0.93), fill=255)
        return mask

    def _build_masked_preview(self, image: Image.Image, mask_image: Image.Image) -> Image.Image:
        source = image.convert("RGBA")
        alpha = mask_image.resize(image.size)
        source.putalpha(alpha)
        background = Image.new("RGBA", image.size, (20, 24, 32, 255))
        background.alpha_composite(source)
        return background.convert("RGB")

    def _build_keypoints(self, width: int, height: int) -> list[dict[str, float | str]]:
        points = {
            "nose": (0.50, 0.12),
            "left_eye": (0.47, 0.11),
            "right_eye": (0.53, 0.11),
            "left_ear": (0.43, 0.12),
            "right_ear": (0.57, 0.12),
            "left_shoulder": (0.39, 0.23),
            "right_shoulder": (0.61, 0.23),
            "left_elbow": (0.31, 0.37),
            "right_elbow": (0.69, 0.37),
            "left_wrist": (0.29, 0.52),
            "right_wrist": (0.71, 0.52),
            "left_hip": (0.44, 0.52),
            "right_hip": (0.56, 0.52),
            "left_knee": (0.45, 0.73),
            "right_knee": (0.55, 0.73),
            "left_ankle": (0.45, 0.94),
            "right_ankle": (0.55, 0.94),
        }
        return [
            {
                "name": name,
                "x": round(x * width, 2),
                "y": round(y * height, 2),
                "confidence": 0.92,
            }
            for name, (x, y) in points.items()
        ]

    def _build_body_params(self, rng: random.Random, validation: ValidationResult) -> dict[str, object]:
        return {
            "body_model_type": "mock-smpl",
            "shape_params": [round(rng.uniform(-0.8, 0.8), 4) for _ in range(10)],
            "pose_params": {"root_orient": [0.0, 0.0, 0.0], "body_pose": [0.0 for _ in range(63)]},
            "camera": {"fov_degrees": 35.0, "distance_m": 2.4},
            "validation_decision": validation.decision,
        }

    def _build_quality_scores(self, validation: ValidationResult) -> dict[str, float]:
        decision_score = {"pass": 0.92, "warning": 0.71, "reject": 0.2}[validation.decision]
        brightness_score = min(1.0, validation.metrics.brightness_mean / 160.0)
        blur_score = min(1.0, validation.metrics.blur_score / 240.0)
        reconstruction_score = round((decision_score + brightness_score + blur_score) / 3.0, 4)
        return {
            "validation_score": round(decision_score, 4),
            "brightness_score": round(brightness_score, 4),
            "blur_score": round(blur_score, 4),
            "reconstruction_score": reconstruction_score,
        }

    def _build_proxy_mesh(self, rng: random.Random) -> str:
        shoulder = round(0.42 + rng.uniform(-0.03, 0.03), 4)
        hip = round(0.30 + rng.uniform(-0.03, 0.03), 4)
        depth = round(0.22 + rng.uniform(-0.02, 0.02), 4)
        head = 0.18
        torso_top = 1.45
        torso_mid = 0.95
        hip_y = 0.62
        foot_y = 0.02

        vertices = [
            (-head / 2, 1.72, -head / 2),
            (head / 2, 1.72, -head / 2),
            (head / 2, 1.90, head / 2),
            (-head / 2, 1.90, head / 2),
            (-shoulder / 2, torso_top, -depth / 2),
            (shoulder / 2, torso_top, -depth / 2),
            (shoulder / 2, torso_top, depth / 2),
            (-shoulder / 2, torso_top, depth / 2),
            (-hip / 2, torso_mid, -depth / 2),
            (hip / 2, torso_mid, -depth / 2),
            (hip / 2, torso_mid, depth / 2),
            (-hip / 2, torso_mid, depth / 2),
            (-hip / 2, hip_y, -depth / 2),
            (hip / 2, hip_y, -depth / 2),
            (hip / 2, hip_y, depth / 2),
            (-hip / 2, hip_y, depth / 2),
            (-0.12, foot_y, -depth / 3),
            (-0.02, foot_y, -depth / 3),
            (-0.02, foot_y, depth / 3),
            (-0.12, foot_y, depth / 3),
            (0.02, foot_y, -depth / 3),
            (0.12, foot_y, -depth / 3),
            (0.12, foot_y, depth / 3),
            (0.02, foot_y, depth / 3),
        ]
        faces = [
            (1, 2, 3), (1, 3, 4),
            (5, 6, 7), (5, 7, 8),
            (9, 10, 11), (9, 11, 12),
            (13, 14, 15), (13, 15, 16),
            (5, 6, 10), (5, 10, 9),
            (8, 7, 11), (8, 11, 12),
            (9, 10, 14), (9, 14, 13),
            (12, 11, 15), (12, 15, 16),
            (13, 17, 18), (13, 18, 14),
            (16, 19, 20), (16, 20, 13),
            (14, 21, 22), (14, 22, 15),
            (15, 23, 24), (15, 24, 16),
        ]
        lines = ["# mock body proxy mesh"]
        lines.extend(f"v {x} {y} {z}" for x, y, z in vertices)
        lines.extend(f"f {a} {b} {c}" for a, b, c in faces)
        return "\n".join(lines) + "\n"
