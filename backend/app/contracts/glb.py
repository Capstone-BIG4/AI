"""Small GLB writer for generated mesh contracts."""

from __future__ import annotations

import json
import math
import struct
from pathlib import Path
from typing import Iterable, Sequence


Vec3 = tuple[float, float, float]
Vec2 = tuple[float, float]
Face = tuple[int, int, int]


def write_mesh_glb(
    path: str | Path,
    vertices: Iterable[Sequence[float]],
    faces: Iterable[Sequence[int]],
    *,
    name: str = "Mesh",
    base_color: Sequence[float] = (0.82, 0.78, 0.72, 1.0),
    roughness: float = 0.9,
    texcoords: Iterable[Sequence[float]] | None = None,
    texture_uri: str | None = None,
    double_sided: bool = False,
) -> None:
    """Write a minimal binary glTF mesh."""

    vertex_list: list[Vec3] = [tuple(map(float, vertex[:3])) for vertex in vertices]
    face_list: list[Face] = [tuple(map(int, face[:3])) for face in faces]
    texcoord_list: list[Vec2] | None = None
    if texcoords is not None:
        texcoord_list = [tuple(map(float, uv[:2])) for uv in texcoords]
        if len(texcoord_list) != len(vertex_list):
            raise ValueError("texcoords length must match vertices length")
    if not vertex_list:
        raise ValueError("vertices must not be empty")
    if not face_list:
        raise ValueError("faces must not be empty")

    glb = build_mesh_glb(
        vertex_list,
        face_list,
        name=name,
        base_color=base_color,
        roughness=roughness,
        texcoords=texcoord_list,
        texture_uri=texture_uri,
        double_sided=double_sided,
    )
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(glb)


def build_mesh_glb(
    vertices: list[Vec3],
    faces: list[Face],
    *,
    name: str,
    base_color: Sequence[float],
    roughness: float,
    texcoords: list[Vec2] | None = None,
    texture_uri: str | None = None,
    double_sided: bool = False,
) -> bytes:
    if texcoords is not None and len(texcoords) != len(vertices):
        raise ValueError("texcoords length must match vertices length")

    flat_indices = [index for face in faces for index in face]
    max_index = max(flat_indices)
    if max_index >= len(vertices):
        raise ValueError("face index out of range")

    position_bytes = b"".join(struct.pack("<fff", *vertex) for vertex in vertices)
    normal_list = _compute_vertex_normals(vertices, faces)
    normal_bytes = b"".join(struct.pack("<fff", *normal) for normal in normal_list)
    texcoord_bytes = (
        b"".join(struct.pack("<ff", *uv) for uv in texcoords)
        if texcoords is not None
        else b""
    )

    if max_index <= 65535:
        component_type = 5123
        index_bytes = b"".join(struct.pack("<H", index) for index in flat_indices)
    else:
        component_type = 5125
        index_bytes = b"".join(struct.pack("<I", index) for index in flat_indices)

    bin_parts: list[bytes] = []
    buffer_views: list[dict[str, int]] = []

    def append_buffer_view(data: bytes, *, target: int) -> int:
        current_length = sum(len(part) for part in bin_parts)
        bin_parts.append(b"\x00" * _padding(current_length, multiple=4))
        byte_offset = sum(len(part) for part in bin_parts)
        bin_parts.append(data)
        view_index = len(buffer_views)
        buffer_views.append(
            {
                "buffer": 0,
                "byteOffset": byte_offset,
                "byteLength": len(data),
                "target": target,
            }
        )
        return view_index

    position_view = append_buffer_view(position_bytes, target=34962)
    normal_view = append_buffer_view(normal_bytes, target=34962)
    texcoord_view = (
        append_buffer_view(texcoord_bytes, target=34962) if texcoord_bytes else None
    )
    index_view = append_buffer_view(index_bytes, target=34963)

    bin_blob = b"".join(bin_parts)
    bin_blob += b"\x00" * _padding(len(bin_blob), multiple=4)

    mins = [min(vertex[axis] for vertex in vertices) for axis in range(3)]
    maxs = [max(vertex[axis] for vertex in vertices) for axis in range(3)]
    uv_mins = (
        [min(uv[axis] for uv in texcoords) for axis in range(2)]
        if texcoords is not None
        else None
    )
    uv_maxs = (
        [max(uv[axis] for uv in texcoords) for axis in range(2)]
        if texcoords is not None
        else None
    )

    pbr = {
        "baseColorFactor": list(base_color),
        "metallicFactor": 0.0,
        "roughnessFactor": roughness,
    }
    if texture_uri:
        pbr["baseColorTexture"] = {"index": 0}

    attributes = {"POSITION": 0, "NORMAL": 1}
    accessors = [
        {
            "bufferView": position_view,
            "componentType": 5126,
            "count": len(vertices),
            "type": "VEC3",
            "min": mins,
            "max": maxs,
        },
        {
            "bufferView": normal_view,
            "componentType": 5126,
            "count": len(vertices),
            "type": "VEC3",
        },
    ]
    if texcoord_view is not None and uv_mins is not None and uv_maxs is not None:
        attributes["TEXCOORD_0"] = len(accessors)
        accessors.append(
            {
                "bufferView": texcoord_view,
                "componentType": 5126,
                "count": len(vertices),
                "type": "VEC2",
                "min": uv_mins,
                "max": uv_maxs,
            }
        )
    index_accessor = len(accessors)
    accessors.append(
        {
            "bufferView": index_view,
            "componentType": component_type,
            "count": len(flat_indices),
            "type": "SCALAR",
        }
    )

    gltf = {
        "asset": {"version": "2.0", "generator": "capstone-mesh-contract"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"name": name, "mesh": 0}],
        "materials": [
            {
                "name": f"{name}_material",
                "pbrMetallicRoughness": pbr,
                "doubleSided": double_sided,
                "alphaMode": "OPAQUE",
            }
        ],
        "meshes": [
            {
                "name": f"{name}Mesh",
                "primitives": [
                    {
                        "attributes": attributes,
                        "indices": index_accessor,
                        "material": 0,
                    }
                ],
            }
        ],
        "buffers": [{"byteLength": len(bin_blob)}],
        "bufferViews": buffer_views,
        "accessors": accessors,
    }
    if texture_uri:
        gltf["images"] = [{"uri": texture_uri}]
        gltf["samplers"] = [
            {
                "magFilter": 9729,
                "minFilter": 9987,
                "wrapS": 33071,
                "wrapT": 33071,
            }
        ]
        gltf["textures"] = [{"sampler": 0, "source": 0}]

    json_blob = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    json_blob += b" " * _padding(len(json_blob), multiple=4)

    total_length = 12 + 8 + len(json_blob) + 8 + len(bin_blob)
    header = struct.pack("<III", 0x46546C67, 2, total_length)
    json_chunk_header = struct.pack("<II", len(json_blob), 0x4E4F534A)
    bin_chunk_header = struct.pack("<II", len(bin_blob), 0x004E4942)
    return header + json_chunk_header + json_blob + bin_chunk_header + bin_blob


def _padding(length: int, *, multiple: int) -> int:
    return (multiple - (length % multiple)) % multiple


def _compute_vertex_normals(vertices: list[Vec3], faces: list[Face]) -> list[Vec3]:
    normals = [[0.0, 0.0, 0.0] for _ in vertices]
    for a_idx, b_idx, c_idx in faces:
        ax, ay, az = vertices[a_idx]
        bx, by, bz = vertices[b_idx]
        cx, cy, cz = vertices[c_idx]
        ux, uy, uz = bx - ax, by - ay, bz - az
        vx, vy, vz = cx - ax, cy - ay, cz - az
        nx = uy * vz - uz * vy
        ny = uz * vx - ux * vz
        nz = ux * vy - uy * vx
        for index in (a_idx, b_idx, c_idx):
            normals[index][0] += nx
            normals[index][1] += ny
            normals[index][2] += nz

    result: list[Vec3] = []
    for nx, ny, nz in normals:
        length = math.sqrt(nx * nx + ny * ny + nz * nz)
        if length == 0:
            result.append((0.0, 1.0, 0.0))
        else:
            result.append((nx / length, ny / length, nz / length))
    return result
