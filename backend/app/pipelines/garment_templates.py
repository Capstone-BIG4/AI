"""Procedural MVP garment templates and sample body placement."""

from __future__ import annotations

import json
import math
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.app.contracts.body_output import write_json
from backend.app.contracts.garment_template import validate_garment_template
from backend.app.contracts.glb import Face, Vec2, Vec3, write_mesh_glb
from backend.app.pipelines.garment_textures import draw_uv_layout


TSHIRT_UV_REGIONS = {
    "front": {"u_min": 0.04, "v_min": 0.04, "u_max": 0.48, "v_max": 0.64},
    "back": {"u_min": 0.52, "v_min": 0.04, "u_max": 0.96, "v_max": 0.64},
    "left_sleeve": {"u_min": 0.04, "v_min": 0.70, "u_max": 0.48, "v_max": 0.84},
    "right_sleeve": {"u_min": 0.52, "v_min": 0.70, "u_max": 0.96, "v_max": 0.84},
    "side": {"u_min": 0.04, "v_min": 0.88, "u_max": 0.96, "v_max": 0.96},
}

PANTS_UV_REGIONS = {
    "front": {"u_min": 0.04, "v_min": 0.04, "u_max": 0.48, "v_max": 0.96},
    "back": {"u_min": 0.52, "v_min": 0.04, "u_max": 0.96, "v_max": 0.96},
    "left_leg": {"u_min": 0.04, "v_min": 0.04, "u_max": 0.25, "v_max": 0.96},
    "right_leg": {"u_min": 0.27, "v_min": 0.04, "u_max": 0.48, "v_max": 0.96},
    "side": {"u_min": 0.04, "v_min": 0.88, "u_max": 0.96, "v_max": 0.96},
}


@dataclass
class MeshDraft:
    vertices: list[Vec3] = field(default_factory=list)
    texcoords: list[Vec2] = field(default_factory=list)
    faces: list[Face] = field(default_factory=list)
    vertex_groups: dict[str, list[int]] = field(default_factory=dict)

    def add_quad(
        self,
        points: tuple[Vec3, Vec3, Vec3, Vec3],
        region: dict[str, float],
        *,
        group: str,
        reverse: bool = False,
    ) -> list[int]:
        base = len(self.vertices)
        self.vertices.extend(points)
        self.texcoords.extend(_quad_uvs(region))
        indices = [base, base + 1, base + 2, base + 3]
        if reverse:
            self.faces.extend([(indices[0], indices[2], indices[1]), (indices[2], indices[0], indices[3])])
        else:
            self.faces.extend([(indices[0], indices[1], indices[2]), (indices[2], indices[3], indices[0])])
        self.vertex_groups.setdefault(group, []).extend(indices)
        return indices


def build_template_assets(
    category: str,
    output_dir: str | Path,
    *,
    texture_uri: str | None = "preview_texture.png",
) -> dict[str, Any]:
    """Generate one MVP garment template and validate its contract."""

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    if category == "tshirt":
        mesh = build_tshirt_mesh(
            center=(0.0, 0.0, 0.0),
            top_y=0.88,
            hem_y=0.05,
            shoulder_width=0.62,
            torso_width=0.46,
            sleeve_span=1.06,
            z_front=0.06,
            z_back=-0.06,
        )
        metadata = tshirt_metadata(mesh.vertex_groups)
        uv_regions = TSHIRT_UV_REGIONS
        base_color = (0.92, 0.92, 0.9, 1.0)
    elif category == "pants":
        mesh = build_pants_mesh(
            center=(0.0, 0.0, 0.0),
            waist_y=0.98,
            hip_y=0.74,
            hem_y=0.02,
            waist_width=0.46,
            hip_width=0.58,
            hem_width=0.18,
            leg_gap=0.06,
            z_front=0.055,
            z_back=-0.055,
        )
        metadata = pants_metadata(mesh.vertex_groups)
        uv_regions = PANTS_UV_REGIONS
        base_color = (0.42, 0.45, 0.48, 1.0)
    else:
        raise ValueError(f"Unknown garment category: {category}")

    draw_uv_layout(root / "uv-layout.png", uv_regions)
    write_mesh_glb(
        root / f"{category}.glb",
        mesh.vertices,
        mesh.faces,
        name=f"{category.title()}Template",
        base_color=base_color,
        roughness=0.86,
        texcoords=mesh.texcoords,
        texture_uri=texture_uri,
        double_sided=True,
    )
    write_json(root / "anchors.json", metadata)
    return validate_garment_template(root, category=category)


def build_fitted_sample_garments(
    *,
    body_glb: str | Path,
    scene_dir: str | Path,
    top_atlas: str | Path,
    pants_atlas: str | Path,
) -> dict[str, Any]:
    """Place MVP garment meshes around a body bounding box for viewer smoke tests."""

    bounds = read_glb_bounds(body_glb)
    root = Path(scene_dir)
    root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(top_atlas, root / "top_texture_atlas.png")
    shutil.copy2(pants_atlas, root / "pants_texture_atlas.png")

    min_x, min_y, min_z = bounds["min"]
    max_x, max_y, max_z = bounds["max"]
    size_x = max_x - min_x
    size_y = max_y - min_y
    size_z = max_z - min_z
    center_x = (min_x + max_x) / 2
    center_z = (min_z + max_z) / 2
    z_front = max_z + max(size_z * 0.05, 0.025)
    z_back = min_z - max(size_z * 0.05, 0.025)

    shirt = build_tshirt_mesh(
        center=(center_x, 0.0, center_z),
        top_y=max_y - size_y * 0.23,
        hem_y=min_y + size_y * 0.43,
        shoulder_width=max(size_x * 0.46, 0.38),
        torso_width=max(size_x * 0.38, 0.32),
        sleeve_span=max(size_x * 0.70, 0.58),
        z_front=z_front,
        z_back=z_back,
    )
    pants = build_pants_mesh(
        center=(center_x, 0.0, center_z),
        waist_y=min_y + size_y * 0.44,
        hip_y=min_y + size_y * 0.34,
        hem_y=min_y + size_y * 0.04,
        waist_width=max(size_x * 0.34, 0.30),
        hip_width=max(size_x * 0.42, 0.36),
        hem_width=max(size_x * 0.16, 0.13),
        leg_gap=max(size_x * 0.07, 0.05),
        z_front=z_front,
        z_back=z_back,
    )

    write_mesh_glb(
        root / "top.glb",
        shirt.vertices,
        shirt.faces,
        name="SampleFittedTop",
        base_color=(1.0, 1.0, 1.0, 1.0),
        roughness=0.84,
        texcoords=shirt.texcoords,
        texture_uri="top_texture_atlas.png",
        double_sided=True,
    )
    write_mesh_glb(
        root / "pants.glb",
        pants.vertices,
        pants.faces,
        name="SampleFittedPants",
        base_color=(1.0, 1.0, 1.0, 1.0),
        roughness=0.72,
        texcoords=pants.texcoords,
        texture_uri="pants_texture_atlas.png",
        double_sided=True,
    )

    report = {
        "body_glb": str(body_glb),
        "body_bounds": bounds,
        "method": "bbox_template_placement",
        "top": {
            "shoulder_scale": round(max(size_x * 0.46, 0.38) / 0.62, 3),
            "torso_scale": round(max(size_x * 0.38, 0.32) / 0.46, 3),
            "length_scale": round((size_y * 0.34) / 0.83, 3),
            "collision_warnings": ["bbox_only_no_body_surface_collision"],
        },
        "pants": {
            "waist_scale": round(max(size_x * 0.34, 0.30) / 0.46, 3),
            "hip_scale": round(max(size_x * 0.42, 0.36) / 0.58, 3),
            "length_scale": round((size_y * 0.40) / 0.96, 3),
            "collision_warnings": ["bbox_only_no_body_surface_collision"],
        },
    }
    with (root / "fitting_report.json").open("w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
        file.write("\n")
    return report


def build_tshirt_mesh(
    *,
    center: Vec3,
    top_y: float,
    hem_y: float,
    shoulder_width: float,
    torso_width: float,
    sleeve_span: float,
    z_front: float,
    z_back: float,
) -> MeshDraft:
    cx, _, cz = center
    mesh = MeshDraft()
    shoulder_y = top_y - (top_y - hem_y) * 0.12
    sleeve_bottom_y = top_y - (top_y - hem_y) * 0.34
    sleeve_top_y = top_y - (top_y - hem_y) * 0.04
    front = TSHIRT_UV_REGIONS["front"]
    back = TSHIRT_UV_REGIONS["back"]
    left_sleeve = TSHIRT_UV_REGIONS["left_sleeve"]
    right_sleeve = TSHIRT_UV_REGIONS["right_sleeve"]
    side = TSHIRT_UV_REGIONS["side"]

    half_shoulder = shoulder_width / 2
    half_torso = torso_width / 2
    half_sleeve = sleeve_span / 2
    front_z = z_front
    back_z = z_back

    front_indices = mesh.add_quad(
        (
            (cx - half_torso, hem_y, front_z),
            (cx + half_torso, hem_y, front_z),
            (cx + half_shoulder, shoulder_y, front_z),
            (cx - half_shoulder, shoulder_y, front_z),
        ),
        front,
        group="torso",
    )
    back_indices = mesh.add_quad(
        (
            (cx - half_torso, hem_y, back_z),
            (cx - half_shoulder, shoulder_y, back_z),
            (cx + half_shoulder, shoulder_y, back_z),
            (cx + half_torso, hem_y, back_z),
        ),
        back,
        group="torso",
        reverse=True,
    )
    mesh.add_quad(
        (
            (cx - half_shoulder, sleeve_top_y, front_z),
            (cx - half_torso, sleeve_bottom_y, front_z),
            (cx - half_sleeve, sleeve_bottom_y, front_z),
            (cx - half_sleeve, sleeve_top_y, front_z),
        ),
        left_sleeve,
        group="left_sleeve",
    )
    mesh.add_quad(
        (
            (cx + half_torso, sleeve_bottom_y, front_z),
            (cx + half_shoulder, sleeve_top_y, front_z),
            (cx + half_sleeve, sleeve_top_y, front_z),
            (cx + half_sleeve, sleeve_bottom_y, front_z),
        ),
        right_sleeve,
        group="right_sleeve",
    )
    mesh.add_quad(
        (
            (cx - half_torso, hem_y, front_z),
            (cx - half_torso, hem_y, back_z),
            (cx - half_shoulder, shoulder_y, back_z),
            (cx - half_shoulder, shoulder_y, front_z),
        ),
        side,
        group="torso",
    )
    mesh.add_quad(
        (
            (cx + half_torso, hem_y, front_z),
            (cx + half_shoulder, shoulder_y, front_z),
            (cx + half_shoulder, shoulder_y, back_z),
            (cx + half_torso, hem_y, back_z),
        ),
        side,
        group="torso",
    )
    mesh.vertex_groups["shoulders"] = sorted(set(front_indices[2:] + back_indices[1:3]))
    for group in ("torso", "left_sleeve", "right_sleeve", "shoulders"):
        mesh.vertex_groups[group] = sorted(set(mesh.vertex_groups[group]))
    return mesh


def build_pants_mesh(
    *,
    center: Vec3,
    waist_y: float,
    hip_y: float,
    hem_y: float,
    waist_width: float,
    hip_width: float,
    hem_width: float,
    leg_gap: float,
    z_front: float,
    z_back: float,
) -> MeshDraft:
    cx, _, _ = center
    mesh = MeshDraft()
    front = PANTS_UV_REGIONS["front"]
    back = PANTS_UV_REGIONS["back"]
    side = PANTS_UV_REGIONS["side"]
    half_waist = waist_width / 2
    half_hip = hip_width / 2
    half_gap = leg_gap / 2
    half_hem = hem_width / 2

    left_outer_hip = cx - half_hip
    left_inner_hip = cx - half_gap
    left_outer_hem = cx - half_gap - hem_width
    left_inner_hem = cx - half_gap
    right_inner_hip = cx + half_gap
    right_outer_hip = cx + half_hip
    right_inner_hem = cx + half_gap
    right_outer_hem = cx + half_gap + hem_width

    waist_group: list[int] = []
    hip_group: list[int] = []
    for z_value, region, reverse in ((z_front, front, False), (z_back, back, True)):
        left = mesh.add_quad(
            (
                (left_outer_hem, hem_y, z_value),
                (left_inner_hem, hem_y, z_value),
                (left_inner_hip, hip_y, z_value),
                (cx - half_waist, waist_y, z_value),
            ),
            region,
            group="left_leg",
            reverse=reverse,
        )
        right = mesh.add_quad(
            (
                (right_inner_hem, hem_y, z_value),
                (right_outer_hem, hem_y, z_value),
                (cx + half_waist, waist_y, z_value),
                (right_outer_hip, hip_y, z_value),
            ),
            region,
            group="right_leg",
            reverse=reverse,
        )
        waist_group.extend([left[3], right[2]])
        hip_group.extend([left[2], right[3]])

    mesh.add_quad(
        (
            (left_outer_hem, hem_y, z_front),
            (left_outer_hem, hem_y, z_back),
            (left_outer_hip, hip_y, z_back),
            (left_outer_hip, hip_y, z_front),
        ),
        side,
        group="left_leg",
    )
    mesh.add_quad(
        (
            (right_outer_hem, hem_y, z_front),
            (right_outer_hip, hip_y, z_front),
            (right_outer_hip, hip_y, z_back),
            (right_outer_hem, hem_y, z_back),
        ),
        side,
        group="right_leg",
    )
    mesh.vertex_groups["waist"] = sorted(set(waist_group))
    mesh.vertex_groups["hip"] = sorted(set(hip_group))
    for group in ("waist", "hip", "left_leg", "right_leg"):
        mesh.vertex_groups[group] = sorted(set(mesh.vertex_groups[group]))
    return mesh


def build_fitted_tshirt_shell_mesh(
    *,
    center: Vec3,
    top_y: float,
    shoulder_y: float,
    hem_y: float,
    shoulder_width: float,
    torso_width: float,
    z_front: float,
    z_back: float,
    left_shoulder: Vec3,
    right_shoulder: Vec3,
    left_wrist: Vec3,
    right_wrist: Vec3,
    sleeve_radius: float,
    sleeve_length_ratio: float = 0.38,
    vertical_sign: int = -1,
) -> MeshDraft:
    """Build a fitted shirt as a rounded torso shell plus short sleeve tubes."""

    mesh = MeshDraft()
    cx, _, cz = center
    depth_radius = max((z_front - z_back) / 2, 0.05)
    length = abs(shoulder_y - hem_y)
    torso_rings = [
        (hem_y - length * 0.018, torso_width * 0.45, depth_radius * 0.70),
        (hem_y, torso_width * 0.46, depth_radius * 0.72),
        (_lerp(hem_y, shoulder_y, 0.28), torso_width * 0.45, depth_radius * 0.78),
        (_lerp(hem_y, shoulder_y, 0.62), max(torso_width * 0.46, shoulder_width * 0.38), depth_radius * 0.82),
        (shoulder_y, shoulder_width * 0.43, depth_radius * 0.78),
        (top_y, shoulder_width * 0.17, depth_radius * 0.38),
    ]
    _add_elliptical_shell(
        mesh,
        center_x=cx,
        center_z=cz,
        rings=torso_rings,
        region=TSHIRT_UV_REGIONS["front"],
        back_region=TSHIRT_UV_REGIONS["back"],
        group="torso",
        segments=40,
    )

    for side, shoulder, wrist, region, group in (
        (1, left_shoulder, left_wrist, TSHIRT_UV_REGIONS["left_sleeve"], "left_sleeve"),
        (-1, right_shoulder, right_wrist, TSHIRT_UV_REGIONS["right_sleeve"], "right_sleeve"),
    ):
        sleeve_start = (
            shoulder[0] + side * sleeve_radius * 0.42,
            shoulder[1] + vertical_sign * abs(shoulder_y - top_y) * 0.10,
            shoulder[2],
        )
        body_direction = (
            wrist[0] - shoulder[0],
            wrist[1] - shoulder[1],
            wrist[2] - shoulder[2],
        )
        direction = (
            side * max(abs(body_direction[0]), shoulder_width * 0.18),
            vertical_sign * max(abs(body_direction[1]) * 0.38, shoulder_width * 0.08),
            body_direction[2] * 0.30,
        )
        direction_length = _vector_length(direction)
        if direction_length < 0.05:
            direction = (side * 1.0, -0.15, 0.0)
            direction_length = _vector_length(direction)
        unit = (
            direction[0] / direction_length,
            direction[1] / direction_length,
            direction[2] / direction_length,
        )
        sleeve_length = max(min(direction_length * sleeve_length_ratio, shoulder_width * 0.38), shoulder_width * 0.18)
        sleeve_end = (
            sleeve_start[0] + unit[0] * sleeve_length,
            sleeve_start[1] + unit[1] * sleeve_length,
            sleeve_start[2] + unit[2] * sleeve_length,
        )
        visual_radius = min(sleeve_radius, max(shoulder_width * 0.18, 0.074))
        _add_oriented_tube(
            mesh,
            start=sleeve_start,
            end=sleeve_end,
            radius_start=visual_radius,
            radius_end=visual_radius * 0.92,
            region=region,
            group=group,
            segments=20,
        )

    mesh.vertex_groups["shoulders"] = sorted(set(mesh.vertex_groups.get("torso", [])))
    for group in ("torso", "left_sleeve", "right_sleeve", "shoulders"):
        mesh.vertex_groups[group] = sorted(set(mesh.vertex_groups.get(group, [])))
    return mesh


def build_fitted_pants_shell_mesh(
    *,
    center: Vec3,
    waist_y: float,
    hip_y: float,
    hem_y: float,
    waist_width: float,
    hip_width: float,
    hem_width: float,
    leg_gap: float,
    z_front: float,
    z_back: float,
    left_leg_center_x: float | None = None,
    right_leg_center_x: float | None = None,
) -> MeshDraft:
    """Build fitted pants as a rounded hip shell and two leg shells."""

    mesh = MeshDraft()
    cx, _, cz = center
    depth_radius = max((z_front - z_back) / 2, 0.05)
    crotch_y = hip_y - abs(waist_y - hip_y) * 0.66
    _add_elliptical_shell(
        mesh,
        center_x=cx,
        center_z=cz,
        rings=[
            (hip_y, hip_width * 0.34, depth_radius * 0.58),
            ((hip_y + waist_y) / 2, max(hip_width * 0.34, waist_width * 0.42), depth_radius * 0.58),
            (waist_y, waist_width * 0.43, depth_radius * 0.52),
        ],
        region=PANTS_UV_REGIONS["front"],
        back_region=PANTS_UV_REGIONS["back"],
        group="hip",
        segments=36,
    )
    leg_spacing = max(leg_gap / 2 + hip_width * 0.18, hem_width * 0.55)
    if left_leg_center_x is None:
        left_leg_center_x = cx + leg_spacing
    if right_leg_center_x is None:
        right_leg_center_x = cx - leg_spacing
    for leg_center_x, group in (
        (left_leg_center_x, "left_leg"),
        (right_leg_center_x, "right_leg"),
    ):
        leg_rings = [
            (hem_y, hem_width * 0.48, depth_radius * 0.42),
            (_lerp(hem_y, crotch_y, 0.50), max(hem_width * 0.52, hip_width * 0.13), depth_radius * 0.48),
            (crotch_y, max(hem_width * 0.58, hip_width * 0.16), depth_radius * 0.56),
            (hip_y, hip_width * 0.17, depth_radius * 0.62),
            (waist_y, waist_width * 0.15, depth_radius * 0.54),
        ]
        indices = _add_elliptical_shell(
            mesh,
            center_x=leg_center_x,
            center_z=cz,
            rings=leg_rings,
            region=PANTS_UV_REGIONS["front"],
            back_region=PANTS_UV_REGIONS["back"],
            group="hip",
            segments=28,
        )
        mesh.vertex_groups.setdefault(group, []).extend(indices)

    for group in ("waist", "hip", "left_leg", "right_leg"):
        mesh.vertex_groups[group] = sorted(set(mesh.vertex_groups.get(group, [])))
    mesh.vertex_groups["waist"] = sorted(set(mesh.vertex_groups.get("hip", [])))
    return mesh


def tshirt_metadata(vertex_groups: dict[str, list[int]]) -> dict[str, Any]:
    return {
        "category": "tshirt",
        "coordinate_system": "template_local",
        "version": 1,
        "uv_regions": TSHIRT_UV_REGIONS,
        "anchors": {
            "left_shoulder": [-0.31, 0.78, 0.0],
            "right_shoulder": [0.31, 0.78, 0.0],
            "neck": [0.0, 0.86, 0.06],
            "left_sleeve_opening": [-0.53, 0.61, 0.0],
            "right_sleeve_opening": [0.53, 0.61, 0.0],
            "hem_center": [0.0, 0.05, 0.0],
        },
        "vertex_groups": vertex_groups,
        "scale_regions": {
            "shoulder_width": {"vertex_group": "shoulders", "axis": "x"},
            "chest_width": {"vertex_group": "torso", "axis": "x"},
            "shirt_length": {"vertex_group": "torso", "axis": "y"},
        },
        "default_allowance": {
            "surface_offset": 0.025,
            "shoulder_extra": 0.04,
            "chest_extra": 0.05,
        },
    }


def pants_metadata(vertex_groups: dict[str, list[int]]) -> dict[str, Any]:
    return {
        "category": "pants",
        "coordinate_system": "template_local",
        "version": 1,
        "uv_regions": PANTS_UV_REGIONS,
        "anchors": {
            "waist_center": [0.0, 0.98, 0.0],
            "hip_center": [0.0, 0.74, 0.0],
            "left_hem": [-0.15, 0.02, 0.0],
            "right_hem": [0.15, 0.02, 0.0],
        },
        "vertex_groups": vertex_groups,
        "scale_regions": {
            "waist_width": {"vertex_group": "waist", "axis": "x"},
            "hip_width": {"vertex_group": "hip", "axis": "x"},
            "leg_length": {"vertex_group": "left_leg,right_leg", "axis": "y"},
            "hem_width": {"vertex_group": "left_leg,right_leg", "axis": "x"},
        },
        "default_allowance": {
            "surface_offset": 0.025,
            "waist_extra": 0.04,
            "hip_extra": 0.05,
        },
    }


def read_glb_bounds(glb_path: str | Path) -> dict[str, list[float]]:
    import numpy as np
    import trimesh

    loaded = trimesh.load(glb_path)
    geometries = list(loaded.geometry.values()) if hasattr(loaded, "geometry") else [loaded]
    vertices = np.vstack([geometry.vertices for geometry in geometries if hasattr(geometry, "vertices")])
    min_values = vertices.min(axis=0).astype(float).tolist()
    max_values = vertices.max(axis=0).astype(float).tolist()
    return {
        "min": min_values,
        "max": max_values,
        "size": (vertices.max(axis=0) - vertices.min(axis=0)).astype(float).tolist(),
    }


def _quad_uvs(region: dict[str, float]) -> list[Vec2]:
    return [
        (region["u_min"], region["v_max"]),
        (region["u_max"], region["v_max"]),
        (region["u_max"], region["v_min"]),
        (region["u_min"], region["v_min"]),
    ]


def _add_elliptical_shell(
    mesh: MeshDraft,
    *,
    center_x: float,
    center_z: float,
    rings: list[tuple[float, float, float]],
    region: dict[str, float],
    back_region: dict[str, float] | None = None,
    group: str,
    segments: int = 32,
) -> list[int]:
    indices: list[int] = []
    base = len(mesh.vertices)
    for ring_index, (y_value, radius_x, radius_z) in enumerate(rings):
        v_ratio = ring_index / max(len(rings) - 1, 1)
        for segment in range(segments + 1):
            angle = 2 * 3.141592653589793 * segment / segments
            cos_value = math.cos(angle)
            sin_value = math.sin(angle)
            x_value = center_x + cos_value * radius_x
            z_value = center_z + sin_value * radius_z
            u_ratio = (cos_value + 1.0) / 2.0
            active_region = region
            if back_region is not None and sin_value < 0:
                active_region = back_region
                u_ratio = 1.0 - u_ratio
            mesh.vertices.append((x_value, y_value, z_value))
            mesh.texcoords.append(_region_uv(active_region, u_ratio, v_ratio))
            index = len(mesh.vertices) - 1
            indices.append(index)
            mesh.vertex_groups.setdefault(group, []).append(index)

    for ring_index in range(len(rings) - 1):
        for segment in range(segments):
            a = base + ring_index * (segments + 1) + segment
            b = a + 1
            c = base + (ring_index + 1) * (segments + 1) + segment + 1
            d = c - 1
            mesh.faces.append((a, b, c))
            mesh.faces.append((c, d, a))
    return indices


def _add_oriented_tube(
    mesh: MeshDraft,
    *,
    start: Vec3,
    end: Vec3,
    radius_start: float,
    radius_end: float,
    region: dict[str, float],
    group: str,
    segments: int = 18,
) -> list[int]:
    axis = _normalize((end[0] - start[0], end[1] - start[1], end[2] - start[2]))
    reference = (0.0, 1.0, 0.0)
    if abs(_dot(axis, reference)) > 0.92:
        reference = (0.0, 0.0, 1.0)
    normal_a = _normalize(_cross(axis, reference))
    normal_b = _normalize(_cross(axis, normal_a))

    indices: list[int] = []
    base = len(mesh.vertices)
    for ring_index, (center, radius) in enumerate(((start, radius_start), (end, radius_end))):
        for segment in range(segments + 1):
            angle = 2 * 3.141592653589793 * segment / segments
            radial = (
                normal_a[0] * math.cos(angle) * radius + normal_b[0] * math.sin(angle) * radius,
                normal_a[1] * math.cos(angle) * radius + normal_b[1] * math.sin(angle) * radius,
                normal_a[2] * math.cos(angle) * radius + normal_b[2] * math.sin(angle) * radius,
            )
            mesh.vertices.append((center[0] + radial[0], center[1] + radial[1], center[2] + radial[2]))
            mesh.texcoords.append(_region_uv(region, segment / segments, ring_index))
            index = len(mesh.vertices) - 1
            indices.append(index)
            mesh.vertex_groups.setdefault(group, []).append(index)

    for segment in range(segments):
        a = base + segment
        b = a + 1
        c = base + (segments + 1) + segment + 1
        d = c - 1
        mesh.faces.append((a, b, c))
        mesh.faces.append((c, d, a))
    return indices


def _region_uv(region: dict[str, float], u_ratio: float, v_ratio: float) -> Vec2:
    return (
        region["u_min"] + (region["u_max"] - region["u_min"]) * u_ratio,
        region["v_max"] - (region["v_max"] - region["v_min"]) * v_ratio,
    )


def _vector_length(vector: Vec3) -> float:
    return math.sqrt(vector[0] * vector[0] + vector[1] * vector[1] + vector[2] * vector[2])


def _normalize(vector: Vec3) -> Vec3:
    length = _vector_length(vector)
    if length == 0:
        return (1.0, 0.0, 0.0)
    return (vector[0] / length, vector[1] / length, vector[2] / length)


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _lerp(start: float, end: float, amount: float) -> float:
    return start + (end - start) * amount
