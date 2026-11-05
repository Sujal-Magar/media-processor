# Media Processor

Media file in, results out. Each task is a **processor** you run from Claude Code as a
skill, and **pipeline skills** run several processors on one file at once. FFmpeg does
the local media work; AI providers do the rest. Audio, video and image processors share
the same layout.

| Processor   | Skill          | Input                                | Output                                                                                                                             | Provider                                        |
| ----------- | -------------- | ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| transcribe  | `/transcribe`  | audio or video                       | transcript (`.md`, `.json`)                                                                                                        | ElevenLabs speech-to-text (official MCP server) |
| tag-visuals | `/tag-visuals` | video or photo                       | free-form visual tags (reusing the folder's existing tags) and on-screen text, with time ranges (`.md`, `.json`), frame thumbnails | OpenAI vision model (official API)              |
| tag-topics  | `/tag-topics`  | a file already transcribed or tagged | what it is about: type, topics and named things (never people), each with its evidence, and a short summary (`.md`, `.json`)       | OpenAI text model (official API)                |

| Pipeline      | Skill            | Runs                                                                        |
| ------------- | ---------------- | --------------------------------------------------------------------------- |
| process-video | `/process-video` | `transcribe` and `tag-visuals` on one video, in parallel, then `tag-topics` |

How a processor runs:

```
input/interview.mov
   │  /transcribe                              │  /tag-visuals
   ▼                                           ▼
prepare.py   FFmpeg: extract speech audio,     prepare.py   FFmpeg: a frame per scene change
             skip silence, split at pauses                  plus one every 5 s (max 60)
   ▼                                           ▼
ElevenLabs MCP  speech_to_text, per part       tag.py       OpenAI vision, up to 8 frames per request,
                                                            then a cropped re-read of small text
   ▼                                           ▼
finalize.py  transcript.md / .json             finalize.py  tags.md / .json, frames/
   ▼                                           ▼
output/transcribe/interview-<hash>/            output/tag-visuals/interview-<hash>/
```

`/process-video` runs both columns at the same time: tagging in the background while
the transcription runs.

When both are done, `tag-topics` reads the transcript, the visual tags and the clearly
read on-screen text (never the file) and asks OpenAI, in one text request, what the
video is about: its type (`student-testimonial`), topics (`australia-student-visa`) and
named things (`subclass-500`). Every tag is English, lowercase, with hyphens.

## Setup (once)

```fish
sudo pacman -S --needed ffmpeg uv
cd ~/programming/work/media-processor
cp .env.example .env          # put your ElevenLabs and OpenAI keys in it
claude                        # or open this folder in the Claude Desktop app's Code tab
```

In Claude Code, run `/setup`. It checks ffmpeg, uvx, both keys, the ElevenLabs MCP
server and whether your OpenAI key can use the vision model, and lists the ElevenLabs
key's permissions. All of it is free. The first start downloads the ElevenLabs server
with `uvx` (about a minute).

## Use

Put a file in `input/`, then in Claude Code:

```
/process-video input/interview.mov
/process-video input/interview.mov speakers timestamps
/transcribe input/voice-note.m4a speakers
/tag-visuals input/photo.jpg
/tag-visuals input/interview.mov every 2 seconds high detail
```

`/process-video` accepts the words of both processors:

| Words                               | Processor   | Effect                                                                                                                                                          |
| ----------------------------------- | ----------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `speakers`                          | transcribe  | label who is speaking (SPEAKER 0, SPEAKER 1, ...)                                                                                                               |
| `language nepali` / `english` / ... | transcribe  | tell ElevenLabs the language; default is auto-detect. Forcing one on mixed speech may translate the other language into it or drop it, so Claude asks first     |
| `timestamps [seconds]`              | transcribe  | split at pauses into even parts of about N seconds (default 120; up to 10 % longer to end at a pause); each part, even a single one, gets a time heading        |
| `track N`                           | transcribe  | use another audio track (0 = first)                                                                                                                             |
| `normalize`                         | transcribe  | even out quiet recordings (peaks limited to -3 dB; the level before is kept in `metadata.json`)                                                                 |
| `every N seconds`                   | tag-visuals | a frame at least every N seconds (default 5), plus every scene change                                                                                           |
| `max N frames`                      | tag-visuals | upper limit on frames (default 60); if it can't cover the video at the asked interval, the interval is stretched and a warning says to what                     |
| `high detail`                       | tag-visuals | let the model see more detail (small objects); about 5× the input tokens per landscape frame and 13× per portrait phone frame, and skips the small-text re-read |
| `no text pass`                      | tag-visuals | don't re-read small text at high detail (by default, frames with text too small to read are re-read in a second request)                                        |
| `force`                             | all         | process again (charged again); the previous result moves to `history/<time>/` in its output folder                                                              |

Claude tells you how many paid requests a job needs before sending anything (for tagging
also a rough input-token estimate, by OpenAI's image tile formula, and the most the
small-text re-read could add: up to N more requests of about T tokens per re-read frame,
only if frames show text too small to read), and Claude Code asks you to approve each
`speech_to_text` call and each tagging run.

Results:

```
output/transcribe/interview-1a2b3c4d/
├── transcript.md     readable transcript
├── transcript.json   text, parts with start/end times, options, model, completeness
├── metadata.json     source file, audio tracks, loudness, request plan, status
└── history/<time>/   earlier results that `force` replaced (only after a `force`)

output/tag-visuals/interview-1a2b3c4d/
├── tags.md           tags by category (object, scene, activity, attribute) with time
│                     ranges and new tags marked, on-screen text with time ranges, and
│                     a frame-by-frame table with thumbnails
├── tags.json         the same, plus confidence, review status, tokens used (tagging and
│                     re-read apart), completeness, and what the small-text re-read found
│                     per frame
├── metadata.json     source file, sampling options, frame times, status
├── frames/           the frames that were tagged
└── history/<time>/   earlier results that `force` replaced (only after a `force`)

output/tag-topics/interview-1a2b3c4d/
├── topics.md         type, topics and entities with their evidence (speech times,
│                     on-screen text, visual tags), new tags marked, and the summary
├── topics.json       the same, plus `visual` (the file's visual tags), confidence,
│                     review status, the inputs it read, tokens used
├── metadata.json     inputs, model, request plan, status
└── history/<time>/   earlier results that `force` replaced (only after a `force`)
```

You can then ask Claude things like "summarize the transcript" or "in which scenes does
a laptop appear?". Claude asks permission before reading anything in `output/`.

## Safety and cost

- **Paid steps always ask.** `.claude/settings.json` puts ElevenLabs `speech_to_text`
  and the OpenAI tagging scripts (visual tags and topics) under `ask`, and blocks every
  other paid ElevenLabs tool (voice cloning, text-to-speech, music, phone calls, ...).
- **No double charges by accident.** The same source file is not processed twice unless
  you say `force`, and then the previous result is kept in `history/<time>/` (named after
  when it was made) instead of being overwritten. Failed requests are never retried. An interrupted tagging run keeps
  the batches it finished, and running `tag.py` on that job again pays only for the rest.
- **Free when there is nothing to do.** Silent audio is not sent to ElevenLabs; an
  audio-only file is not sent to OpenAI.
- **Providers only see prepared files.** ElevenLabs reads only `work/` (extracted
  audio); OpenAI receives only the sampled frames (at most 768 px), plus, for text too
  small to read, a full-resolution crop around that text. For topics, OpenAI receives
  the transcript text, the visual tags and the clearly read on-screen text, never a
  file. Neither sees your originals or other files.
- **ElevenLabs keeps the audio.** The pinned MCP server (`elevenlabs-mcp` 0.12.2) always
  sends requests with logging on, so ElevenLabs stores the audio and transcript under its
  normal retention. The tool can't turn this off; zero retention would need another route
  (and, per ElevenLabs, an enterprise plan). `transcript.json` records it
  (`provider.request_logging`).
- **Results stay out of the chat.** Transcripts and tags are written to files; the
  scripts print paths and counts, not content.
- **Keys stay out of the chat.** Claude is not allowed to read `.env`.
- **OpenAI without a third-party server.** OpenAI has no official MCP server for vision,
  so `lib/openai_api.py` calls the official API directly instead of handing your key to
  a community server.

## Layout

```
media-processor/
├── input/                         your media files
├── work/<processor>/<job>/        temporary files (deleted after each finished job)
├── output/<processor>/<name>-<hash>/
├── processors/<processor>/        scripts for one processor
├── lib/media.py                   shared FFmpeg/ffprobe helpers
├── lib/workspace.py               shared paths, hashing, file writing
├── lib/openai_api.py              OpenAI API client (standard library only)
├── lib/tags.py                    tag wording (lowercase, hyphens) and tag libraries
├── servers/<provider>.py          starts a provider's MCP server (.mcp.json)
├── scripts/check_setup.py         environment check for /setup
├── .claude/skills/<name>/         the skills you run (processors and pipelines)
├── .claude/settings.json          permissions: allowed, asks first, blocked
└── CLAUDE.md                      rules Claude follows here
```

## Adding a processor

For example `enhance-audio` or `describe-image`:

1. Add `processors/<name>/` with its scripts, reusing `lib/media.py` and `lib/workspace.py`.
2. Add `.claude/skills/<name>/SKILL.md`. Use `disable-model-invocation: true` if it costs
   money, so it only runs when you type it.
3. In `.claude/settings.json`, `allow` its free scripts and put its paid tools or scripts
   under `ask`.
4. For a new provider, add its key to `.env.example` and a check to
   `scripts/check_setup.py`, plus either `servers/<provider>.py` and an `.mcp.json` entry
   (official MCP server) or `lib/<provider>_api.py` (official API).
5. Add a row to the processor table above, and add it to `/process-video` if it should
   run on every video.

## Running steps by hand

Useful for testing without Claude (prepare and finalize are free):

```fish
python3 scripts/check_setup.py
python3 processors/transcribe/prepare.py input/interview.mov --part-seconds 120 --diarize
# the paid transcription step needs the MCP tool; inside Claude Code: /transcribe ...
python3 processors/transcribe/finalize.py work/transcribe/<job-folder>

python3 processors/tag-visuals/prepare.py input/interview.mov --interval 5
python3 processors/tag-visuals/tag.py work/tag-visuals/<job-folder>     # paid
```

## Settings

Optional values in `.env` (see `.env.example`):

| Variable                  | Default      | Meaning                                                  |
| ------------------------- | ------------ | -------------------------------------------------------- |
| `OPENAI_VISION_MODEL`     | `gpt-6-luna` | any OpenAI model with image input                        |
| `OPENAI_REASONING_EFFORT` | `none`       | tagging needs little reasoning; `unset` sends no setting |

## Limits

- The ElevenLabs MCP tool returns plain text: no word-level timestamps, no detected
  language, no model name. Timestamps come from splitting into parts, so they are per
  part, not per sentence. The pinned server version always uses the `scribe_v2` model and
  writes sounds such as (laughter) into the text; `transcript.json` records both. Its
  success message names the input audio, not the transcript file.
- With `speakers` and several parts, speaker numbers restart in each part.
- Speech audio is sent as mono. When one channel of a stereo track is silent (phones often
  record a wireless mic on one side), only the live channel is used, so the level and the
  "quiet" warning describe the speech; `metadata.json` lists each channel's peak.
- Visual tags are free-form English so any organisation can use them. The model is shown
  the tags already used in this folder (up to 300, most used first) as a vocabulary, not
  a checklist: it reuses one only when it describes exactly what is visible (a colour,
  garment or posture must match). Frames go in as few requests of up to 8 as possible,
  split evenly (9 frames: 5 + 4, not 8 + 1), so no frame is tagged alone. From the second
  request on, the model also sees the tags and text earlier requests gave the same video,
  so an unchanged scene keeps its wording. With `force`, the file's own earlier tags are
  offered too, but count as new against the rest of the library. New tags are marked so
  a reviewer can merge near-duplicates. Readings of one text that differ by a letter or
  two (TELICHO / TILICHO) are merged, keeping the most frequent spelling and listing the
  others as `variants`; text with 4 or more digits is never merged unless identical, and
  neither is a partial reading with a clear one. The tag library covers everything in
  this folder, so keep separate organisations in separate copies of the folder. Time
  ranges are as precise as the frame sampling (a scene change, or every 5 s by default).
- On-screen text is read by the same request. Where the model sees text too small to read
  (a certificate on a wall, a number on a badge), one frame per run of such frames is
  taken again from the original file at full resolution, cropped around where the model
  saw the text (with a wide margin, at least 30 % of the frame each way, small crops
  enlarged 2×), and re-read at high detail. Text whose box is under 80 px on its short
  side in the original is not re-read (`skipped: text box N px ...`): no model can read it,
  so the request isn't paid for. Its text is added to every frame of the run; text
  the first pass read that the re-read didn't read again (outside the crop, or
  invented at low detail) is kept but marked `confirmed: false`. `tags.json` says per frame what the
  re-read found (`text_reread`: `found`, `nothing readable` or `skipped: <reason>`), keeps
  the first pass's text (`text_low_detail`), and `text_pass.status` says whether the pass
  ran (`done`, `not needed`, `off (no text pass)`, `skipped (high detail)`, `skipped (text
too small)`, or `incomplete` when a request failed). `no text
pass` skips the re-read, and so does `high detail`. Each text is marked `clear` or
  `partial`: the model writes characters it can't read as `…` instead of guessing them
  and leaves out lines it can't read at all (an item with no letter or digit, such as a
  bare `…`, is dropped and doesn't count as text found), and `tags.md` lists partial and
  unconfirmed text under "Partly readable or unconfirmed (check against the frame)". Text is reliable
  when large and clear and less so when tiny, blurry or a long number.
- The model's answers are not verified. It can misread text or complete it from context,
  even text it marks `partial`, and the `…` doesn't always sit where the doubt is. Check
  every read text against the frame before relying on it (registration numbers such as
  a MARN, prices, dates); `partial` text is unconfirmed. Confidence is the model's own
  estimate, not a measured score, and is mostly `high`. Tags can differ between runs and
  between requests for the same video, and a library tag is sometimes reused where it
  doesn't quite fit (`close-up` on a waist-up shot).
- Tags are shown as soon as they exist; `tags.json` marks them `staging_pending` so an
  operator review step can be added later.
- People are tagged as "person" only; there is no face or identity recognition.
- Works in Claude Code (terminal, or the Code tab of Claude Desktop). Claude Desktop's
  chat mode does not load project skills or `.mcp.json`.
- A failed transcription keeps the parts that succeeded (`"complete": false`);
  re-running needs `force` and pays for every part again.
