#!/usr/bin/env python3
"""Start the official ElevenLabs MCP server for this repo (run by .mcp.json, not by hand).

- Takes ELEVENLABS_API_KEY from the shell, or from .env if the shell has none.
- Lets the server read and write only inside work/ (its ELEVENLABS_MCP_BASE_PATH).
- Output mode "files": results are saved to disk instead of being returned to Claude.
- The pinned version always sends model scribe_v2 with request logging on, so ElevenLabs
  keeps what it receives; see the STT_* constants.

stdout belongs to the MCP protocol, so messages go to stderr only.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root, for `lib`

from lib.workspace import WORK, dotenv_value

# The skills were written against this version's tool parameters; bump deliberately.
PACKAGE = "elevenlabs-mcp==0.12.2"
# What this version's speech_to_text hard-codes (server.py, speech_to_text). The tool can't
# change them, so transcribe/finalize.py records them. Re-check when bumping PACKAGE.
STT_MODEL = "scribe_v2"
STT_LOGGING = True  # ElevenLabs keeps the request (no zero retention)
STT_AUDIO_EVENTS = True  # sounds such as (laughter) are written into the text


def main() -> None:
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip() or dotenv_value(
        "ELEVENLABS_API_KEY"
    )
    if not key:
        print("ELEVENLABS_API_KEY is not set; add it to .env", file=sys.stderr)
        sys.exit(1)
    env = {
        **os.environ,
        "ELEVENLABS_API_KEY": key,
        "ELEVENLABS_MCP_BASE_PATH": str(WORK),
        "ELEVENLABS_MCP_OUTPUT_MODE": "files",
    }
    WORK.mkdir(exist_ok=True)
    os.chdir(WORK)
    try:
        os.execvpe("uvx", ["uvx", "--from", PACKAGE, "elevenlabs-mcp"], env)
    except FileNotFoundError:
        print("uvx is not installed (sudo pacman -S uv)", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
