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
  server, OpenAI through `processors/tag-visuals/tag.py`,
  `processors/tag-topics/tag.py`, `processors/generate-copy/generate.py` and
  `processors/draft-report/draft.py`. Never improvise another route (curl, an SDK, a
  different tool), and never use tools under `deny`.
- Results may be private. Do not open files in `output/` or `work/` unless the user asks.
- Never read or print `.env`.
- Never change a processor's original result. Derived work the user asks for (a
  translation, a summary) goes into a new file next to it.

## Layout and naming

| Path                                  | Contents                                                                                                     |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| `input/`                              | media files from the user (any type)                                                                         |
| `input/reports/<YYYY-MM>.json`        | one month's numbers for `draft-report` (mock Pulse analytics; shape in `fixtures/`)                          |
| `fixtures/`                           | example inputs in git, such as `report-input.example.json`                                                   |
| `work/<processor>/<name>-<time>/`     | temporary files for one job; the only place MCP servers may read                                             |
| `output/<processor>/<name>-<hash8>/`  | results for one source file (hash = first 8 of its SHA-256)                                                  |
| `output/.../<name>-<hash8>/history/`  | earlier results that `force` replaced, one `<time>/` folder each                                             |
| `processors/<processor>/`             | that processor's scripts, usually `prepare.py`, a paid step, `finalize.py`                                   |
| `processors/transcribe/subtitles.py`  | WebVTT/SRT subtitles from a transcript (finalize writes them; `--all` adds them to older transcripts)        |
| `.claude/skills/<processor>/SKILL.md` | the skill the user runs, same name as the processor                                                          |
| `.claude/skills/<pipeline>/SKILL.md`  | a pipeline skill: runs processors by following their skills                                                  |
| `lib/media.py`                        | shared FFmpeg/ffprobe helpers (probe, picture size, audio tracks and channels, extraction, loudness, pauses) |
| `lib/workspace.py`                    | shared paths, hashing, safe file writing, result history, `.env` reading                                     |
| `lib/tags.py`                         | tag wording (English, lowercase, hyphens) and tag libraries rebuilt from results                             |
| `lib/material.py`                     | earlier results (speech, visual tags, on-screen text) as referenced text for a model                         |
| `lib/numbers.py`                      | numbers in model-written text checked against the numbers it was given (48.2K for 48,200)                    |
| `lib/organisation.py`                 | the organisation's own details from `organisation.json` (git-ignored client data; see the example file)      |
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

Copy (`generate-copy`: hooks, an edit script, captions per platform, hashtags, an
optional translation) is drafted from the same material plus the topic tags in one text
request. It is a draft for a person to approve (`review_status: draft`), never
published; hooks and script segments cite the footage they use, and no copy names a
person. The organisation's name is spelled as `organisation.json` gives it, never as
speech-to-text heard it.

A report narrative (`draft-report`, Pulse C17b) is drafted from one month's numbers
(totals and their change, platforms, post snapshots, the Top 3 highlights, the
strategist's plan) plus the topic tags and hook of posts made from a video, in one text
request. It is a draft for the strategist to sign off, never sent. Every sentence cites
its data and every number must be one the data holds; it describes what happened, never
why, and next month's list only rewords the strategist's plan (empty without one).
Strategic insight (C18b) is not part of it.

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
