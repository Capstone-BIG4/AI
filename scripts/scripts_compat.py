from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parent


def import_from_scripts_dir(module_stem: str):
    path = SCRIPTS_DIR / f"{module_stem}.py"
    spec = importlib.util.spec_from_file_location(module_stem, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load script module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
