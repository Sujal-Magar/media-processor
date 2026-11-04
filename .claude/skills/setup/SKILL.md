---
name: setup
description: Check that ffmpeg, uvx, the API keys and the providers the processors use (ElevenLabs MCP server, OpenAI vision model) are ready. Free; use when the user asks whether things are set up or when provider tools are missing.
---

# Setup check

Nothing here costs money.

1. Run `python3 scripts/check_setup.py` and show its output. For each `FAIL`, give the fix:
   - ffmpeg/ffprobe: `sudo pacman -S ffmpeg`
   - uvx: `sudo pacman -S uv`
   - ELEVENLABS_API_KEY: `cp .env.example .env`, then put the key from
     https://elevenlabs.io/app/settings/api-keys after `ELEVENLABS_API_KEY=`. Do not ask the
     user to paste the key into the chat, and never read `.env`.
   - OPENAI_API_KEY: the same, with a key from https://platform.openai.com/api-keys after
     `OPENAI_API_KEY=`.
   - OpenAI model access: the script asked OpenAI (free) whether the key can use the
     vision model. `invalid_api_key` = wrong key; `model_not_found` = set
     `OPENAI_VISION_MODEL` in `.env` to a model the key can use.

2. Check that the `mcp__elevenlabs__*` tools are available. If they are not:
   - the key may be missing (step 1), or the server failed to start;
   - tell the user to run `/mcp` to see the server status, and to restart Claude Code after
     adding the key;
   - the first start downloads the server with uvx and can take a minute.

3. If the tools are available, list the key's permissions. ElevenLabs has no tool that
   lists them, so try each free, read-only tool below once and judge by the answer:

   | Permission (ElevenLabs key settings) | Free probe                            | Call with                                                |
   | ------------------------------------ | ------------------------------------- | -------------------------------------------------------- |
   | User: read (plan and usage)          | `mcp__elevenlabs__check_subscription` | nothing                                                  |
   | Models: read                         | `mcp__elevenlabs__list_models`        | nothing                                                  |
   | Voices: read                         | `mcp__elevenlabs__search_voices`      | `search: "zz-permission-probe"` (keeps the answer empty) |
   | ElevenLabs Agents: read              | `mcp__elevenlabs__list_agents`        | nothing                                                  |
   - Any normal answer: `granted`. Do not repeat the content of the answer, except for
     `check_subscription`: report the plan (`tier`), `status`, and characters used out of
     the limit.
   - `missing_permissions`: `missing`. The error names the permission ("missing the
     permission user_read"); show that name.
   - `invalid_api_key`: the key itself is wrong. Stop probing and say so.
   - Anything else (network, rate limit): `unknown`, with the short reason.

   Then add these rows, which cannot be probed without a paid request:

   | Permission     | Needed by     | Status                                                                                                                                |
   | -------------- | ------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
   | Speech to Text | `/transcribe` | `not checkable for free`: if it is missing, the first `/transcribe` request is refused before any work is done, so nothing is charged |

   Show one table with every permission and its status. Never call a paid tool to test a
   permission. To change permissions: https://elevenlabs.io/app/settings/api-keys, edit the
   key, then restart Claude Code. Only Speech to Text is required; the read permissions just
   make `/setup` more informative.

End with one line each for `/transcribe` (ElevenLabs key and MCP tools), `/tag-visuals`
(OpenAI key and model access) and `/process-video` (both): ready, or what is missing.
