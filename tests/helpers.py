"""Shared test setup: the repo root on sys.path, and loading processor scripts."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SCRIPT_NAMES = ("prepare", "tag", "generate", "finalize")


def load_script(processor: str, name: str) -> ModuleType:
    """processors/<processor>/<name>.py as a fresh module. The scripts import each other
    by bare name (`from finalize import ...`), so those names are cleared first, or one
    processor's finalize would stand in for another's."""
    folder = ROOT / "processors" / processor
    for script in SCRIPT_NAMES:
        sys.modules.pop(script, None)
    sys.path.insert(0, str(folder))
    try:
        spec = importlib.util.spec_from_file_location(
            f"{processor.replace('-', '_')}_{name}", folder / f"{name}.py"
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(folder))
    return module
