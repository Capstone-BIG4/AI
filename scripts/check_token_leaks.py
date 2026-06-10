from __future__ import annotations

from pathlib import Path

from pipeline_common import ROOT, read_env_keys


SCAN_DIRS = ["assets", "docs", "scripts", ".omx/plans"]
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".pt", ".npy", ".npz", ".ply", ".pdf"}


def main() -> int:
    token = read_env_keys().get("HF_TOKEN", "")
    if not token:
        print("status=skipped")
        print("reason=HF_TOKEN not present")
        return 0
    hits = []
    for rel in SCAN_DIRS:
        base = ROOT / rel
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() in SKIP_SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if token in text:
                hits.append(str(path.relative_to(ROOT)))
    if hits:
        for path in hits:
            print(f"token_leak={path}")
        return 1
    print("status=success")
    print("token_leak_hits=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
