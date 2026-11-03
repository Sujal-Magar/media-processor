# Media Processor

Media file in, result out. Each task is a **processor** you run from Claude Code as a
skill. FFmpeg does the local media work; AI providers do the rest through their official
MCP servers. Audio, video and image processors share the same layout.

| Processor  | Skill         | Input          | Output                      | Provider                  |
| ---------- | ------------- | -------------- | --------------------------- | ------------------------- |
| transcribe | `/transcribe` | audio or video | transcript (`.md`, `.json`) | ElevenLabs speech-to-text |

How a processor runs (transcribe as the example):

```
input/interview.mov
   │  /transcribe
   ▼
prepare.py        FFmpeg: pick audio track, extract mono audio, strip GPS/device metadata,
   │              skip silent audio, split at pauses (optional)          free, local
   ▼
ElevenLabs MCP    speech_to_text, one request per part, asks you first   paid
   │              result saved to disk, not sent back to Claude
   ▼
finalize.py       transcript.md, transcript.json, metadata.json         free, local
   ▼
output/transcribe/interview-<hash>/
```

## Setup (once)

```fish
sudo pacman -S --needed ffmpeg uv
cd ~/programming/work/media-processor
cp .env.example .env          # put your key after ELEVENLABS_API_KEY=
claude                        # or open this folder in the Claude Desktop app's Code tab
```

In Claude Code, run `/setup`. It checks ffmpeg, uvx, the key and the MCP server, and
looks up your ElevenLabs plan for free. The first start downloads the ElevenLabs server
with `uvx` (about a minute).

## Use: transcribe

Put a file in `input/`, then in Claude Code:

```
/transcribe input/interview.mov
/transcribe input/voice-note.m4a speakers
/transcribe input/interview.mov language nepali timestamps
/transcribe input/interview.mov timestamps 60 speakers
/transcribe input/obs-recording.mkv track 1 normalize
```

| Words                               | Effect                                                                                       |
| ----------------------------------- | -------------------------------------------------------------------------------------------- |
| `speakers`                          | label who is speaking (SPEAKER 0, SPEAKER 1, ...)                                            |
| `language nepali` / `english` / ... | tell ElevenLabs the language; default is auto-detect                                         |
| `timestamps [seconds]`              | split at pauses into parts of at most N seconds (default 120); each part gets a time heading |
| `track N`                           | use another audio track (0 = first)                                                          |
| `normalize`                         | even out quiet recordings                                                                    |
| `force`                             | transcribe again (charged again)                                                             |

Claude tells you how many paid requests a job needs, and Claude Code asks you to approve
each `speech_to_text` call.

Results:

```
output/transcribe/interview-1a2b3c4d/
├── transcript.md     readable transcript
├── transcript.json   text, parts with start/end times, options, completeness
└── metadata.json     source file, audio tracks, loudness, request plan
```

You can then ask Claude things like "summarize the transcript" or "translate it to
English into a new file". Claude asks permission before reading anything in `output/`.

## Safety and cost

- **Paid tools always ask.** `.claude/settings.json` puts each paid tool a processor uses
  under `ask` and blocks every other paid ElevenLabs tool (voice cloning, text-to-speech,
  music, phone calls, ...).
- **No double charges by accident.** The same source file is not processed twice unless
  you say `force`. Failed requests are never retried.
- **Silent audio is free.** If the chosen track is silent, nothing is sent (and you are
  told if another track has sound).
- **Providers only see prepared files.** MCP servers can read only `work/`; they never see
  your originals or other files.
- **Results stay out of the chat.** Providers save results to files and only answer
  "saved". The scripts print paths and counts, not content.
- **The key stays out of the chat.** Claude is not allowed to read `.env`.

## Layout

```
media-processor/
├── input/                         your media files
├── work/<processor>/<job>/        temporary files (deleted after each job)
├── output/<processor>/<name>-<hash>/
├── processors/<processor>/        scripts for one processor
├── lib/media.py                   shared FFmpeg/ffprobe helpers
├── lib/workspace.py               shared paths, hashing, file writing
├── servers/<provider>.py          starts a provider's MCP server (.mcp.json)
├── scripts/check_setup.py         environment check for /setup
├── .claude/skills/<processor>/    the skill you run
├── .claude/settings.json          permissions: allowed, asks first, blocked
└── CLAUDE.md                      rules Claude follows here
```

## Adding a processor

For example `enhance-audio` or `describe-image`:

1. Add `processors/<name>/` with its scripts, reusing `lib/media.py` and `lib/workspace.py`.
2. Add `.claude/skills/<name>/SKILL.md`. Use `disable-model-invocation: true` if it costs
   money, so it only runs when you type it.
3. In `.claude/settings.json`, `allow` its scripts and put its paid tools under `ask`.
4. For a new provider, also add `servers/<provider>.py`, an entry in `.mcp.json`, its key
   in `.env.example` and a check in `scripts/check_setup.py`.
5. Add a row to the processor table above.

## Running steps by hand

Useful for testing without Claude (prepare and finalize are free):

```fish
python3 scripts/check_setup.py
python3 processors/transcribe/prepare.py input/interview.mov --part-seconds 120 --diarize
# the paid step needs the MCP tool; inside Claude Code: /transcribe ...
python3 processors/transcribe/finalize.py work/transcribe/<job-folder>
```

## Limits

- The ElevenLabs MCP tool returns plain text: no word-level timestamps, no detected
  language, no model name. Timestamps come from splitting into parts, so they are per
  part, not per sentence.
- With `speakers` and several parts, speaker numbers restart in each part.
- Works in Claude Code (terminal, or the Code tab of Claude Desktop). Claude Desktop's
  chat mode does not load project skills or `.mcp.json`.
- A failed or interrupted job keeps the parts that succeeded (`transcript.json` has
  `"complete": false`); re-running needs `force` and pays for every part again.
