from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from pipeline_common import PIPELINE, ensure_dir, now_iso, relative, write_json


def load_ascii_ply_vertices(path: Path) -> np.ndarray:
    lines = path.read_text(encoding="ascii", errors="replace").splitlines()
    if not lines or lines[0] != "ply":
        raise ValueError(f"Unsupported mesh file: {path}")
    vertex_count = None
    header_end = None
    for index, line in enumerate(lines):
        parts = line.split()
        if len(parts) == 3 and parts[:2] == ["element", "vertex"]:
            vertex_count = int(parts[2])
        if line == "end_header":
            header_end = index + 1
            break
    if vertex_count is None or header_end is None:
        raise ValueError("Invalid PLY header")
    vertices = []
    for line in lines[header_end : header_end + vertex_count]:
        x, y, z = line.split()[:3]
        vertices.append((float(x), float(y), float(z)))
    return np.asarray(vertices, dtype=np.float32)


def band_span(vertices: np.ndarray, y_min: float, y_max: float, low: float, high: float) -> dict[str, float]:
    height = max(y_max - y_min, 1e-6)
    lo = y_min + height * low
    hi = y_min + height * high
    band = vertices[(vertices[:, 1] >= lo) & (vertices[:, 1] <= hi)]
    if len(band) == 0:
        return {"x_width": 0.0, "z_depth": 0.0}
    return {
        "x_width": float(band[:, 0].max() - band[:, 0].min()),
        "z_depth": float(band[:, 2].max() - band[:, 2].min()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--body-artifact", default=str(PIPELINE / "sam3d" / "body.ply"))
    parser.add_argument("--output", default=str(PIPELINE / "viewer_hq" / "sam_measurements.json"))
    args = parser.parse_args()

    mesh_path = Path(args.body_artifact)
    vertices = load_ascii_ply_vertices(mesh_path)
    mins = vertices.min(axis=0)
    maxs = vertices.max(axis=0)
    span = maxs - mins
    y_min, y_max = float(mins[1]), float(maxs[1])

    bands = {
        "head": band_span(vertices, y_min, y_max, 0.84, 1.00),
        "shoulder": band_span(vertices, y_min, y_max, 0.68, 0.80),
        "chest": band_span(vertices, y_min, y_max, 0.54, 0.68),
        "waist": band_span(vertices, y_min, y_max, 0.43, 0.54),
        "hip": band_span(vertices, y_min, y_max, 0.34, 0.45),
        "leg": band_span(vertices, y_min, y_max, 0.02, 0.34),
    }
    shoulder_width = max(bands["shoulder"]["x_width"], 1e-6)
    measurements = {
        "generated_at": now_iso(),
        "source_body": relative(mesh_path),
        "vertex_count": int(len(vertices)),
        "bounds": {
            "min": [float(v) for v in mins],
            "max": [float(v) for v in maxs],
            "span": [float(v) for v in span],
        },
        "normalized": {
            "height": 1.0,
            "shoulder_width": float(shoulder_width / max(span[1], 1e-6)),
            "body_depth": float(span[2] / max(span[1], 1e-6)),
            "hip_to_shoulder": float(bands["hip"]["x_width"] / shoulder_width),
            "waist_to_shoulder": float(bands["waist"]["x_width"] / shoulder_width),
        },
        "bands": bands,
        "usage_note": "Used to size neutral front/side/back mannequin guides. SAM controls proportions; final viewer quality is produced by VTON/diffusion/refinement and best-pick.",
    }
    output = Path(args.output)
    ensure_dir(output.parent)
    write_json(output, measurements)
    print("status=success")
    print(f"measurements={relative(output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
