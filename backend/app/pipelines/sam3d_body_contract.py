"""Convert SAM 3D Body estimator outputs into the project body contract."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from backend.app.contracts.body_output import validate_body_output, write_json
from backend.app.contracts.glb import write_mesh_glb


MHR_INDEX = {
    "left_shoulder": 5,
    "right_shoulder": 6,
    "left_elbow": 7,
    "right_elbow": 8,
    "left_hip": 9,
    "right_hip": 10,
    "left_knee": 11,
    "right_knee": 12,
    "left_ankle": 13,
    "right_ankle": 14,
    "right_wrist": 41,
    "left_wrist": 62,
    "neck": 69,
}


def export_sam3d_body_contract(
    *,
    person_output: dict[str, Any],
    faces: Any,
    output_dir: str | Path,
    job_id: str,
    model_name: str = "sam-3d-body",
    model_version: str = "unknown",
    warnings: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Export the first SAM 3D Body person output to the phase-0 contract."""

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)

    vertices = _as_float_rows(person_output["pred_vertices"])
    keypoints = _as_float_rows(person_output["pred_keypoints_3d"])
    normalized_vertices, normalized_keypoints = normalize_body(vertices, keypoints)

    write_mesh_glb(root / "body.glb", normalized_vertices, _as_int_rows(faces), name="SAM3DBody")
    write_json(root / "landmarks.json", build_landmarks(normalized_keypoints))
    write_json(
        root / "body_metadata.json",
        {
            "job_id": job_id,
            "model_name": model_name,
            "model_version": model_version,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_image_policy": "not_logged",
            "quality_score": estimate_quality_score(person_output),
            "warnings": list(warnings or []),
        },
    )
    write_json(root / "sam_params.json", build_sam_params(person_output))
    return validate_body_output(root)


def export_neutral_sam3d_body_contract(
    *,
    person_output: dict[str, Any],
    model_head: Any,
    faces: Any,
    output_dir: str | Path,
    job_id: str,
    model_name: str = "sam-3d-body-neutral-mannequin",
    model_version: str = "unknown",
    warnings: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Export a neutral-pose SAM/MHR mannequin with the predicted body shape."""

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)

    vertices, keypoints = build_neutral_sam3d_body(person_output, model_head)
    normalized_vertices, normalized_keypoints = normalize_body(vertices, keypoints)
    normalized_vertices, normalized_keypoints = orient_y_up(
        normalized_vertices,
        normalized_keypoints,
    )

    write_mesh_glb(
        root / "body.glb",
        normalized_vertices,
        _as_int_rows(faces),
        name="SAM3DNeutralMannequin",
        base_color=(0.68, 0.67, 0.64, 1.0),
        roughness=0.86,
        double_sided=True,
    )
    write_json(root / "landmarks.json", build_landmarks(normalized_keypoints))
    write_json(
        root / "body_metadata.json",
        {
            "job_id": job_id,
            "model_name": model_name,
            "model_version": model_version,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_image_policy": "not_logged",
            "quality_score": estimate_quality_score(person_output),
            "shape_source": "sam_3d_body_shape_scale_params",
            "pose_policy": "zero_global_body_hand_pose",
            "warnings": [
                "neutral_pose_generated_from_sam_shape_scale_not_source_photo_pose",
                *(warnings or []),
            ],
        },
    )
    write_json(root / "sam_params.json", build_sam_params(person_output))
    return validate_body_output(root)


def build_neutral_sam3d_body(
    person_output: dict[str, Any],
    model_head: Any,
) -> tuple[list[list[float]], list[list[float]]]:
    """Run SAM's MHR head in neutral pose while preserving predicted shape/scale."""

    import torch

    device = next(model_head.parameters()).device
    shape_params = _batched_tensor(person_output["shape_params"], device)
    scale_params = _batched_tensor(person_output["scale_params"], device)
    body_pose_params = torch.zeros_like(_batched_tensor(person_output["body_pose_params"], device))
    hand_pose_params = torch.zeros_like(_batched_tensor(person_output["hand_pose_params"], device))
    global_rot = torch.zeros_like(_batched_tensor(person_output["global_rot"], device))
    global_trans = torch.zeros_like(global_rot)
    expr_params = torch.zeros_like(_batched_tensor(person_output["expr_params"], device))

    with torch.no_grad():
        vertices, keypoints = model_head.mhr_forward(
            global_trans=global_trans,
            global_rot=global_rot,
            body_pose_params=body_pose_params,
            hand_pose_params=hand_pose_params,
            scale_params=scale_params,
            shape_params=shape_params,
            expr_params=expr_params,
            do_pcblend=True,
            return_keypoints=True,
        )

    vertices = vertices.detach().cpu().numpy()[0]
    keypoints = keypoints.detach().cpu().numpy()[0][:70]
    vertices[:, [1, 2]] *= -1
    keypoints[:, [1, 2]] *= -1
    return _as_float_rows(vertices), _as_float_rows(keypoints)


def build_sam_params(person_output: dict[str, Any]) -> dict[str, Any]:
    """Persist compact SAM/MHR params needed to reproduce the body shape."""

    keys = (
        "bbox",
        "focal_length",
        "pred_cam_t",
        "pred_pose_raw",
        "global_rot",
        "body_pose_params",
        "hand_pose_params",
        "scale_params",
        "shape_params",
        "expr_params",
        "mhr_model_params",
    )
    params = {
        key: _jsonable_numeric(person_output[key])
        for key in keys
        if key in person_output and person_output[key] is not None
    }
    params["schema_version"] = 1
    return params


def normalize_body(
    vertices: list[list[float]],
    keypoints: list[list[float]],
) -> tuple[list[list[float]], list[list[float]]]:
    """Center body around hips and set ankle floor to y=0.

    This is a first service coordinate normalization. It keeps SAM/MHR orientation
    intact and only translates the result into a stable viewer frame.
    """

    hip = _midpoint(
        keypoints[MHR_INDEX["left_hip"]],
        keypoints[MHR_INDEX["right_hip"]],
    )
    floor_y = min(
        keypoints[MHR_INDEX["left_ankle"]][1],
        keypoints[MHR_INDEX["right_ankle"]][1],
    )
    offset = [hip[0], floor_y, hip[2]]

    def shift(point: list[float]) -> list[float]:
        return [point[0] - offset[0], point[1] - offset[1], point[2] - offset[2]]

    return [shift(vertex) for vertex in vertices], [shift(point) for point in keypoints]


def orient_y_up(
    vertices: list[list[float]],
    keypoints: list[list[float]],
) -> tuple[list[list[float]], list[list[float]]]:
    """Flip neutral SAM output into the viewer's Y-up floor coordinate system."""

    neck_y = keypoints[MHR_INDEX["neck"]][1]
    ankle_y = (
        keypoints[MHR_INDEX["left_ankle"]][1]
        + keypoints[MHR_INDEX["right_ankle"]][1]
    ) / 2
    if ankle_y > neck_y:
        vertices = [[point[0], -point[1], point[2]] for point in vertices]
        keypoints = [[point[0], -point[1], point[2]] for point in keypoints]

    nose_z = keypoints[0][2]
    neck_z = keypoints[MHR_INDEX["neck"]][2]
    if nose_z < neck_z:
        vertices = [[point[0], point[1], -point[2]] for point in vertices]
        keypoints = [[point[0], point[1], -point[2]] for point in keypoints]

    floor_y = min(point[1] for point in vertices)

    def shift(point: list[float]) -> list[float]:
        return [point[0], point[1] - floor_y, point[2]]

    return [shift(vertex) for vertex in vertices], [shift(point) for point in keypoints]


def build_landmarks(keypoints: list[list[float]]) -> dict[str, Any]:
    left_shoulder = keypoints[MHR_INDEX["left_shoulder"]]
    right_shoulder = keypoints[MHR_INDEX["right_shoulder"]]
    left_hip = keypoints[MHR_INDEX["left_hip"]]
    right_hip = keypoints[MHR_INDEX["right_hip"]]
    left_ankle = keypoints[MHR_INDEX["left_ankle"]]
    right_ankle = keypoints[MHR_INDEX["right_ankle"]]
    hip_center = _midpoint(left_hip, right_hip)
    shoulder_center = _midpoint(left_shoulder, right_shoulder)
    chest_center = _weighted_midpoint(shoulder_center, hip_center, 0.65)
    waist_center = _weighted_midpoint(shoulder_center, hip_center, 0.38)

    points = {
        "neck": keypoints[MHR_INDEX["neck"]],
        "nose": keypoints[0],
        "left_shoulder": left_shoulder,
        "right_shoulder": right_shoulder,
        "left_elbow": keypoints[MHR_INDEX["left_elbow"]],
        "right_elbow": keypoints[MHR_INDEX["right_elbow"]],
        "chest_center": chest_center,
        "waist_center": waist_center,
        "hip_center": hip_center,
        "left_wrist": keypoints[MHR_INDEX["left_wrist"]],
        "right_wrist": keypoints[MHR_INDEX["right_wrist"]],
        "left_knee": keypoints[MHR_INDEX["left_knee"]],
        "right_knee": keypoints[MHR_INDEX["right_knee"]],
        "left_ankle": left_ankle,
        "right_ankle": right_ankle,
    }

    return {
        "coordinate_system": "viewer",
        "scale_mode": "meter_or_model_normalized",
        "points": points,
        "measurements_estimated": {
            "shoulder_width": _distance(left_shoulder, right_shoulder),
            "torso_length": _distance(shoulder_center, hip_center),
            "leg_length": (
                _distance(left_hip, left_ankle) + _distance(right_hip, right_ankle)
            )
            / 2,
            "hip_width": _distance(left_hip, right_hip),
        },
    }


def estimate_quality_score(person_output: dict[str, Any]) -> float:
    bbox = person_output.get("bbox")
    if bbox is None:
        return 0.75
    try:
        width = max(float(bbox[2]) - float(bbox[0]), 0.0)
        height = max(float(bbox[3]) - float(bbox[1]), 0.0)
    except (TypeError, ValueError, IndexError):
        return 0.75
    if width <= 0 or height <= 0:
        return 0.5
    aspect = height / width
    if 1.5 <= aspect <= 4.5:
        return 0.85
    return 0.65


def _as_float_rows(value: Any) -> list[list[float]]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    return [[float(item) for item in row[:3]] for row in value]


def _as_int_rows(value: Any) -> list[list[int]]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    return [[int(item) for item in row[:3]] for row in value]


def _batched_tensor(value: Any, device: Any) -> Any:
    import torch

    tensor = torch.as_tensor(value, dtype=torch.float32, device=device)
    if tensor.ndim == 1:
        tensor = tensor.unsqueeze(0)
    return tensor


def _jsonable_numeric(value: Any) -> Any:
    if hasattr(value, "detach"):
        value = value.detach().cpu()
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, tuple):
        value = list(value)
    if isinstance(value, list):
        return [_jsonable_numeric(item) for item in value]
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


def _midpoint(a: list[float], b: list[float]) -> list[float]:
    return [(a[idx] + b[idx]) / 2 for idx in range(3)]


def _weighted_midpoint(a: list[float], b: list[float], a_weight: float) -> list[float]:
    b_weight = 1 - a_weight
    return [a[idx] * a_weight + b[idx] * b_weight for idx in range(3)]


def _distance(a: list[float], b: list[float]) -> float:
    return sum((a[idx] - b[idx]) ** 2 for idx in range(3)) ** 0.5
