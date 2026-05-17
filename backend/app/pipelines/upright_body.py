"""Reorient a SAM body contract into a viewer-upright body contract."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.contracts.body_output import validate_body_output, write_json
from backend.app.contracts.glb import Face, Vec3, write_mesh_glb


def create_upright_body_output(
    source_body_dir: str | Path,
    output_dir: str | Path,
    *,
    job_id: str = "upright-body",
) -> dict[str, Any]:
    """Convert a source body mesh/landmarks to a stable Y-up viewer contract."""

    source = validate_body_output(source_body_dir)
    vertices, faces = read_body_mesh(source["body_glb"])
    landmarks = source["landmarks"]
    transform = build_upright_transform(landmarks["points"], vertices)
    transformed_vertices = [transform_vertex(vertex, transform) for vertex in vertices]
    transformed_landmarks = transform_landmarks(landmarks, transform)

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    write_mesh_glb(
        root / "body.glb",
        transformed_vertices,
        faces,
        name="UprightSAMBody",
        base_color=(0.78, 0.76, 0.72, 1.0),
        roughness=0.82,
        double_sided=True,
    )
    write_json(root / "landmarks.json", transformed_landmarks)
    write_json(root / "body_metadata.json", upright_metadata(source, transform, job_id))
    return validate_body_output(root)


def read_body_mesh(body_glb: str | Path) -> tuple[list[Vec3], list[Face]]:
    import numpy as np
    import trimesh

    loaded = trimesh.load(body_glb)
    geometries = list(loaded.geometry.values()) if hasattr(loaded, "geometry") else [loaded]
    vertices: list[Vec3] = []
    faces: list[Face] = []
    for geometry in geometries:
        if not hasattr(geometry, "vertices") or not hasattr(geometry, "faces"):
            continue
        base = len(vertices)
        vertices.extend(tuple(map(float, vertex[:3])) for vertex in np.asarray(geometry.vertices))
        faces.extend(tuple(int(base + index) for index in face[:3]) for face in np.asarray(geometry.faces))
    if not vertices or not faces:
        raise ValueError(f"No mesh vertices/faces found in {body_glb}")
    return vertices, faces


def build_upright_transform(
    points: dict[str, list[float]],
    vertices: list[Vec3],
) -> dict[str, float | bool]:
    neck_y = float(points["neck"][1])
    ankle_y = (float(points["left_ankle"][1]) + float(points["right_ankle"][1])) / 2
    flip_y = ankle_y > neck_y
    transformed_y_values = [(-vertex[1] if flip_y else vertex[1]) for vertex in vertices]
    y_offset = -min(transformed_y_values)
    return {
        "flip_y": flip_y,
        "y_offset": y_offset,
    }


def transform_vertex(vertex: Vec3, transform: dict[str, float | bool]) -> Vec3:
    y_value = -vertex[1] if transform["flip_y"] else vertex[1]
    return (vertex[0], y_value + float(transform["y_offset"]), vertex[2])


def transform_landmarks(
    landmarks: dict[str, Any],
    transform: dict[str, float | bool],
) -> dict[str, Any]:
    points = {
        name: list(transform_vertex(tuple(map(float, value[:3])), transform))
        for name, value in landmarks["points"].items()
    }
    output = dict(landmarks)
    output["scale_mode"] = "upright_from_source_body"
    output["points"] = points
    return output


def upright_metadata(
    source: dict[str, Any],
    transform: dict[str, float | bool],
    job_id: str,
) -> dict[str, Any]:
    source_metadata = source["metadata"]
    source_warnings = source_metadata.get("warnings", [])
    warnings = [
        "source_sam_body_reoriented_for_viewer_y_up",
        *source_warnings,
    ]
    return {
        "job_id": job_id,
        "model_name": "sam-3d-body-upright-viewer",
        "model_version": "upright-transform-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_image_policy": "not_logged",
        "source_body_model": source_metadata.get("model_name", "unknown"),
        "source_body_job_id": source_metadata.get("job_id", ""),
        "scale_mode": "upright_from_source_body",
        "quality_score": float(source_metadata.get("quality_score", 0.5)),
        "transform": transform,
        "warnings": warnings,
    }
