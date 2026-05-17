"""Development fallback body generator.

This creates a simple mannequin-shaped GLB plus landmark/metadata JSON files.
It is not a replacement for SAM 3D Body. Its purpose is to unblock viewer and
fitting development while the real model environment is being prepared.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from backend.app.contracts.glb import Vec3, write_mesh_glb
from backend.app.contracts.body_output import validate_body_output, write_json


def create_fallback_body_output(
    output_dir: str | Path,
    *,
    job_id: str = "phase0-fallback",
    warnings: Iterable[str] | None = None,
) -> dict[str, object]:
    """Create the phase-0 body contract using a low-poly placeholder body."""

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)

    vertices, faces = _build_mannequin_mesh()
    write_mesh_glb(root / "body.glb", vertices, faces, name="FallbackBody")
    write_json(root / "landmarks.json", fallback_landmarks())
    write_json(root / "body_metadata.json", fallback_metadata(job_id, warnings or []))

    return validate_body_output(root)


def fallback_landmarks() -> dict[str, object]:
    return {
        "coordinate_system": "viewer",
        "scale_mode": "normalized",
        "points": {
            "neck": [0.0, 1.46, 0.0],
            "left_shoulder": [-0.28, 1.34, 0.0],
            "right_shoulder": [0.28, 1.34, 0.0],
            "chest_center": [0.0, 1.20, 0.0],
            "waist_center": [0.0, 0.96, 0.0],
            "hip_center": [0.0, 0.80, 0.0],
            "left_wrist": [-0.52, 0.78, 0.0],
            "right_wrist": [0.52, 0.78, 0.0],
            "left_knee": [-0.12, 0.42, 0.0],
            "right_knee": [0.12, 0.42, 0.0],
            "left_ankle": [-0.12, 0.06, 0.0],
            "right_ankle": [0.12, 0.06, 0.0],
        },
        "measurements_estimated": {
            "shoulder_width": 0.56,
            "torso_length": 0.50,
            "leg_length": 0.74,
            "hip_width": 0.34,
        },
    }


def fallback_metadata(
    job_id: str,
    warnings: Iterable[str],
) -> dict[str, object]:
    return {
        "job_id": job_id,
        "model_name": "development-fallback-body",
        "model_version": "phase0-low-poly-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_image_policy": "not_logged",
        "quality_score": 0.25,
        "warnings": [
            "development_fallback_not_user_reconstruction",
            *list(warnings),
        ],
    }


def _build_mannequin_mesh() -> tuple[list[Vec3], list[tuple[int, int, int]]]:
    vertices: list[Vec3] = []
    faces_out: list[tuple[int, int, int]] = []

    def add_box(center: Vec3, size: Vec3) -> None:
        base = len(vertices)
        cx, cy, cz = center
        sx, sy, sz = (size[0] / 2, size[1] / 2, size[2] / 2)
        vertices.extend(
            [
                (cx - sx, cy - sy, cz - sz),
                (cx + sx, cy - sy, cz - sz),
                (cx + sx, cy + sy, cz - sz),
                (cx - sx, cy + sy, cz - sz),
                (cx - sx, cy - sy, cz + sz),
                (cx + sx, cy - sy, cz + sz),
                (cx + sx, cy + sy, cz + sz),
                (cx - sx, cy + sy, cz + sz),
            ]
        )
        faces = [
            (0, 1, 2, 2, 3, 0),
            (4, 6, 5, 6, 4, 7),
            (0, 4, 5, 5, 1, 0),
            (3, 2, 6, 6, 7, 3),
            (1, 5, 6, 6, 2, 1),
            (0, 3, 7, 7, 4, 0),
        ]
        for face in faces:
            face_indices = [base + item for item in face]
            faces_out.extend(
                (face_indices[idx], face_indices[idx + 1], face_indices[idx + 2])
                for idx in range(0, len(face_indices), 3)
            )

    add_box((0.0, 1.68, 0.0), (0.20, 0.22, 0.18))  # head
    add_box((0.0, 1.12, 0.0), (0.46, 0.72, 0.18))  # torso
    add_box((-0.42, 1.04, 0.0), (0.12, 0.68, 0.12))  # left arm
    add_box((0.42, 1.04, 0.0), (0.12, 0.68, 0.12))  # right arm
    add_box((-0.13, 0.36, 0.0), (0.15, 0.72, 0.13))  # left leg
    add_box((0.13, 0.36, 0.0), (0.15, 0.72, 0.13))  # right leg

    return vertices, faces_out
