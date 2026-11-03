# Media Processor

Processes media files (audio, video, images) with AI providers through MCP servers.
Each task is a **processor** that the user runs as a skill, e.g. `/transcribe`. Claude
runs the steps; small Python scripts do the local media work with FFmpeg.

## Rules

- Paid tools are listed under `ask` in `.claude/settings.json`. Use one only inside the
  skill that needs it, once per planned request, in order, never in parallel, and never
  retry a failed call.
- Tools under `deny` must never be used, and no provider may be reached by curl, a REST
  API or an SDK as a fallback.
- Results may be private. Do not open files in `output/` or `work/` unless the user asks.
- Never read or print `.env`.
- Never change a processor's original result. Derived work the user asks for (a
  translation, a summary) goes into a new file next to it.

## Layout and naming

| Path                                  | Contents                                                                          |
| ------------------------------------- | --------------------------------------------------------------------------------- |
| `input/`                              | media files from the user (any type)                                              |
| `work/<processor>/<name>-<time>/`     | temporary files for one job; the only place MCP servers may read                  |
| `output/<processor>/<name>-<hash8>/`  | results for one source file (hash = first 8 of its SHA-256)                       |
| `processors/<processor>/`             | that processor's scripts, usually `prepare.py` and `finalize.py`                  |
| `.claude/skills/<processor>/SKILL.md` | the skill the user runs, same name as the processor                               |
| `lib/media.py`                        | shared FFmpeg/ffprobe helpers (probe, audio tracks, extraction, loudness, pauses) |
| `lib/workspace.py`                    | shared paths, hashing, safe file writing, `.env` reading                          |
| `servers/<provider>.py`               | starts one provider's MCP server; registered in `.mcp.json`                       |
| `scripts/`                            | repo utilities such as `check_setup.py`                                           |

Processor names are verbs or verb-object pairs in kebab case (`transcribe`,
`enhance-audio`, `describe-image`).

## Adding a processor

1. `processors/<name>/` with the scripts. Reuse `lib/`; put helpers that a second
   processor could use into `lib/` instead of the processor folder.
2. `.claude/skills/<name>/SKILL.md` with `disable-model-invocation: true` if it costs money.
3. In `.claude/settings.json`: `allow` its scripts, `ask` its paid tools.
4. A new provider also needs `servers/<provider>.py`, an entry in `.mcp.json`, its
   paid tools in `ask`/`deny`, its key in `.env.example` and a check in
   `scripts/check_setup.py`.
5. A row in the README's processor table.
