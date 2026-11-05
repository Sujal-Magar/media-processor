#!/usr/bin/env python3
"""Check that the tools and keys the processors need are installed. Costs nothing.

With an OpenAI key present, it also asks OpenAI whether the key can use the vision model
(and the topic model, if set apart; a free model lookup, no generation).
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root, for `lib`

from lib.openai_api import (
    DEFAULT_VISION_MODEL,
    OpenAIError,
    request,
    setting,
    topic_model,
)
from lib.workspace import WORK, dotenv_value


def key_source(name: str) -> str | None:
    if os.environ.get(name, "").strip():
        return "shell environment"
    if dotenv_value(name):
        return ".env file"
    return None


def key_check(name: str, needed_by: str) -> tuple[str, bool, str]:
    source = key_source(name)
    return (
        name,
        source is not None,
        f"found in {source}" if source else f"not set ({needed_by})",
    )


def openai_model_check(model: str, name: str) -> tuple[str, bool, str]:
    try:
        request("GET", f"/models/{model}", timeout=15)
    except OpenAIError as exc:
        return name, False, f"{model}: {exc.code} {exc.message[:80]}"
    return name, True, f"{model} usable with this key"


def tool_check(name: str, hint: str) -> tuple[str, bool, str]:
    path = shutil.which(name)
    return name, path is not None, path or hint


def main() -> None:
    checks = [
        ("python 3.10+", sys.version_info >= (3, 10), sys.version.split()[0]),
        tool_check("ffmpeg", "sudo pacman -S ffmpeg"),
        tool_check("ffprobe", "comes with ffmpeg"),
        tool_check("uvx", "sudo pacman -S uv"),
        ("work/ writable", os.access(WORK, os.W_OK), str(WORK)),
        key_check("ELEVENLABS_API_KEY", "needed by /transcribe"),
        key_check("OPENAI_API_KEY", "needed by /tag-visuals and /tag-topics"),
    ]
    if key_source("OPENAI_API_KEY"):
        vision = (
            setting("OPENAI_VISION_MODEL", DEFAULT_VISION_MODEL) or DEFAULT_VISION_MODEL
        )
        checks.append(openai_model_check(vision, "OpenAI model access"))
        if topic_model() != vision:
            checks.append(openai_model_check(topic_model(), "OpenAI topic model"))
    for name, ok, detail in checks:
        print(f"{'ok  ' if ok else 'FAIL'}  {name:<20} {detail}")
    sys.exit(0 if all(ok for _, ok, _ in checks) else 1)


if __name__ == "__main__":
    main()
