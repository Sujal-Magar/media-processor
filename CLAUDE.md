# Media Processor

Processes media files (audio, video, images) with AI providers. Each task is a
**processor** that the user runs as a skill, e.g. `/transcribe` or `/tag-visuals`;
**pipeline skills** such as `/process-video` run several processors on one file. Claude
runs the steps; small Python scripts do the local media work with FFmpeg.

## Rules

- Paid steps are listed under `ask` in `.claude/settings.json` (MCP tools and the scripts
  that call a paid API). Run one only inside the skill that needs it, as often as its plan
  says, and never retry a failed paid step.
- Providers are reached only the way the processor defines: ElevenLabs through its MCP
  server, OpenAI through `processors/tag-visuals/tag.py` and
  `processors/tag-topics/tag.py`. Never improvise another route (curl, an SDK, a
  different tool), and never use tools under `deny`.
- Results may be private. Do not open files in `output/` or `work/` unless the user asks.
- Never read or print `.env`.
- Never change a processor's original result. Derived work the user asks for (a
  translation, a summary) goes into a new file next to it.

## Layout and naming

| Path                                  | Contents                                                                                                     |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| `input/`                              | media files from the user (any type)                                                                         |
| `work/<processor>/<name>-<time>/`     | temporary files for one job; the only place MCP servers may read                                             |
| `output/<processor>/<name>-<hash8>/`  | results for one source file (hash = first 8 of its SHA-256)                                                  |
| `output/.../<name>-<hash8>/history/`  | earlier results that `force` replaced, one `<time>/` folder each                                             |
| `processors/<processor>/`             | that processor's scripts, usually `prepare.py`, a paid step, `finalize.py`                                   |
| `.claude/skills/<processor>/SKILL.md` | the skill the user runs, same name as the processor                                                          |
| `.claude/skills/<pipeline>/SKILL.md`  | a pipeline skill: runs processors by following their skills                                                  |
| `lib/media.py`                        | shared FFmpeg/ffprobe helpers (probe, picture size, audio tracks and channels, extraction, loudness, pauses) |
| `lib/workspace.py`                    | shared paths, hashing, safe file writing, result history, `.env` reading                                     |
| `lib/tags.py`                         | tag wording (English, lowercase, hyphens) and tag libraries rebuilt from results                             |
| `lib/<provider>_api.py`               | client for a provider without an official MCP server (`openai_api.py`, with its cost estimate)               |
| `servers/<provider>.py`               | starts one provider's MCP server; registered in `.mcp.json`                                                  |
| `scripts/`                            | repo utilities such as `check_setup.py`                                                                      |

Visual tags are free-form. Their shared vocabulary is rebuilt from
`output/tag-visuals/*/tags.json` on every run, so one folder is one tag library: keep
each organisation in its own copy of this folder (the Pulse PRD requires per-client data
isolation). Tags new to the library are marked `new`; read on-screen text must be
confirmed against the frame before anyone relies on it. Every tag is English,
lowercase, with words joined by hyphens (`speaking-to-camera`); `lib/tags.py` cleans
labels, also those in results saved before this rule.

Topic tags (`tag-topics`: type, topic, entity) come from a file's transcript, visual tags
and on-screen text in one text request; each cites its evidence, and none names a
person. Their library is `output/tag-topics/*/topics.json`, rebuilt the same way.

Processor names are verbs or verb-object pairs in kebab case (`transcribe`,
`tag-visuals`, `enhance-audio`). Pipeline skills are named `process-<content>`
(`process-video`).

## Adding a processor

1. `processors/<name>/` with the scripts. Reuse `lib/`; put helpers that a second
   processor could use into `lib/` instead of the processor folder.
2. `.claude/skills/<name>/SKILL.md` with `disable-model-invocation: true` if it costs money.
3. In `.claude/settings.json`: `allow` its free scripts, `ask` its paid tools or scripts.
4. A new provider also needs its key in `.env.example` and a check in
   `scripts/check_setup.py`, plus either `servers/<provider>.py` and an entry in
   `.mcp.json` (official MCP server, other paid tools under `deny`) or
   `lib/<provider>_api.py` (official API, when no official MCP server exists).
5. A row in the README's processor table, and the processor in any pipeline skill that
   should run it.
