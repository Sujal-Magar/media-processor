# Content Creation Automation: Media Processor

## Components it currently tackles

- **C06b** Media transcription & visual tagging: `/transcribe`, `/tag-visuals`, `/tag-topics`
- **C09b** Creative copywriting & script generation: `/generate-copy`
- **C17b** Report narrative synthesis: `/draft-report`

## What it is

A repo you open in **Claude Code**. It turns a media file into searchable results and draft social copy:

- `/transcribe`: speech to text with **ElevenLabs** (English, Nepali), with optional speaker labels and timestamps, plus subtitles in WebVTT and SRT (cue times estimated within each part).
- `/tag-visuals`: what is visible (objects, scenes, activities, attributes) and readable on-screen text, with time ranges, using an **OpenAI** vision model.
- `/tag-topics`: what a file is about (type, topics, named things), each tag citing its evidence, from the transcript and visual tags.
- `/generate-copy`: draft copy from the same results: 3–5 hooks, an edit script (soundbites and B-roll with their times), a caption per platform, hashtags and an optional translation (e.g. Nepali).
- `/draft-report`: the narrative of a client's monthly report (headline, three short paragraphs, top post, highlight and tile lines, next month's plan in the client's words) from that month's numbers, each sentence citing its data and every number checked against it. The numbers are mocked until Pulse's analytics exist.
- `/process-video`: runs transcription and visual tagging on one video at the same time, then topics.

## Why it is built this way

| Decision                                                         | Reason                                                                                                                                                                                  |
| ---------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Claude Code skills plus small scripts, instead of an application | A first version was a full Python app (about 5,000 lines). It worked, but took too long to review. Here Claude runs the steps, and standard-library Python does the deterministic work. |
| FFmpeg does all media work locally                               | It is free and predictable: audio extraction, silence detection, splitting at pauses, frame sampling. Providers only receive prepared audio or frames, never the originals.             |
| ElevenLabs through its **official MCP server**                   | Recommended integration. The server can only read `work/`, and saves transcripts to disk, so the text never passes through the chat.                                                    |
| OpenAI through its **official API** (`gpt-6-luna`)               | OpenAI has no official MCP server for this, and community servers would hold our key.                                                                                                   |
| Content-agnostic **processors**                                  | Each task is one folder plus one skill. Adding one doesn't touch the others.                                                                                                            |
| Free-form tags that reuse existing tags                          | Any organisation can use it, while the model reuses the folder's existing wording, so "laptop" doesn't become "notebook". New tags are flagged.                                         |
| Topics and copy work from results, not the file                  | One cheap text request each. Every tag, hook and soundbite cites the footage it rests on, so a reviewer can check it.                                                                   |
| The organisation's name comes from `organisation.json`           | Speech-to-text can mishear it (it wrote the municipality "Tilottama" for "Tilicho"). Topics and copy use the spelling in this file.                                                     |
| Report numbers are given to the model, never left to it          | The model only words the month: every number it writes is checked against the data its sentence cites, and rankings of posts are worked out by prepare, not by the model.               |
| Report data is mocked for now                                    | Pulse's analytics (C15) and report compilation (C17a) don't exist yet, so `input/reports/<month>.json` stands in for them, in the shape their documents define.                         |

## How it works

```
input/<file>
  ├─ /transcribe:    prepare.py (FFmpeg: extract audio, skip silence, split at pauses)
  │                  → ElevenLabs MCP speech_to_text, one request per part
  │                  → finalize.py → output/transcribe/<name>-<hash>/transcript.md, .json,
  │                    subtitles .vtt and .srt (subtitles.py)
  │
  ├─ /tag-visuals:   prepare.py (FFmpeg: a frame per scene change plus one every 5 s;
  │                  collects existing tags)
  │                  → tag.py: OpenAI, 8 frames per request (tags + on-screen text),
  │                    then a cropped full-resolution re-read of small text
  │                  → finalize.py → output/tag-visuals/<name>-<hash>/tags.md, .json, frames/
  │
  ├─ /tag-topics:    prepare.py (transcript + visual tags + on-screen text as text)
  │                  → tag.py: one OpenAI text request
  │                  → finalize.py → output/tag-topics/<name>-<hash>/topics.md, .json
  │
  └─ /generate-copy: prepare.py (the same material, topic tags, organisation.json,
                     platforms, tone, brief)
                     → generate.py: one OpenAI text request
                     → finalize.py → output/generate-copy/<name>-<hash>/copy.md, .json

input/reports/<month>.json
  └─ /draft-report:  prepare.py (the month's totals, platforms, post snapshots, highlights,
                     the strategist's plan; leaders per measure; topic tags and hook of
                     posts made from a video in input/)
                     → draft.py: one OpenAI text request
                     → finalize.py (numbers and rankings checked against the data)
                     → output/draft-report/<month>-<hash>/report.md, .json

/process-video = transcribe and tag-visuals in parallel, then tag-topics.
```

Each processor follows the same pattern: **prepare (free, local) → paid step → finalize (free, local)**. The rules for each step live in `.claude/skills/<name>/SKILL.md`.

## Cost and safety guards

- Every paid step asks for approval (`.claude/settings.json`). The 13 other paid ElevenLabs tools (voice cloning, text-to-speech, ...) are blocked.
- No automatic retries. The same file is never charged twice unless you say `force`; the replaced result moves to `history/`.
- Silent audio and audio-only files are skipped for free.
- Partial results are kept. An interrupted tagging run resumes and pays only for what's missing.
- Claude cannot read `.env` (the keys). Scripts print counts and paths, not transcripts, tags or copy.
- People are never named in topics, copy or reports. Copy and reports are drafts (`review_status: draft`) and are never published or sent.

## Layout

```
.claude/skills/        setup, transcribe, tag-visuals, tag-topics, generate-copy, draft-report,
                       process-video
.claude/settings.json  permissions: allowed / asks first / blocked
processors/<name>/     prepare.py, paid step, finalize.py
lib/                   media.py (FFmpeg), workspace.py (paths, files), openai_api.py,
                       tags.py, material.py (results as text), organisation.py,
                       numbers.py (numbers in model text checked against the data)
fixtures/              example inputs (report-input.example.json)
servers/elevenlabs.py  starts the ElevenLabs MCP server (.mcp.json)
scripts/check_setup.py free environment and key checks
organisation.json      the organisation's name, website, hashtags (git-ignored)
input/ work/ output/   files to be processed (input/reports/: a month's numbers), temporary
                       jobs, results (all git-ignored)
```
