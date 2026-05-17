"""SAM-proportion fitting mannequin body derived from a body contract."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.contracts.body_output import validate_body_output, write_json
from backend.app.contracts.glb import Face, Vec3, write_mesh_glb
from backend.app.pipelines.garment_templates import read_glb_bounds
from backend.app.pipelines.hybrid_fitting import read_glb_percentiles


CANONICAL_HEIGHT = 1.8


def create_canonical_body_output(
    source_body_dir: str | Path,
    output_dir: str | Path,
    *,
    job_id: str = "canonical-sample-body",
) -> dict[str, Any]:
    """Create a smooth human-like fitting mannequin scaled from a source body."""

    source = validate_body_output(source_body_dir)
    dimensions = estimate_canonical_dimensions(source)
    vertices, faces = build_canonical_mannequin_mesh(dimensions)

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    write_mesh_glb(
        root / "body.glb",
        vertices,
        faces,
        name="SAMProportionFittingBody",
        base_color=(0.62, 0.61, 0.58, 1.0),
        roughness=0.88,
    )
    write_json(root / "landmarks.json", canonical_landmarks(dimensions))
    write_json(root / "body_metadata.json", canonical_metadata(source, dimensions, job_id))
    return validate_body_output(root)


def estimate_canonical_dimensions(source: dict[str, Any]) -> dict[str, float]:
    bounds = read_glb_bounds(source["body_glb"])
    percentiles = read_glb_percentiles(source["body_glb"])
    points = source["landmarks"]["points"]
    measurements = source["landmarks"].get("measurements_estimated", {})
    source_height = max(abs(bounds["size"][1]), 0.1)
    scale = CANONICAL_HEIGHT / source_height
    core_width = max(percentiles["x"]["p80"] - percentiles["x"]["p20"], 0.05)
    shoulder_distance = _distance(points["left_shoulder"], points["right_shoulder"])
    measured_hip = float(measurements.get("hip_width", 0.0))

    shoulder_width = _clamp(
        max(shoulder_distance * scale * 1.45, core_width * scale * 1.28, 0.46),
        0.44,
        0.58,
    )
    hip_width = _clamp(
        max(measured_hip * scale * 2.25, shoulder_width * 0.76, 0.36),
        0.35,
        shoulder_width * 0.96,
    )
    chest_width = _clamp(max(shoulder_width * 0.82, hip_width * 1.02), 0.39, shoulder_width * 0.92)
    waist_width = _clamp((chest_width + hip_width) * 0.45, 0.32, chest_width * 0.86)
    depth = _clamp(max(abs(bounds["size"][2]) * scale * 0.58, 0.22), 0.20, 0.28)

    return {
        "height": CANONICAL_HEIGHT,
        "shoulder_width": shoulder_width,
        "chest_width": chest_width,
        "waist_width": waist_width,
        "hip_width": hip_width,
        "depth": depth,
        "head_radius_x": 0.090,
        "head_radius_y": 0.122,
        "head_radius_z": 0.084,
        "neck_radius_x": 0.047,
        "neck_radius_z": 0.042,
        "upper_arm_radius": max(shoulder_width * 0.11, 0.046),
        "wrist_radius": 0.037,
        "thigh_radius": max(hip_width * 0.205, 0.068),
        "knee_radius": max(hip_width * 0.125, 0.046),
        "ankle_radius": 0.036,
    }


def build_canonical_mannequin_mesh(dimensions: dict[str, float]) -> tuple[list[Vec3], list[Face]]:
    vertices: list[Vec3] = []
    faces: list[Face] = []
    height = dimensions["height"]
    shoulder_width = dimensions["shoulder_width"]
    chest_width = dimensions["chest_width"]
    waist_width = dimensions["waist_width"]
    hip_width = dimensions["hip_width"]
    depth = dimensions["depth"]

    add_elliptical_shell(
        vertices,
        faces,
        rings=[
            (height * 0.435, hip_width * 0.42, depth * 0.44),
            (height * 0.475, hip_width * 0.53, depth * 0.56),
            (height * 0.545, max(hip_width * 0.50, waist_width * 0.54), depth * 0.54),
            (height * 0.610, waist_width * 0.50, depth * 0.49),
            (height * 0.685, chest_width * 0.49, depth * 0.53),
            (height * 0.745, chest_width * 0.53, depth * 0.55),
            (height * 0.790, shoulder_width * 0.50, depth * 0.49),
            (height * 0.825, shoulder_width * 0.29, depth * 0.34),
        ],
        center_x=0.0,
        center_z=0.0,
        segments=56,
    )
    add_tapered_tube(
        vertices,
        faces,
        start=(0.0, height * 0.805, 0.0),
        end=(0.0, height * 0.865, 0.0),
        radius_start=(dimensions["neck_radius_x"], dimensions["neck_radius_z"]),
        radius_end=(dimensions["neck_radius_x"] * 0.88, dimensions["neck_radius_z"] * 0.88),
        segments=36,
    )
    add_ellipsoid(
        vertices,
        faces,
        center=(0.0, height * 0.92, 0.0),
        radii=(
            dimensions["head_radius_x"],
            dimensions["head_radius_y"],
            dimensions["head_radius_z"],
        ),
        lat_segments=14,
        lon_segments=36,
    )
    add_ellipsoid(
        vertices,
        faces,
        center=(0.0, height * 0.925, dimensions["head_radius_z"] * 0.84),
        radii=(0.020, 0.030, 0.032),
        lat_segments=6,
        lon_segments=16,
    )
    for side in (-1, 1):
        add_ellipsoid(
            vertices,
            faces,
            center=(side * dimensions["head_radius_x"] * 0.94, height * 0.922, -0.004),
            radii=(0.014, 0.026, 0.010),
            lat_segments=6,
            lon_segments=14,
        )
    add_ellipsoid(
        vertices,
        faces,
        center=(0.0, height * 0.905, dimensions["head_radius_z"] * 0.72),
        radii=(0.034, 0.010, 0.006),
        lat_segments=4,
        lon_segments=16,
    )

    upper_arm_radius = dimensions["upper_arm_radius"]
    wrist_radius = dimensions["wrist_radius"]
    for side in (-1, 1):
        shoulder = (side * shoulder_width * 0.51, height * 0.770, depth * 0.015)
        elbow = (side * shoulder_width * 0.58, height * 0.575, depth * 0.060)
        wrist = (side * shoulder_width * 0.54, height * 0.360, depth * 0.050)
        add_tapered_tube_chain(
            vertices,
            faces,
            rings=[
                (shoulder, (upper_arm_radius * 1.06, upper_arm_radius * 0.96)),
                (
                    (side * shoulder_width * 0.56, height * 0.675, depth * 0.045),
                    (upper_arm_radius * 1.00, upper_arm_radius * 0.92),
                ),
                (elbow, (upper_arm_radius * 0.82, upper_arm_radius * 0.78)),
                (
                    (side * shoulder_width * 0.57, height * 0.465, depth * 0.058),
                    (upper_arm_radius * 0.70, upper_arm_radius * 0.64),
                ),
                (wrist, (wrist_radius, wrist_radius * 0.90)),
            ],
            segments=44,
        )
        add_ellipsoid(
            vertices,
            faces,
            center=(side * shoulder_width * 0.54, height * 0.334, depth * 0.058),
            radii=(wrist_radius * 0.95, wrist_radius * 1.36, wrist_radius * 0.84),
            lat_segments=6,
            lon_segments=18,
        )

    thigh_radius = dimensions["thigh_radius"]
    knee_radius = dimensions["knee_radius"]
    ankle_radius = dimensions["ankle_radius"]
    for side in (-1, 1):
        hip = (side * hip_width * 0.235, height * 0.445, 0.0)
        knee = (side * hip_width * 0.185, height * 0.235, depth * 0.012)
        ankle = (side * hip_width * 0.155, height * 0.055, depth * 0.008)
        add_tapered_tube_chain(
            vertices,
            faces,
            rings=[
                (hip, (thigh_radius, thigh_radius * 0.92)),
                (
                    (side * hip_width * 0.215, height * 0.345, depth * 0.013),
                    (thigh_radius * 0.86, thigh_radius * 0.82),
                ),
                (knee, (knee_radius, knee_radius * 0.90)),
                (
                    (side * hip_width * 0.170, height * 0.145, depth * 0.013),
                    (knee_radius * 0.86, knee_radius * 0.80),
                ),
                (ankle, (ankle_radius, ankle_radius * 0.84)),
            ],
            segments=44,
        )
        add_ellipsoid(
            vertices,
            faces,
            center=(side * hip_width * 0.17, height * 0.028, depth * 0.09),
            radii=(ankle_radius * 1.35, ankle_radius * 0.55, ankle_radius * 2.0),
            lat_segments=6,
            lon_segments=18,
        )

    return vertices, faces


def canonical_landmarks(dimensions: dict[str, float]) -> dict[str, Any]:
    height = dimensions["height"]
    shoulder = dimensions["shoulder_width"] / 2
    hip = dimensions["hip_width"] / 2
    return {
        "coordinate_system": "viewer",
        "scale_mode": "canonical_from_source_body",
        "points": {
            "neck": [0.0, height * 0.82, 0.0],
            "left_shoulder": [shoulder, height * 0.78, 0.0],
            "right_shoulder": [-shoulder, height * 0.78, 0.0],
            "chest_center": [0.0, height * 0.70, 0.0],
            "waist_center": [0.0, height * 0.58, 0.0],
            "hip_center": [0.0, height * 0.455, 0.0],
            "left_wrist": [shoulder * 1.08, height * 0.360, dimensions["depth"] * 0.050],
            "right_wrist": [-shoulder * 1.08, height * 0.360, dimensions["depth"] * 0.050],
            "left_knee": [hip * 0.37, height * 0.235, dimensions["depth"] * 0.012],
            "right_knee": [-hip * 0.37, height * 0.235, dimensions["depth"] * 0.012],
            "left_ankle": [hip * 0.31, height * 0.055, dimensions["depth"] * 0.008],
            "right_ankle": [-hip * 0.31, height * 0.055, dimensions["depth"] * 0.008],
        },
        "measurements_estimated": {
            "shoulder_width": dimensions["shoulder_width"],
            "torso_length": height * 0.365,
            "leg_length": height * 0.415,
            "hip_width": dimensions["hip_width"],
        },
    }


def canonical_metadata(
    source: dict[str, Any],
    dimensions: dict[str, float],
    job_id: str,
) -> dict[str, Any]:
    source_metadata = source["metadata"]
    source_warnings = source_metadata.get("warnings", [])
    return {
        "job_id": job_id,
        "model_name": "canonical-body-from-sam-proportions",
        "model_version": "sam-proportion-smooth-mannequin-v2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_image_policy": "not_logged",
        "source_body_model": source_metadata.get("model_name", "unknown"),
        "source_body_job_id": source_metadata.get("job_id", ""),
        "scale_mode": "canonical_from_source_body",
        "quality_score": min(float(source_metadata.get("quality_score", 0.5)), 0.7),
        "canonical_dimensions": dimensions,
        "warnings": [
            "sam_proportions_transferred_to_smooth_fitting_mannequin",
            *source_warnings,
        ],
    }


def add_elliptical_shell(
    vertices: list[Vec3],
    faces: list[Face],
    *,
    rings: list[tuple[float, float, float]],
    center_x: float,
    center_z: float,
    segments: int = 32,
) -> None:
    base = len(vertices)
    for y_value, radius_x, radius_z in rings:
        for index in range(segments):
            angle = 2 * math.pi * index / segments
            vertices.append(
                (
                    center_x + math.cos(angle) * radius_x,
                    y_value,
                    center_z + math.sin(angle) * radius_z,
                )
            )

    for ring_index in range(len(rings) - 1):
        for index in range(segments):
            next_index = (index + 1) % segments
            a = base + ring_index * segments + index
            b = base + ring_index * segments + next_index
            c = base + (ring_index + 1) * segments + next_index
            d = base + (ring_index + 1) * segments + index
            faces.append((a, b, c))
            faces.append((c, d, a))

    bottom_center = len(vertices)
    vertices.append((center_x, rings[0][0], center_z))
    top_center = len(vertices)
    vertices.append((center_x, rings[-1][0], center_z))
    bottom_base = base
    top_base = base + (len(rings) - 1) * segments
    for index in range(segments):
        next_index = (index + 1) % segments
        faces.append((bottom_center, bottom_base + next_index, bottom_base + index))
        faces.append((top_center, top_base + index, top_base + next_index))


def add_tapered_tube(
    vertices: list[Vec3],
    faces: list[Face],
    *,
    start: Vec3,
    end: Vec3,
    radius_start: tuple[float, float],
    radius_end: tuple[float, float],
    segments: int = 24,
) -> None:
    axis = _normalize((end[0] - start[0], end[1] - start[1], end[2] - start[2]))
    reference = (0.0, 1.0, 0.0)
    if abs(_dot(axis, reference)) > 0.92:
        reference = (0.0, 0.0, 1.0)
    normal_a = _normalize(_cross(axis, reference))
    normal_b = _normalize(_cross(axis, normal_a))

    base = len(vertices)
    for ring_index, (center, radii) in enumerate(((start, radius_start), (end, radius_end))):
        for index in range(segments):
            angle = 2 * math.pi * index / segments
            offset = (
                normal_a[0] * math.cos(angle) * radii[0] + normal_b[0] * math.sin(angle) * radii[1],
                normal_a[1] * math.cos(angle) * radii[0] + normal_b[1] * math.sin(angle) * radii[1],
                normal_a[2] * math.cos(angle) * radii[0] + normal_b[2] * math.sin(angle) * radii[1],
            )
            vertices.append((center[0] + offset[0], center[1] + offset[1], center[2] + offset[2]))

    start_center = len(vertices)
    vertices.append(start)
    end_center = len(vertices)
    vertices.append(end)
    for index in range(segments):
        next_index = (index + 1) % segments
        a = base + index
        b = base + next_index
        c = base + segments + next_index
        d = base + segments + index
        faces.append((a, b, c))
        faces.append((c, d, a))
        faces.append((start_center, b, a))
        faces.append((end_center, d, c))


def add_tapered_tube_chain(
    vertices: list[Vec3],
    faces: list[Face],
    *,
    rings: list[tuple[Vec3, tuple[float, float]]],
    segments: int = 32,
) -> None:
    """Create one smooth limb tube through multiple control rings."""

    if len(rings) < 2:
        raise ValueError("tube chain needs at least two rings")

    base = len(vertices)
    for ring_index, (center, radii) in enumerate(rings):
        previous_center = rings[max(ring_index - 1, 0)][0]
        next_center = rings[min(ring_index + 1, len(rings) - 1)][0]
        tangent = _normalize(
            (
                next_center[0] - previous_center[0],
                next_center[1] - previous_center[1],
                next_center[2] - previous_center[2],
            )
        )
        reference = (0.0, 1.0, 0.0)
        if abs(_dot(tangent, reference)) > 0.92:
            reference = (0.0, 0.0, 1.0)
        normal_a = _normalize(_cross(tangent, reference))
        normal_b = _normalize(_cross(tangent, normal_a))
        for index in range(segments):
            angle = 2 * math.pi * index / segments
            offset = (
                normal_a[0] * math.cos(angle) * radii[0] + normal_b[0] * math.sin(angle) * radii[1],
                normal_a[1] * math.cos(angle) * radii[0] + normal_b[1] * math.sin(angle) * radii[1],
                normal_a[2] * math.cos(angle) * radii[0] + normal_b[2] * math.sin(angle) * radii[1],
            )
            vertices.append((center[0] + offset[0], center[1] + offset[1], center[2] + offset[2]))

    for ring_index in range(len(rings) - 1):
        for index in range(segments):
            next_index = (index + 1) % segments
            a = base + ring_index * segments + index
            b = base + ring_index * segments + next_index
            c = base + (ring_index + 1) * segments + next_index
            d = base + (ring_index + 1) * segments + index
            faces.append((a, b, c))
            faces.append((c, d, a))

    start_center = len(vertices)
    vertices.append(rings[0][0])
    end_center = len(vertices)
    vertices.append(rings[-1][0])
    start_base = base
    end_base = base + (len(rings) - 1) * segments
    for index in range(segments):
        next_index = (index + 1) % segments
        faces.append((start_center, start_base + next_index, start_base + index))
        faces.append((end_center, end_base + index, end_base + next_index))


def add_tapered_cylinder(
    vertices: list[Vec3],
    faces: list[Face],
    *,
    y_bottom: float,
    y_top: float,
    rx_bottom: float,
    rz_bottom: float,
    rx_top: float,
    rz_top: float,
    center_x: float = 0.0,
    center_z: float = 0.0,
    segments: int = 24,
) -> None:
    base = len(vertices)
    for ring, y_value in enumerate((y_bottom, y_top)):
        rx = rx_bottom if ring == 0 else rx_top
        rz = rz_bottom if ring == 0 else rz_top
        for index in range(segments):
            angle = 2 * math.pi * index / segments
            vertices.append(
                (
                    center_x + math.cos(angle) * rx,
                    y_value,
                    center_z + math.sin(angle) * rz,
                )
            )
    bottom_center = len(vertices)
    vertices.append((center_x, y_bottom, center_z))
    top_center = len(vertices)
    vertices.append((center_x, y_top, center_z))

    for index in range(segments):
        next_index = (index + 1) % segments
        bottom_a = base + index
        bottom_b = base + next_index
        top_a = base + segments + index
        top_b = base + segments + next_index
        faces.append((bottom_a, bottom_b, top_b))
        faces.append((top_b, top_a, bottom_a))
        faces.append((bottom_center, bottom_a, bottom_b))
        faces.append((top_center, top_b, top_a))


def add_ellipsoid(
    vertices: list[Vec3],
    faces: list[Face],
    *,
    center: Vec3,
    radii: Vec3,
    lat_segments: int = 10,
    lon_segments: int = 24,
) -> None:
    base = len(vertices)
    cx, cy, cz = center
    rx, ry, rz = radii
    for lat in range(lat_segments + 1):
        theta = math.pi * lat / lat_segments
        sin_theta = math.sin(theta)
        cos_theta = math.cos(theta)
        for lon in range(lon_segments):
            phi = 2 * math.pi * lon / lon_segments
            vertices.append(
                (
                    cx + rx * sin_theta * math.cos(phi),
                    cy + ry * cos_theta,
                    cz + rz * sin_theta * math.sin(phi),
                )
            )
    for lat in range(lat_segments):
        for lon in range(lon_segments):
            next_lon = (lon + 1) % lon_segments
            a = base + lat * lon_segments + lon
            b = base + lat * lon_segments + next_lon
            c = base + (lat + 1) * lon_segments + next_lon
            d = base + (lat + 1) * lon_segments + lon
            faces.append((a, b, c))
            faces.append((c, d, a))


def _distance(a: list[float], b: list[float]) -> float:
    return math.sqrt(
        (a[0] - b[0]) * (a[0] - b[0])
        + (a[1] - b[1]) * (a[1] - b[1])
        + (a[2] - b[2]) * (a[2] - b[2])
    )


def _vector_length(vector: Vec3) -> float:
    return math.sqrt(vector[0] * vector[0] + vector[1] * vector[1] + vector[2] * vector[2])


def _normalize(vector: Vec3) -> Vec3:
    length = _vector_length(vector)
    if length <= 1e-8:
        return (0.0, 1.0, 0.0)
    return (vector[0] / length, vector[1] / length, vector[2] / length)


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))
