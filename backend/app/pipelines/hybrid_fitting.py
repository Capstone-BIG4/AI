"""Landmark and anchor based MVP garment fitting."""

from __future__ import annotations

import json
import math
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.app.contracts.body_output import validate_body_output
from backend.app.contracts.glb import write_mesh_glb
from backend.app.pipelines.garment_templates import (
    build_fitted_pants_shell_mesh,
    build_fitted_tshirt_shell_mesh,
    read_glb_bounds,
)
from backend.app.pipelines.upright_body import read_body_mesh


Vec3 = tuple[float, float, float]


@dataclass(frozen=True)
class BodyFitFrame:
    bounds: dict[str, list[float]]
    percentiles: dict[str, dict[str, float]]
    points: dict[str, Vec3]
    measurements: dict[str, float]
    section_metrics: dict[str, dict[str, float]]
    vertical_sign: int
    warnings: list[str]

    @property
    def height(self) -> float:
        return abs(self.bounds["size"][1])

    @property
    def full_width(self) -> float:
        return abs(self.bounds["size"][0])

    @property
    def full_depth(self) -> float:
        return abs(self.bounds["size"][2])

    @property
    def core_width(self) -> float:
        return self.percentiles["x"]["p80"] - self.percentiles["x"]["p20"]

    @property
    def center_x(self) -> float:
        candidates = [
            self.points[name][0]
            for name in ("chest_center", "waist_center", "hip_center")
            if name in self.points
        ]
        if candidates:
            return sum(candidates) / len(candidates)
        return (self.bounds["min"][0] + self.bounds["max"][0]) / 2

    @property
    def center_z(self) -> float:
        candidates = [
            self.points[name][2]
            for name in ("chest_center", "waist_center", "hip_center")
            if name in self.points
        ]
        if candidates:
            return sum(candidates) / len(candidates)
        return (self.bounds["min"][2] + self.bounds["max"][2]) / 2

    def lower_edge_y(self) -> float:
        return self.bounds["max"][1] if self.vertical_sign > 0 else self.bounds["min"][1]

    def advance_down(self, y_value: float, distance: float) -> float:
        return y_value + self.vertical_sign * distance

    def is_lower_than(self, candidate: float, reference: float) -> bool:
        return candidate > reference if self.vertical_sign > 0 else candidate < reference


def build_landmark_fitted_garments(
    *,
    body_dir: str | Path,
    scene_dir: str | Path,
    top_atlas: str | Path,
    pants_atlas: str | Path,
    tshirt_template_dir: str | Path,
    pants_template_dir: str | Path,
) -> dict[str, Any]:
    """Create fitted sample garment GLBs using body landmarks and template anchors."""

    body_contract = validate_body_output(body_dir)
    body_glb = Path(body_contract["body_glb"])
    tshirt_anchors = _read_json(Path(tshirt_template_dir) / "anchors.json")
    pants_anchors = _read_json(Path(pants_template_dir) / "anchors.json")
    body_vertices, body_faces = read_body_mesh(body_glb)
    frame = build_body_fit_frame(body_contract, body_vertices)

    root = Path(scene_dir)
    root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(top_atlas, root / "top_texture_atlas.png")
    shutil.copy2(pants_atlas, root / "pants_texture_atlas.png")

    top_fit = compute_top_fit(frame, tshirt_anchors)
    pants_fit = compute_pants_fit(frame, pants_anchors, top_fit)
    top_fit = adjust_top_fit_for_clearance(frame, top_fit, body_vertices)
    pants_fit = adjust_pants_fit_for_clearance(
        frame,
        pants_fit,
        build_pants_collision_proxy(frame, pants_fit),
    )

    top_mesh = build_fitted_tshirt_shell_mesh(
        center=(top_fit["center_x"], 0.0, top_fit["center_z"]),
        top_y=top_fit["top_y"],
        shoulder_y=top_fit["shoulder_y"],
        hem_y=top_fit["hem_y"],
        shoulder_width=top_fit["shoulder_width"],
        torso_width=top_fit["torso_width"],
        z_front=top_fit["z_front"],
        z_back=top_fit["z_back"],
        left_shoulder=top_fit["left_shoulder"],
        right_shoulder=top_fit["right_shoulder"],
        left_wrist=top_fit["left_sleeve_target"],
        right_wrist=top_fit["right_sleeve_target"],
        sleeve_radius=top_fit["sleeve_radius"],
        vertical_sign=top_fit["vertical_sign"],
    )
    pants_mesh = build_fitted_pants_shell_mesh(
        center=(pants_fit["center_x"], 0.0, pants_fit["center_z"]),
        waist_y=pants_fit["waist_y"],
        hip_y=pants_fit["hip_y"],
        hem_y=pants_fit["hem_y"],
        waist_width=pants_fit["waist_width"],
        hip_width=pants_fit["hip_width"],
        hem_width=pants_fit["hem_width"],
        leg_gap=pants_fit["leg_gap"],
        z_front=pants_fit["z_front"],
        z_back=pants_fit["z_back"],
        left_leg_center_x=pants_fit["left_leg_center_x"],
        right_leg_center_x=pants_fit["right_leg_center_x"],
    )

    write_mesh_glb(
        root / "body_visible.glb",
        body_vertices,
        filter_visible_body_faces(body_vertices, body_faces, frame, top_fit, pants_fit),
        name="VisibleSAMBody",
        base_color=(0.70, 0.62, 0.56, 1.0),
        roughness=0.82,
        double_sided=True,
    )
    write_mesh_glb(
        root / "top.glb",
        top_mesh.vertices,
        top_mesh.faces,
        name="LandmarkFittedTop",
        base_color=(1.0, 1.0, 1.0, 1.0),
        roughness=0.84,
        texcoords=top_mesh.texcoords,
        texture_uri="top_texture_atlas.png",
        double_sided=True,
    )
    write_mesh_glb(
        root / "pants.glb",
        pants_mesh.vertices,
        pants_mesh.faces,
        name="LandmarkFittedPants",
        base_color=(1.0, 1.0, 1.0, 1.0),
        roughness=0.72,
        texcoords=pants_mesh.texcoords,
        texture_uri="pants_texture_atlas.png",
        double_sided=True,
    )

    report = {
        "body_glb": str(body_glb),
        "display_body_glb": str(root / "body_visible.glb"),
        "body_bounds": frame.bounds,
        "method": "landmark_anchor_hybrid_v1",
        "coordinate_assumptions": {
            "vertical_axis": "y",
            "y_direction": "increases_down" if frame.vertical_sign > 0 else "increases_up",
            "surface_offset_mode": "front_back_depth_offset",
        },
        "landmark_warnings": frame.warnings,
        "top": _top_report(top_fit, tshirt_anchors),
        "pants": _pants_report(pants_fit, pants_anchors),
    }
    with (root / "fitting_report.json").open("w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
        file.write("\n")
    return report


def build_body_fit_frame(
    body_contract: dict[str, Any],
    body_vertices: list[Vec3] | None = None,
) -> BodyFitFrame:
    points = {
        name: _to_vec3(value)
        for name, value in body_contract["landmarks"]["points"].items()
    }
    measurements = {
        name: float(value)
        for name, value in body_contract["landmarks"].get("measurements_estimated", {}).items()
        if isinstance(value, (int, float))
    }
    bounds = read_glb_bounds(body_contract["body_glb"])
    percentiles = read_glb_percentiles(body_contract["body_glb"])
    if body_vertices is None:
        body_vertices, _ = read_body_mesh(body_contract["body_glb"])
    section_metrics = _body_section_metrics(body_vertices, points, bounds)
    warnings: list[str] = []

    neck_y = points["neck"][1]
    ankle_y = _mean([points["left_ankle"][1], points["right_ankle"][1]])
    vertical_sign = 1 if ankle_y > neck_y else -1
    shoulder_delta = abs(points["left_shoulder"][1] - points["right_shoulder"][1])
    if shoulder_delta > abs(bounds["size"][1]) * 0.18:
        warnings.append("asymmetric_shoulder_landmarks_pose_influenced")
    ankle_delta = abs(points["left_ankle"][1] - points["right_ankle"][1])
    if ankle_delta > abs(bounds["size"][1]) * 0.18:
        warnings.append("asymmetric_ankle_landmarks_pose_influenced")

    return BodyFitFrame(
        bounds=bounds,
        percentiles=percentiles,
        points=points,
        measurements=measurements,
        section_metrics=section_metrics,
        vertical_sign=vertical_sign,
        warnings=warnings,
    )


def compute_top_fit(
    frame: BodyFitFrame,
    template: dict[str, Any],
) -> dict[str, Any]:
    allowance = template.get("default_allowance", {})
    surface_offset = float(allowance.get("surface_offset", 0.025))
    shoulder_extra = float(allowance.get("shoulder_extra", 0.04))
    chest_extra = float(allowance.get("chest_extra", 0.05))

    shoulder_y = _mean(
        [frame.points["left_shoulder"][1], frame.points["right_shoulder"][1]]
    )
    hip_y = frame.points["hip_center"][1]
    waist_y = frame.points["waist_center"][1]
    lower_torso_y = hip_y if frame.is_lower_than(hip_y, waist_y) else frame.advance_down(waist_y, frame.height * 0.12)
    hem_y = frame.advance_down(lower_torso_y, frame.height * 0.035)
    top_y = (shoulder_y - 0.12 * hem_y) / 0.88

    measured_shoulder = _distance(frame.points["left_shoulder"], frame.points["right_shoulder"])
    measured_hip = float(frame.measurements.get("hip_width", 0.0))
    chest_width = _section_value(frame, "chest", "width", frame.core_width)
    waist_width = _section_value(frame, "waist", "width", measured_hip * 0.95)
    hip_width = _section_value(frame, "hip", "width", measured_hip)
    shoulder_width = _clamp(
        max(measured_shoulder * 1.08, chest_width * 1.03, 0.32) + shoulder_extra * 0.65,
        0.32,
        max(measured_shoulder * 1.36, 0.42),
    )
    torso_width = _clamp(
        max(chest_width * 1.02, waist_width * 1.02, hip_width * 1.03, shoulder_width * 0.72) + chest_extra * 0.62,
        0.30,
        max(shoulder_width * 0.90, hip_width * 1.10),
    )
    sleeve_span = _clamp(
        shoulder_width + max(shoulder_width * 0.48, 0.18),
        shoulder_width,
        max(frame.full_width * 0.86, shoulder_width),
    )
    front_z, back_z = _front_back_z(frame, surface_offset, sections=("chest", "waist", "hip"))
    sleeve_radius = _clamp(
        max(shoulder_width * 0.13, 0.072),
        0.072,
        0.120,
    )

    return {
        "center_x": frame.center_x,
        "center_z": frame.center_z,
        "top_y": top_y,
        "shoulder_y": shoulder_y,
        "hem_y": hem_y,
        "shoulder_width": shoulder_width,
        "torso_width": torso_width,
        "sleeve_span": sleeve_span,
        "sleeve_radius": sleeve_radius,
        "left_shoulder": frame.points["left_shoulder"],
        "right_shoulder": frame.points["right_shoulder"],
        "left_wrist": frame.points["left_wrist"],
        "right_wrist": frame.points["right_wrist"],
        "left_sleeve_target": frame.points.get("left_elbow", frame.points["left_wrist"]),
        "right_sleeve_target": frame.points.get("right_elbow", frame.points["right_wrist"]),
        "vertical_sign": frame.vertical_sign,
        "z_front": front_z,
        "z_back": back_z,
        "template_shoulder_width": _anchor_width(template, "left_shoulder", "right_shoulder"),
        "template_torso_width": 0.46,
        "template_length": abs(template["anchors"]["neck"][1] - template["anchors"]["hem_center"][1]),
        "warnings": [],
    }


def compute_pants_fit(
    frame: BodyFitFrame,
    template: dict[str, Any],
    top_fit: dict[str, Any],
) -> dict[str, Any]:
    allowance = template.get("default_allowance", {})
    surface_offset = float(allowance.get("surface_offset", 0.025))
    waist_extra = float(allowance.get("waist_extra", 0.04))
    hip_extra = float(allowance.get("hip_extra", 0.05))

    waist_y = frame.points["waist_center"][1]
    hip_y = frame.points["hip_center"][1]
    if not frame.is_lower_than(hip_y, waist_y):
        hip_y = frame.advance_down(waist_y, frame.height * 0.12)

    ankle_candidates = [frame.points["left_ankle"][1], frame.points["right_ankle"][1], frame.lower_edge_y()]
    hem_y = max(ankle_candidates) if frame.vertical_sign > 0 else min(ankle_candidates)
    hem_y = frame.advance_down(hem_y, -frame.height * 0.02)

    measured_hip = float(frame.measurements.get("hip_width", 0.0))
    body_waist_width = _section_value(frame, "waist", "width", measured_hip * 0.95)
    body_hip_width = _section_value(frame, "hip", "width", measured_hip)
    measured_hip_width = measured_hip if 0.12 <= measured_hip <= 1.2 else body_hip_width
    waist_width = _clamp(
        max(top_fit["torso_width"] * 0.66, body_waist_width * 1.02, measured_hip_width * 0.90) + waist_extra * 0.55,
        0.28,
        max(body_waist_width * 1.24, 0.38),
    )
    hip_width = _clamp(
        max(waist_width * 1.03, body_hip_width * 1.06, measured_hip_width * 1.00) + hip_extra * 0.55,
        waist_width,
        max(body_hip_width * 1.22, waist_width),
    )
    hem_width = _clamp(hip_width * 0.30, 0.12, max(hip_width * 0.40, 0.13))
    leg_gap = _clamp(hip_width * 0.16, 0.045, 0.12)
    front_z, back_z = _front_back_z(frame, surface_offset, sections=("waist", "hip"))

    return {
        "center_x": frame.center_x,
        "center_z": frame.center_z,
        "waist_y": waist_y,
        "hip_y": hip_y,
        "hem_y": hem_y,
        "waist_width": waist_width,
        "hip_width": hip_width,
        "hem_width": hem_width,
        "leg_gap": leg_gap,
        "left_leg_center_x": _mean(
            [frame.points["left_knee"][0], frame.points["left_ankle"][0]]
        ),
        "right_leg_center_x": _mean(
            [frame.points["right_knee"][0], frame.points["right_ankle"][0]]
        ),
        "z_front": front_z,
        "z_back": back_z,
        "template_waist_width": 0.46,
        "template_hip_width": 0.58,
        "template_leg_length": abs(template["anchors"]["waist_center"][1] - template["anchors"]["left_hem"][1]),
        "template_hem_width": abs(template["anchors"]["right_hem"][0] - template["anchors"]["left_hem"][0]),
        "warnings": [],
    }


def adjust_top_fit_for_clearance(
    frame: BodyFitFrame,
    fit: dict[str, Any],
    body_vertices: list[Vec3],
) -> dict[str, Any]:
    target_clearance = 0.012
    adjusted = dict(fit)
    iterations = 0
    for iterations in range(10):
        check = analyze_top_clearance(frame, adjusted, body_vertices)
        missing = target_clearance - check["min_clearance"]
        if missing <= 0:
            break
        torso_clearance = _numeric_clearance(check["torso"])
        sleeve_clearance = _numeric_clearance(check["sleeves"])
        if torso_clearance < target_clearance:
            grow = min(max(missing * 0.65, 0.01), 0.055)
            adjusted["torso_width"] += grow
            adjusted["shoulder_width"] += grow * 0.45
        if sleeve_clearance < target_clearance:
            adjusted["sleeve_radius"] = min(
                adjusted["sleeve_radius"] + min(max(missing * 0.70, 0.008), 0.024),
                0.180,
            )
        torso_missing = target_clearance - torso_clearance
        if torso_missing > 0:
            depth_grow = min(max(torso_missing * 1.25, 0.010), 0.045)
            adjusted["z_front"] += depth_grow
            adjusted["z_back"] -= depth_grow
    final_check = analyze_top_clearance(frame, adjusted, body_vertices)
    final_check["adjustment_iterations"] = iterations
    adjusted["fit_checks"] = final_check
    adjusted["warnings"] = _clearance_warnings(final_check)
    return adjusted


def adjust_pants_fit_for_clearance(
    frame: BodyFitFrame,
    fit: dict[str, Any],
    body_vertices: list[Vec3],
) -> dict[str, Any]:
    target_clearance = 0.006
    adjusted = dict(fit)
    iterations = 0
    for iterations in range(28):
        check = analyze_pants_clearance(frame, adjusted, body_vertices)
        missing = target_clearance - check["min_clearance"]
        if missing <= 0 or (
            check["penetration_vertex_count"] == 0 and check["min_clearance"] >= 0.002
        ):
            break
        grow = min(max(missing * 0.42, 0.006), 0.022)
        adjusted["waist_width"] += grow * 0.45
        adjusted["hip_width"] += grow * 0.55
        adjusted["hem_width"] += grow * 0.25
        depth_grow = min(max(missing * 0.9, 0.012), 0.06)
        adjusted["z_front"] += depth_grow
        adjusted["z_back"] -= depth_grow
    final_check = analyze_pants_clearance(frame, adjusted, body_vertices)
    final_check["adjustment_iterations"] = iterations
    adjusted["fit_checks"] = final_check
    adjusted["warnings"] = _clearance_warnings(final_check)
    return adjusted


def analyze_top_clearance(
    frame: BodyFitFrame,
    fit: dict[str, Any],
    body_vertices: list[Vec3],
) -> dict[str, Any]:
    torso = _empty_clearance_summary()
    sleeves = _empty_clearance_summary()
    y_min, y_max = sorted((fit["hem_y"], fit["shoulder_y"]))
    depth_radius = max((fit["z_front"] - fit["z_back"]) / 2, 0.05)
    center_z = (fit["z_front"] + fit["z_back"]) / 2
    for vertex in body_vertices:
        x_value, y_value, z_value = vertex
        torso_sample_limit = min(fit["shoulder_width"] * 0.38, fit["torso_width"] * 0.54)
        if y_min <= y_value <= y_max and abs(x_value - fit["center_x"]) <= torso_sample_limit:
            t = (y_value - y_min) / max(y_max - y_min, 0.001)
            radius_x = _lerp(fit["torso_width"] * 0.50, fit["shoulder_width"] * 0.50, t)
            radius_z = _lerp(depth_radius * 0.86, depth_radius, t)
            clearance = _elliptical_shell_clearance(
                x_value - fit["center_x"],
                z_value - center_z,
                radius_x,
                radius_z,
            )
            _record_clearance(torso, clearance)

        for side, shoulder_name, wrist_name in (
            (1, "left_shoulder", "left_sleeve_target"),
            (-1, "right_shoulder", "right_sleeve_target"),
        ):
            if (x_value - fit["center_x"]) * side < 0:
                continue
            torso_edge = fit["torso_width"] * 0.46
            if abs(x_value - fit["center_x"]) < torso_edge:
                continue
            start, end = _sleeve_segment(
                fit[shoulder_name],
                fit[wrist_name],
                fit["sleeve_radius"],
                side,
                fit["shoulder_width"],
                int(fit.get("vertical_sign", frame.vertical_sign)),
            )
            distance, projection = _distance_to_segment(vertex, start, end)
            sleeve_sample_radius = fit["sleeve_radius"] + 0.045
            if 0.0 <= projection <= 1.0 and distance <= sleeve_sample_radius:
                _record_clearance(sleeves, fit["sleeve_radius"] - distance)

    return _combine_clearance("top", torso, sleeves)


def analyze_pants_clearance(
    frame: BodyFitFrame,
    fit: dict[str, Any],
    body_vertices: list[Vec3],
) -> dict[str, Any]:
    hip = _empty_clearance_summary()
    legs = _empty_clearance_summary()
    y_min, y_max = sorted((fit["hem_y"], fit["hip_y"]))
    crotch_y = frame.advance_down(fit["hip_y"], abs(fit["waist_y"] - fit["hip_y"]) * 0.72)
    upper_min, upper_max = sorted((crotch_y, fit["hip_y"]))
    center_z = (fit["z_front"] + fit["z_back"]) / 2
    depth_radius = max((fit["z_front"] - fit["z_back"]) / 2, 0.05)
    leg_centers = (fit["left_leg_center_x"], fit["right_leg_center_x"])
    for vertex in body_vertices:
        x_value, y_value, z_value = vertex
        if not y_min <= y_value <= y_max:
            continue
        if upper_min <= y_value <= upper_max:
            t = abs(y_value - crotch_y) / max(abs(fit["hip_y"] - crotch_y), 0.001)
            radius_x = _lerp(fit["hip_width"] * 0.44, fit["hip_width"] * 0.50, t)
            radius_z = _lerp(depth_radius * 0.78, depth_radius * 0.88, t)
            if abs(x_value - fit["center_x"]) > max(radius_x * 1.08, 0.14):
                continue
            clearance = _elliptical_shell_clearance(
                x_value - fit["center_x"],
                z_value - center_z,
                radius_x,
                radius_z,
            )
            _record_clearance(hip, clearance)
            continue

        center_x = min(leg_centers, key=lambda value: abs(x_value - value))
        t = (y_value - y_min) / max(y_max - y_min, 0.001)
        radius_x = _lerp(fit["hem_width"] * 0.50, fit["hip_width"] * 0.24, t)
        radius_z = _lerp(depth_radius * 0.56, depth_radius * 0.82, t)
        leg_sample_limit = max(min(radius_x * 1.05, fit["hip_width"] * 0.22), 0.105)
        if abs(x_value - center_x) > leg_sample_limit:
            continue
        clearance = _elliptical_shell_clearance(
            x_value - center_x,
            z_value - center_z,
            radius_x,
            radius_z,
        )
        _record_clearance(legs, clearance)

    return _combine_clearance("pants", hip, legs)


def build_pants_collision_proxy(frame: BodyFitFrame, fit: dict[str, Any]) -> list[Vec3]:
    """Build a body-core proxy for pants fitting, excluding source-photo clothing bulges."""

    vertices: list[Vec3] = []
    center_z = frame.center_z
    waist_depth = _section_value(frame, "waist", "depth", 0.20)
    hip_depth = _section_value(frame, "hip", "depth", waist_depth)
    waist_width = _section_value(frame, "waist", "width", fit["waist_width"] * 0.72)
    hip_width = _section_value(frame, "hip", "width", fit["hip_width"] * 0.70)
    crotch_y = frame.advance_down(fit["hip_y"], abs(fit["waist_y"] - fit["hip_y"]) * 0.72)

    for y_value, radius_x, radius_z in (
        (fit["waist_y"], max(waist_width * 0.50, 0.13), max(waist_depth * 0.38, 0.075)),
        (fit["hip_y"], max(hip_width * 0.50, 0.15), max(hip_depth * 0.38, 0.082)),
        (crotch_y, max(hip_width * 0.34, 0.11), max(hip_depth * 0.34, 0.074)),
    ):
        vertices.extend(_ellipse_points(fit["center_x"], y_value, center_z, radius_x, radius_z))

    for side, knee_name, ankle_name, leg_center_x in (
        (1, "left_knee", "left_ankle", fit["left_leg_center_x"]),
        (-1, "right_knee", "right_ankle", fit["right_leg_center_x"]),
    ):
        knee = frame.points[knee_name]
        ankle = frame.points[ankle_name]
        upper_leg_x = _lerp(leg_center_x, knee[0], 0.35)
        rings = (
            (crotch_y, upper_leg_x, 0.078, 0.080),
            ((crotch_y + knee[1]) / 2, _lerp(upper_leg_x, knee[0], 0.45), 0.068, 0.068),
            (knee[1], knee[0], 0.058, 0.060),
            ((knee[1] + ankle[1]) / 2, _lerp(knee[0], ankle[0], 0.55), 0.052, 0.054),
            (max(fit["hem_y"], min(ankle[1], knee[1])), ankle[0], 0.048, 0.050),
        )
        for y_value, x_value, radius_x, radius_z in rings:
            vertices.extend(_ellipse_points(x_value, y_value, center_z, radius_x, radius_z))

    return vertices


def filter_visible_body_faces(
    vertices: list[Vec3],
    faces: list[tuple[int, int, int]],
    frame: BodyFitFrame,
    top_fit: dict[str, Any],
    pants_fit: dict[str, Any],
) -> list[tuple[int, int, int]]:
    visible: list[tuple[int, int, int]] = []
    for face in faces:
        centroid = _face_centroid(vertices, face)
        if _covered_by_top(centroid, top_fit) or _covered_by_pants(centroid, frame, pants_fit):
            continue
        visible.append(face)
    return visible or faces


def _covered_by_top(point: Vec3, fit: dict[str, Any]) -> bool:
    x_value, y_value, z_value = point
    for side, shoulder_name, wrist_name in (
        (1, "left_shoulder", "left_sleeve_target"),
        (-1, "right_shoulder", "right_sleeve_target"),
    ):
        if (x_value - fit["center_x"]) * side < 0:
            continue
        start, end = _sleeve_segment(
            fit[shoulder_name],
            fit[wrist_name],
            fit["sleeve_radius"],
            side,
            fit["shoulder_width"],
            int(fit.get("vertical_sign", -1)),
        )
        distance, projection = _distance_to_segment(point, start, end)
        if 0.0 <= projection <= 1.0 and distance <= fit["sleeve_radius"] * 1.06:
            return True

    y_min, y_max = sorted((fit["hem_y"], fit["top_y"]))
    if not y_min <= y_value <= y_max:
        return False
    y_ratio = (y_value - y_min) / max(y_max - y_min, 0.001)
    torso_half = fit["torso_width"] * 0.49
    shoulder_half = fit["shoulder_width"] * 0.43
    width = _lerp(torso_half, shoulder_half, min(y_ratio * 1.18, 1.0))
    z_center = (fit["z_front"] + fit["z_back"]) / 2
    z_radius = max((fit["z_front"] - fit["z_back"]) / 2, 0.08)
    return (
        abs(x_value - fit["center_x"]) <= width
        and abs(z_value - z_center) <= z_radius * 1.16
    )


def _covered_by_pants(point: Vec3, frame: BodyFitFrame, fit: dict[str, Any]) -> bool:
    x_value, y_value, z_value = point
    y_min, y_max = sorted((fit["hem_y"], fit["waist_y"]))
    if not y_min <= y_value <= y_max:
        return False
    z_center = (fit["z_front"] + fit["z_back"]) / 2
    z_radius = max((fit["z_front"] - fit["z_back"]) / 2, 0.08)
    if abs(z_value - z_center) > z_radius * 1.18:
        return False

    crotch_y = frame.advance_down(fit["hip_y"], abs(fit["waist_y"] - fit["hip_y"]) * 0.72)
    upper_min, upper_max = sorted((crotch_y, fit["waist_y"]))
    if upper_min <= y_value <= upper_max:
        return abs(x_value - fit["center_x"]) <= fit["hip_width"] * 0.54

    center_x = min(
        (fit["left_leg_center_x"], fit["right_leg_center_x"]),
        key=lambda value: abs(x_value - value),
    )
    return abs(x_value - center_x) <= max(fit["hem_width"] * 0.78, 0.11)


def _ellipse_points(
    center_x: float,
    y_value: float,
    center_z: float,
    radius_x: float,
    radius_z: float,
    *,
    segments: int = 24,
) -> list[Vec3]:
    return [
        (
            center_x + math.cos(2 * math.pi * index / segments) * radius_x,
            y_value,
            center_z + math.sin(2 * math.pi * index / segments) * radius_z,
        )
        for index in range(segments)
    ]


def _face_centroid(vertices: list[Vec3], face: tuple[int, int, int]) -> Vec3:
    a, b, c = (vertices[index] for index in face)
    return (
        (a[0] + b[0] + c[0]) / 3,
        (a[1] + b[1] + c[1]) / 3,
        (a[2] + b[2] + c[2]) / 3,
    )


def read_glb_percentiles(glb_path: str | Path) -> dict[str, dict[str, float]]:
    import numpy as np
    import trimesh

    loaded = trimesh.load(glb_path)
    geometries = list(loaded.geometry.values()) if hasattr(loaded, "geometry") else [loaded]
    vertices = np.vstack([geometry.vertices for geometry in geometries if hasattr(geometry, "vertices")])
    result: dict[str, dict[str, float]] = {}
    for axis_name, axis_index in (("x", 0), ("y", 1), ("z", 2)):
        values = np.percentile(vertices[:, axis_index], [10, 20, 50, 80, 90])
        result[axis_name] = {
            "p10": float(values[0]),
            "p20": float(values[1]),
            "p50": float(values[2]),
            "p80": float(values[3]),
            "p90": float(values[4]),
        }
    return result


def _top_report(fit: dict[str, Any], template: dict[str, Any]) -> dict[str, Any]:
    length = abs(fit["hem_y"] - fit["shoulder_y"])
    return {
        "shoulder_scale": round(fit["shoulder_width"] / fit["template_shoulder_width"], 3),
        "torso_scale": round(fit["torso_width"] / fit["template_torso_width"], 3),
        "length_scale": round(length / fit["template_length"], 3),
        "anchors_used": [
            "body.left_shoulder",
            "body.right_shoulder",
            "body.waist_center",
            "body.hip_center",
            "template.left_shoulder",
            "template.right_shoulder",
            "template.hem_center",
        ],
        "placement": {
            "center_x": round(fit["center_x"], 4),
            "center_z": round(fit["center_z"], 4),
            "top_y": round(fit["top_y"], 4),
            "hem_y": round(fit["hem_y"], 4),
            "shoulder_width": round(fit["shoulder_width"], 4),
            "torso_width": round(fit["torso_width"], 4),
            "sleeve_radius": round(fit["sleeve_radius"], 4),
        },
        "fit_checks": fit["fit_checks"],
        "collision_warnings": fit["warnings"],
    }


def _pants_report(fit: dict[str, Any], template: dict[str, Any]) -> dict[str, Any]:
    length = abs(fit["hem_y"] - fit["waist_y"])
    return {
        "waist_scale": round(fit["waist_width"] / fit["template_waist_width"], 3),
        "hip_scale": round(fit["hip_width"] / fit["template_hip_width"], 3),
        "length_scale": round(length / fit["template_leg_length"], 3),
        "hem_width_scale": round(fit["hem_width"] / fit["template_hem_width"], 3),
        "anchors_used": [
            "body.waist_center",
            "body.hip_center",
            "body.left_ankle",
            "body.right_ankle",
            "template.waist_center",
            "template.hip_center",
            "template.left_hem",
            "template.right_hem",
        ],
        "placement": {
            "center_x": round(fit["center_x"], 4),
            "center_z": round(fit["center_z"], 4),
            "waist_y": round(fit["waist_y"], 4),
            "hip_y": round(fit["hip_y"], 4),
            "hem_y": round(fit["hem_y"], 4),
            "waist_width": round(fit["waist_width"], 4),
            "hip_width": round(fit["hip_width"], 4),
            "hem_width": round(fit["hem_width"], 4),
            "left_leg_center_x": round(fit["left_leg_center_x"], 4),
            "right_leg_center_x": round(fit["right_leg_center_x"], 4),
        },
        "fit_checks": fit["fit_checks"],
        "collision_warnings": fit["warnings"],
    }


def _front_back_z(
    frame: BodyFitFrame,
    surface_offset: float,
    *,
    sections: tuple[str, ...],
) -> tuple[float, float]:
    available = [frame.section_metrics[name] for name in sections if name in frame.section_metrics]
    if available:
        z_front = max(section["z_front"] for section in available)
        z_back = min(section["z_back"] for section in available)
    else:
        z_front = frame.percentiles["z"]["p90"]
        z_back = frame.percentiles["z"]["p10"]
    offset = max((z_front - z_back) * 0.08, surface_offset)
    return z_front + offset, z_back - offset


def _body_section_metrics(
    vertices: list[Vec3],
    points: dict[str, Vec3],
    bounds: dict[str, list[float]],
) -> dict[str, dict[str, float]]:
    height = max(abs(bounds["size"][1]), 0.001)
    center_x = _mean(
        [points[name][0] for name in ("chest_center", "waist_center", "hip_center") if name in points]
    )
    measured_shoulder = _distance(points["left_shoulder"], points["right_shoulder"])
    specs = {
        "chest": ("chest_center", height * 0.026, max(measured_shoulder * 0.62, 0.20)),
        "waist": ("waist_center", height * 0.030, max(measured_shoulder * 0.46, 0.17)),
        "hip": ("hip_center", height * 0.034, max(measured_shoulder * 0.58, 0.19)),
    }
    metrics: dict[str, dict[str, float]] = {}
    for section, (point_name, band, x_limit) in specs.items():
        y_value = points[point_name][1]
        samples = [
            vertex
            for vertex in vertices
            if abs(vertex[1] - y_value) <= band and abs(vertex[0] - center_x) <= x_limit
        ]
        if len(samples) < 20:
            samples = [
                vertex
                for vertex in vertices
                if abs(vertex[1] - y_value) <= band * 1.8 and abs(vertex[0] - center_x) <= x_limit * 1.2
            ]
        if not samples:
            continue
        xs = [sample[0] for sample in samples]
        zs = [sample[2] for sample in samples]
        x_p08 = _percentile(xs, 8)
        x_p92 = _percentile(xs, 92)
        z_p08 = _percentile(zs, 8)
        z_p92 = _percentile(zs, 92)
        metrics[section] = {
            "width": max(x_p92 - x_p08, 0.001),
            "depth": max(z_p92 - z_p08, 0.001),
            "z_front": z_p92,
            "z_back": z_p08,
            "sample_count": float(len(samples)),
        }
    return metrics


def _section_value(
    frame: BodyFitFrame,
    section: str,
    key: str,
    fallback: float,
) -> float:
    return float(frame.section_metrics.get(section, {}).get(key, fallback))


def _anchor_width(template: dict[str, Any], left_name: str, right_name: str) -> float:
    return abs(template["anchors"][right_name][0] - template["anchors"][left_name][0])


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _to_vec3(value: Any) -> Vec3:
    if not (
        isinstance(value, list)
        and len(value) == 3
        and all(isinstance(item, (int, float)) for item in value)
    ):
        raise ValueError(f"Expected numeric vec3, got {value!r}")
    return float(value[0]), float(value[1]), float(value[2])


def _distance(a: Vec3, b: Vec3) -> float:
    return math.sqrt(
        (a[0] - b[0]) * (a[0] - b[0])
        + (a[1] - b[1]) * (a[1] - b[1])
        + (a[2] - b[2]) * (a[2] - b[2])
    )


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def _sleeve_segment(
    shoulder: Vec3,
    wrist: Vec3,
    sleeve_radius: float,
    side: int,
    shoulder_width: float,
    vertical_sign: int,
) -> tuple[Vec3, Vec3]:
    start = (
        shoulder[0] + side * sleeve_radius * 0.52,
        shoulder[1] + vertical_sign * shoulder_width * 0.02,
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
        body_direction[2] * 0.35,
    )
    length = _distance((0.0, 0.0, 0.0), direction)
    if length < 0.05:
        direction = (side * 1.0, vertical_sign * 0.15, 0.0)
        length = _distance((0.0, 0.0, 0.0), direction)
    unit = (direction[0] / length, direction[1] / length, direction[2] / length)
    sleeve_length = max(min(length * 0.38, shoulder_width * 0.38), shoulder_width * 0.18)
    end = (
        start[0] + unit[0] * sleeve_length,
        start[1] + unit[1] * sleeve_length,
        start[2] + unit[2] * sleeve_length,
    )
    return start, end


def _distance_to_segment(point: Vec3, start: Vec3, end: Vec3) -> tuple[float, float]:
    segment = (end[0] - start[0], end[1] - start[1], end[2] - start[2])
    length_sq = segment[0] * segment[0] + segment[1] * segment[1] + segment[2] * segment[2]
    if length_sq == 0:
        return _distance(point, start), 0.0
    projection = (
        (point[0] - start[0]) * segment[0]
        + (point[1] - start[1]) * segment[1]
        + (point[2] - start[2]) * segment[2]
    ) / length_sq
    clamped = _clamp(projection, 0.0, 1.0)
    closest = (
        start[0] + segment[0] * clamped,
        start[1] + segment[1] * clamped,
        start[2] + segment[2] * clamped,
    )
    return _distance(point, closest), projection


def _elliptical_shell_clearance(
    dx: float,
    dz: float,
    radius_x: float,
    radius_z: float,
) -> float:
    radius_x = max(radius_x, 0.001)
    radius_z = max(radius_z, 0.001)
    normalized = math.sqrt((dx / radius_x) * (dx / radius_x) + (dz / radius_z) * (dz / radius_z))
    return min(radius_x, radius_z) * (1.0 - normalized)


def _empty_clearance_summary() -> dict[str, Any]:
    return {
        "sample_count": 0,
        "penetration_vertex_count": 0,
        "min_clearance": 999.0,
    }


def _record_clearance(summary: dict[str, Any], clearance: float) -> None:
    summary["sample_count"] += 1
    summary["min_clearance"] = min(float(summary["min_clearance"]), clearance)
    if clearance < 0:
        summary["penetration_vertex_count"] += 1


def _finalize_clearance_summary(summary: dict[str, Any]) -> dict[str, Any]:
    if summary["sample_count"] == 0:
        return {
            "sample_count": 0,
            "penetration_vertex_count": 0,
            "min_clearance": None,
            "status": "insufficient_samples",
        }
    return {
        "sample_count": summary["sample_count"],
        "penetration_vertex_count": summary["penetration_vertex_count"],
        "min_clearance": round(float(summary["min_clearance"]), 4),
        "status": "pass" if summary["penetration_vertex_count"] == 0 else "penetration_detected",
    }


def _combine_clearance(label: str, *sections: dict[str, Any]) -> dict[str, Any]:
    finalized = [_finalize_clearance_summary(section) for section in sections]
    valid = [section for section in finalized if section["min_clearance"] is not None]
    min_clearance = min((section["min_clearance"] for section in valid), default=999.0)
    penetration_count = sum(section["penetration_vertex_count"] for section in finalized)
    result = {
        "label": label,
        "min_clearance": min_clearance,
        "penetration_vertex_count": penetration_count,
        "status": "pass" if penetration_count == 0 and valid else "needs_attention",
    }
    if label == "top":
        result["torso"] = finalized[0]
        result["sleeves"] = finalized[1]
    elif label == "pants" and len(finalized) > 1:
        result["hip"] = finalized[0]
        result["legs"] = finalized[1]
    else:
        result["legs"] = finalized[0]
    return result


def _clearance_warnings(check: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    if check["penetration_vertex_count"] > 0:
        warnings.append(f"{check['label']}_body_penetration_detected")
    if check["status"] != "pass":
        warnings.append(f"{check['label']}_fit_check_needs_attention")
    return warnings


def _numeric_clearance(section: dict[str, Any]) -> float:
    value = section.get("min_clearance")
    return 999.0 if value is None else float(value)


def _lerp(start: float, end: float, amount: float) -> float:
    return start + (end - start) * amount


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        raise ValueError("Cannot compute percentile of empty values")
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = (len(ordered) - 1) * percentile / 100
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return float(ordered[lower])
    ratio = position - lower
    return float(ordered[lower] + (ordered[upper] - ordered[lower]) * ratio)
