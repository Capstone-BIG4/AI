from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import numpy as np

from pipeline_common import PIPELINE, ensure_dir, now_iso, read_json, relative, write_json


VERTEX_KEYS = {"pred_vertices", "vertices", "verts", "mesh_vertices"}
FACE_KEYS = {"faces", "pred_faces", "mesh_faces"}


def load_native(path: Path) -> Any:
    if path.suffix == ".pt":
        import torch

        return torch.load(path, map_location="cpu", weights_only=False)
    if path.suffix == ".npz":
        data = np.load(path, allow_pickle=True)
        if "outputs" in data:
            return data["outputs"][0]
        return {key: data[key] for key in data.files}
    raise ValueError(f"Unsupported native output: {path}")


def as_numpy(value: Any) -> np.ndarray | None:
    if value is None:
        return None
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    arr = np.asarray(value)
    if arr.dtype == object:
        return None
    return arr


def recursive_find(value: Any, keys: set[str]) -> tuple[str, np.ndarray] | None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key) in keys:
                arr = as_numpy(item)
                if arr is not None:
                    return str(key), arr
        for key, item in value.items():
            found = recursive_find(item, keys)
            if found:
                return f"{key}.{found[0]}", found[1]
    elif isinstance(value, (list, tuple)):
        for idx, item in enumerate(value):
            found = recursive_find(item, keys)
            if found:
                return f"{idx}.{found[0]}", found[1]
    return None


def normalize_vertices(vertices: np.ndarray) -> np.ndarray:
    vertices = np.asarray(vertices, dtype=np.float32)
    vertices = np.squeeze(vertices)
    if vertices.ndim == 3:
        vertices = vertices[0]
    if vertices.ndim != 2 or vertices.shape[1] != 3:
        raise ValueError(f"Unsupported vertices shape: {vertices.shape}")
    return vertices


def normalize_faces(faces: np.ndarray) -> np.ndarray:
    faces = np.asarray(faces, dtype=np.int64)
    faces = np.squeeze(faces)
    if faces.ndim == 3:
        faces = faces[0]
    if faces.ndim != 2 or faces.shape[1] < 3:
        raise ValueError(f"Unsupported faces shape: {faces.shape}")
    return faces[:, :3]


def write_ply(path: Path, vertices: np.ndarray, faces: np.ndarray) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="ascii") as fh:
        fh.write("ply\nformat ascii 1.0\n")
        fh.write(f"element vertex {len(vertices)}\n")
        fh.write("property float x\nproperty float y\nproperty float z\n")
        fh.write(f"element face {len(faces)}\n")
        fh.write("property list uchar int vertex_indices\n")
        fh.write("end_header\n")
        for x, y, z in vertices:
            fh.write(f"{float(x):.8f} {float(y):.8f} {float(z):.8f}\n")
        for a, b, c in faces:
            fh.write(f"3 {int(a)} {int(b)} {int(c)}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--native-output", default=str(PIPELINE / "sam3d" / "native_output.pt"))
    parser.add_argument("--faces", default=str(PIPELINE / "sam3d" / "estimator_faces.npy"))
    parser.add_argument("--output", default=str(PIPELINE / "sam3d" / "body.ply"))
    args = parser.parse_args()

    native_path = Path(args.native_output)
    out_path = Path(args.output)
    metadata_path = PIPELINE / "sam3d" / "body_metadata.json"
    metadata = read_json(metadata_path) if metadata_path.exists() else {}

    if metadata.get("status") == "blocked" and not native_path.exists():
        print("status=blocked")
        print("reason=SAM native output missing")
        return 2
    outputs = load_native(native_path)
    vertex_found = recursive_find(outputs, VERTEX_KEYS)
    if not vertex_found:
        raise RuntimeError("Could not find vertices in native SAM output")
    vertex_key, vertices = vertex_found
    vertices = normalize_vertices(vertices)

    face_found = recursive_find(outputs, FACE_KEYS)
    face_source = None
    if face_found:
        face_source, faces = face_found
    elif Path(args.faces).exists():
        face_source = relative(Path(args.faces))
        faces = np.load(args.faces)
    else:
        raise RuntimeError("Could not find faces in native output or estimator_faces.npy")
    faces = normalize_faces(faces)

    write_ply(out_path, vertices, faces)
    metadata.update(
        {
            "status": "success",
            "exported_body_artifact": relative(out_path),
            "exported_body_format": out_path.suffix.lstrip("."),
            "native_vertex_key": vertex_key,
            "face_source": face_source,
            "vertex_count": int(len(vertices)),
            "face_count": int(len(faces)),
            "artifact_exported_at": now_iso(),
        }
    )
    write_json(metadata_path, metadata)
    print("status=success")
    print(f"body_artifact={relative(out_path)}")
    print(f"vertices={len(vertices)} faces={len(faces)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
