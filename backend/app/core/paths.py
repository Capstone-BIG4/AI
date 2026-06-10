from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
FRONTEND = ROOT / "frontend"
ASSETS = ROOT / "assets"
DOCS = ROOT / "docs"
RUNTIME = ROOT / "runtime"
UPLOADS = RUNTIME / "uploads"


def project_path(path: str) -> Path:
    return ROOT / path.lstrip("/")
