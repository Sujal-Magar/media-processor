# Media Processor: overview for review

## What it is

A folder you open in **Claude Code**. It turns a media file into searchable results:

- `/transcribe`: speech to text with **ElevenLabs** (English, Nepali, ...), with optional speaker labels and timestamps.
- `/tag-visuals`: what is visible (objects, scenes, activities, attributes) and readable on-screen text, with time ranges, using an **OpenAI** vision model.
- `/process-video`: runs both on one video at the same time.

It is the processing behind the Pulse/LoopStudio asset flow ("uploading → processing (transcribing/tagging) → ready" in the PRD).

## Why it is built this way

| Decision                                                         | Reason                                                                                                                                                                                                                                  |
| ---------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Claude Code skills plus small scripts, instead of an application | A first version was a full Python app (`../ai-processing-platform`, about 5,000 lines). It worked, but took too long to review. Here Claude runs the steps, and about 1,600 lines of standard-library Python do the deterministic work. |
| FFmpeg does all media work locally                               | It is free and predictable: audio extraction, silence detection, splitting at pauses, frame sampling. Providers only receive prepared audio or frames, never the originals.                                                             |
| ElevenLabs through its **official MCP server**                   | Recommended integration. The server can only read `work/`, and saves transcripts to disk, so the text never passes through the chat.                                                                                                    |
| OpenAI through its **official API** (`lib/openai_api.py`)        | OpenAI has no official vision MCP server, and community servers would hold our key.                                                                                                                                                     |
| Content-agnostic **processors**                                  | Each task (`transcribe`, `tag-visuals`, later e.g. `enhance-audio`) is one folder plus one skill. Adding one doesn't touch the others.                                                                                                  |
| Free-form tags that reuse existing tags                          | Any organisation can use it (no fixed list), while the model reuses the folder's existing wording, so "laptop" doesn't become "notebook computer". New tags are flagged.                                                                |

## How it works

```
input/<file>
  ├─ /transcribe:  prepare.py (FFmpeg: extract audio, skip silence, split at pauses)
  │                → ElevenLabs MCP speech_to_text, one request per part
  │                → finalize.py → output/transcribe/<name>-<hash>/transcript.md, .json
  │
  └─ /tag-visuals: prepare.py (FFmpeg: a frame per scene change plus one every 5 s;
                   collects existing tags)
                   → tag.py: OpenAI, 8 frames per request (tags + on-screen text),
                     then one cropped full-resolution re-read per run of frames with small text
                   → finalize.py → output/tag-visuals/<name>-<hash>/tags.md, .json, frames/

/process-video = both: tagging runs in the background while transcription runs.
```

Each processor follows the same pattern: **prepare (free, local) → paid step → finalize (free, local)**. The rules for each step live in `.claude/skills/<name>/SKILL.md`.

## Cost and safety guards

- Every paid step asks for approval (`.claude/settings.json`). The 13 other paid ElevenLabs tools (voice cloning, text-to-speech, ...) are blocked.
- No automatic retries. The same file is never charged twice unless you say `force`.
- Silent audio and audio-only files are skipped for free.
- Partial results are kept. An interrupted tagging run resumes and pays only for what's missing.
- Claude cannot read `.env` (the keys). Scripts print counts and paths, not transcripts or tags.
- Camera, device and GPS metadata is stripped before audio leaves the machine. People are tagged only as "person", never identified.

## Layout

```
.claude/skills/      setup, transcribe, tag-visuals, process-video
.claude/settings.json  permissions: allowed / asks first / blocked
processors/<name>/   prepare.py, paid step, finalize.py
lib/                 media.py (FFmpeg), workspace.py (paths, files), openai_api.py
servers/elevenlabs.py  starts the ElevenLabs MCP server (.mcp.json)
scripts/check_setup.py free environment and key checks
input/ work/ output/   your files, temporary jobs, results (all git-ignored)
```

## Try it

```fish
cp .env.example .env     # add ELEVENLABS_API_KEY and OPENAI_API_KEY
claude                   # in this folder
/setup                   # free check of tools, keys, model access, key permissions
/process-video input/<video> speakers timestamps
```

Full usage is in `README.md`, and the rules Claude follows here are in `CLAUDE.md`.

## Product decisions already made

- Sending frames to OpenAI is acceptable for Pulse's data rules.
- Tags are English only. On-screen text is kept in its original language and script.
- On-screen text (e.g. a MARN on screen) is read in the same request as the tags.
- "Identify speaking faces" means _someone is speaking to camera_, not who they are.
- Clients see tags straight away, as in the screen design. `tags.json` keeps `review_status: staging_pending` so operator review can be added later.

## Status

- **Tested with real providers:** transcription (plain, speakers plus timestamps, `force`), tagging (several runs; 11 of 13 tags reused from the existing library), `/process-video` with both processors running in parallel, and the double-charge guard.
- **Tested without cost** (synthetic media and a local stand-in for OpenAI): frame sampling, partial failure and resume, existing-tag reuse, on-screen text, and the re-read of small text (one full-resolution frame per run, cropped to the text, also on rotated phone video).
- **Read real text:** a high-detail run read "CERTIFICATE" from a wall certificate but not its details. Re-reading a full frame at 2048 px read 3 short words, because OpenAI downscales large images, so the re-read now crops to the text. The cropped re-read ran for real: 2 requests and about 2,500 input tokens (high detail on every frame used about 9,200), and it read slightly longer text. The certificate's body text is too small in this footage to be read at any setting; use a close photo for documents.

## Known limits

- The ElevenLabs MCP tool returns plain text. Timestamps are per part (split at pauses), not per word, and speaker numbers restart in each part.
- Tag confidence is the model's own estimate. On-screen text, especially long numbers, must be checked against the frame.
- The tag library is per folder: use one folder per organisation (the PRD requires per-client isolation).
- It works in Claude Code (terminal, or the Code tab of Claude Desktop), not in Claude Desktop chat.
- The consent gate from the Pulse design docs (no processing of testimonials without consent) is not enforced here yet.
- "Claude asks before reading `output/`" only covers Claude's file-reading tool. Reading results with a shell command still asks today, because unlisted shell commands always prompt, but it would not if someone allowed broad commands such as `python3 *`. Keep shell permissions narrow.

## Please review

1. The permission lists in `.claude/settings.json`: is anything paid allowed that shouldn't be?
2. The skill instructions (`.claude/skills/*/SKILL.md`): are they clear and safe?
3. The tagging prompt and output (`processors/tag-visuals/tag.py`, a sample `tags.md`): are the tags useful for Pulse's filters and QA?
4. Whether one folder per organisation is acceptable, or we need per-client tag libraries in one folder.
5. Whether the consent gate should be added before real client media is processed.
