#!/usr/bin/env python3
"""Check that the tools and keys the processors need are installed. Costs nothing."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root, for `lib`

from lib.workspace import WORK, dotenv_value  # noqa: E402


def key_source(name: str) -> str | None:
    if os.environ.get(name, "").strip():
        return "shell environment"
    if dotenv_value(name):
        return ".env file"
    return None


def main() -> None:
    elevenlabs_key = key_source("ELEVENLABS_API_KEY")
    checks = [
        ("python 3.10+", sys.version_info >= (3, 10), sys.version.split()[0]),
        (
            "ffmpeg",
            bool(shutil.which("ffmpeg")),
            shutil.which("ffmpeg") or "sudo pacman -S ffmpeg",
        ),
        (
            "ffprobe",
            bool(shutil.which("ffprobe")),
            shutil.which("ffprobe") or "comes with ffmpeg",
        ),
        ("uvx", bool(shutil.which("uvx")), shutil.which("uvx") or "sudo pacman -S uv"),
        (
            "ELEVENLABS_API_KEY",
            elevenlabs_key is not None,
            f"found in {elevenlabs_key}" if elevenlabs_key else "not set",
        ),
        ("work/ writable", os.access(WORK, os.W_OK), str(WORK)),
    ]
    for name, ok, detail in checks:
        print(f"{'ok  ' if ok else 'FAIL'}  {name:<20} {detail}")
    sys.exit(0 if all(ok for _, ok, _ in checks) else 1)


if __name__ == "__main__":
    main()
