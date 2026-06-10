from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
from PIL import Image

from pipeline_common import PIPELINE, ensure_dir, now_iso, read_json, relative, write_json


def load_ply(path: Path) -> tuple[np.ndarray, np.ndarray]:
    lines = path.read_text(encoding="ascii", errors="replace").splitlines()
    if not lines or lines[0] != "ply":
        raise ValueError("Only ASCII PLY is supported by this lightweight renderer")
    vertex_count = face_count = None
    header_end = None
    for idx, line in enumerate(lines):
        parts = line.split()
        if len(parts) == 3 and parts[:2] == ["element", "vertex"]:
            vertex_count = int(parts[2])
        elif len(parts) == 3 and parts[:2] == ["element", "face"]:
            face_count = int(parts[2])
        elif line == "end_header":
            header_end = idx + 1
            break
    if vertex_count is None or face_count is None or header_end is None:
        raise ValueError("Invalid PLY header")
    vertices = []
    for line in lines[header_end : header_end + vertex_count]:
        x, y, z = line.split()[:3]
        vertices.append([float(x), float(y), float(z)])
    faces = []
    for line in lines[header_end + vertex_count : header_end + vertex_count + face_count]:
        parts = line.split()
        if int(parts[0]) < 3:
            continue
        faces.append([int(parts[1]), int(parts[2]), int(parts[3])])
    return np.asarray(vertices, dtype=np.float32), np.asarray(faces, dtype=np.int64)


def load_obj(path: Path) -> tuple[np.ndarray, np.ndarray]:
    vertices = []
    faces = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("v "):
            _, x, y, z, *_ = line.split()
            vertices.append([float(x), float(y), float(z)])
        elif line.startswith("f "):
            idxs = []
            for token in line.split()[1:4]:
                idxs.append(int(token.split("/")[0]) - 1)
            if len(idxs) == 3:
                faces.append(idxs)
    return np.asarray(vertices, dtype=np.float32), np.asarray(faces, dtype=np.int64)


def load_mesh(path: Path) -> tuple[np.ndarray, np.ndarray]:
    if path.suffix.lower() == ".ply":
        return load_ply(path)
    if path.suffix.lower() == ".obj":
        return load_obj(path)
    raise ValueError(f"Unsupported mesh format for lightweight renderer: {path.suffix}")


def rotate_y(vertices: np.ndarray, degrees: float) -> np.ndarray:
    theta = math.radians(degrees)
    c, s = math.cos(theta), math.sin(theta)
    rot = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], dtype=np.float32)
    return vertices @ rot.T


def normalize_view(vertices: np.ndarray, size: int, padding: float = 0.12) -> np.ndarray:
    v = vertices.copy()
    center = (v.max(axis=0) + v.min(axis=0)) / 2
    v -= center
    span = max(float(v[:, 0].max() - v[:, 0].min()), float(v[:, 1].max() - v[:, 1].min()), 1e-6)
    scale = (size * (1 - 2 * padding)) / span
    xy = v[:, [0, 1]] * scale
    x = xy[:, 0] + size / 2
    y = size / 2 + xy[:, 1]
    z = v[:, 2]
    return np.column_stack([x, y, z]).astype(np.float32)


def barycentric(px: float, py: float, tri: np.ndarray):
    x0, y0 = tri[0, 0], tri[0, 1]
    x1, y1 = tri[1, 0], tri[1, 1]
    x2, y2 = tri[2, 0], tri[2, 1]
    den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
    if abs(den) < 1e-8:
        return None
    a = ((y1 - y2) * (px - x2) + (x2 - x1) * (py - y2)) / den
    b = ((y2 - y0) * (px - x2) + (x0 - x2) * (py - y2)) / den
    c = 1 - a - b
    if a < -1e-4 or b < -1e-4 or c < -1e-4:
        return None
    return a, b, c


def render(vertices: np.ndarray, faces: np.ndarray, yaw: float, size: int) -> dict[str, Image.Image]:
    world = rotate_y(vertices, yaw)
    screen = normalize_view(world, size)
    zbuf = np.full((size, size), np.inf, dtype=np.float32)
    silhouette = np.zeros((size, size), dtype=np.uint8)
    normal = np.zeros((size, size, 3), dtype=np.float32)

    view_faces = world[faces]
    normals = np.cross(view_faces[:, 1] - view_faces[:, 0], view_faces[:, 2] - view_faces[:, 0])
    norms = np.linalg.norm(normals, axis=1, keepdims=True)
    normals = normals / np.maximum(norms, 1e-8)

    for face_idx, face in enumerate(faces):
        tri = screen[face]
        min_x = max(0, int(np.floor(tri[:, 0].min())))
        max_x = min(size - 1, int(np.ceil(tri[:, 0].max())))
        min_y = max(0, int(np.floor(tri[:, 1].min())))
        max_y = min(size - 1, int(np.ceil(tri[:, 1].max())))
        if min_x > max_x or min_y > max_y:
            continue
        for yy in range(min_y, max_y + 1):
            for xx in range(min_x, max_x + 1):
                bc = barycentric(xx + 0.5, yy + 0.5, tri)
                if bc is None:
                    continue
                a, b, c = bc
                z = a * tri[0, 2] + b * tri[1, 2] + c * tri[2, 2]
                if z < zbuf[yy, xx]:
                    zbuf[yy, xx] = z
                    silhouette[yy, xx] = 255
                    normal[yy, xx] = normals[face_idx]

    valid = silhouette > 0
    depth = np.zeros((size, size), dtype=np.uint8)
    if np.any(valid):
        z = zbuf[valid]
        z_norm = (z - z.min()) / max(float(z.max() - z.min()), 1e-6)
        depth[valid] = (255 * (1 - z_norm)).astype(np.uint8)
    normal_rgb = ((normal + 1) * 127.5).clip(0, 255).astype(np.uint8)
    normal_rgb[~valid] = 0

    # Coarse body-region map from vertical screen position. This is not DensePose.
    part = np.zeros((size, size, 3), dtype=np.uint8)
    yy = np.indices((size, size))[0]
    part[(valid) & (yy < size * 0.18)] = [210, 210, 210]
    part[(valid) & (yy >= size * 0.18) & (yy < size * 0.48)] = [20, 120, 220]
    part[(valid) & (yy >= size * 0.48) & (yy < size * 0.62)] = [30, 180, 120]
    part[(valid) & (yy >= size * 0.62)] = [220, 180, 60]

    return {
        "silhouette": Image.fromarray(silhouette),
        "depth": Image.fromarray(depth),
        "normal": Image.fromarray(normal_rgb),
        "coarse_part_map": Image.fromarray(part),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--body-artifact", default=str(PIPELINE / "sam3d" / "body.ply"))
    parser.add_argument("--output-dir", default=str(PIPELINE / "guides"))
    parser.add_argument("--size", type=int, default=1024)
    args = parser.parse_args()

    mesh_path = Path(args.body_artifact)
    out_dir = ensure_dir(Path(args.output_dir))
    vertices, faces = load_mesh(mesh_path)
    views = {"front": 0.0, "side": 90.0, "back": 180.0}
    outputs = {}
    for view, yaw in views.items():
        rendered = render(vertices, faces, yaw=yaw, size=args.size)
        outputs[view] = {}
        for kind, image in rendered.items():
            path = out_dir / f"{view}_{kind}.png"
            image.save(path)
            outputs[view][kind] = relative(path)

    body_meta_path = PIPELINE / "sam3d" / "body_metadata.json"
    body_meta = read_json(body_meta_path) if body_meta_path.exists() else {}
    metadata = {
        "generated_at": now_iso(),
        "renderer": "lightweight_python_orthographic_rasterizer",
        "body_artifact": relative(mesh_path),
        "native_sam_output": body_meta.get("native_output_path"),
        "source_output_schema": body_meta.get("source_output_schema_path"),
        "resolution": [args.size, args.size],
        "views": views,
        "outputs": outputs,
        "part_map_note": "coarse_part_map is a vertical anatomical region map, not DensePose.",
    }
    write_json(out_dir / "guide_metadata.json", metadata)
    print("status=success")
    print("guide_metadata=assets/pipeline/guides/guide_metadata.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
