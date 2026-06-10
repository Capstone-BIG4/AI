from __future__ import annotations

from pathlib import Path
from typing import Any

from pipeline_common import ROOT, read_json


def collect_paths(value: Any) -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"path", "body_metadata", "native_output", "exported_body_artifact", "source_output_schema", "base_candidate", "source_reference"} and isinstance(item, str):
                paths.append(item)
            else:
                paths.extend(collect_paths(item))
    elif isinstance(value, list):
        for item in value:
            paths.extend(collect_paths(item))
    return paths


def main() -> int:
    manifest = read_json(ROOT / "assets" / "manifest.json")
    missing = []
    for path in sorted(set(collect_paths(manifest))):
        if path.startswith("http://") or path.startswith("https://"):
            continue
        if not (ROOT / path).exists():
            missing.append(path)
    if missing:
        for path in missing:
            print(f"missing={path}")
        return 1
    print("status=success")
    print("checked_manifest_paths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
