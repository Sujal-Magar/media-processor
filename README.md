# Media Processor

Media file in, results out. Each task is a **processor** you run from Claude Code as a
skill, and **pipeline skills** run several processors on one file at once. FFmpeg does
the local media work; AI providers do the rest. Audio, video and image processors share
the same layout.

| Processor     | Skill            | Input                                  | Output                                                                                                                                                             | Provider                                        |
| ------------- | ---------------- | -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------- |
| transcribe    | `/transcribe`    | audio or video                         | transcript (`.md`, `.json`) and subtitles (`.vtt`, `.srt`, times estimated within each part)                                                                       | ElevenLabs speech-to-text (official MCP server) |
| tag-visuals   | `/tag-visuals`   | video or photo                         | free-form visual tags (reusing the folder's existing tags) and on-screen text, with time ranges (`.md`, `.json`), frame thumbnails                                 | OpenAI vision model (official API)              |
| tag-topics    | `/tag-topics`    | a file already transcribed or tagged   | what it is about: type, topics and named things (never people), each with its evidence, and a short summary (`.md`, `.json`)                                       | OpenAI text model (official API)                |
| generate-copy | `/generate-copy` | a video already transcribed and tagged | draft copy: 3–5 hooks, an edit script (soundbites and B-roll with their times), a caption per platform, hashtag clusters, an optional translation (`.md`, `.json`) | OpenAI text model (official API)                |
| draft-report  | `/draft-report`  | one month's numbers (`.json`)          | draft monthly report narrative: a headline, three short paragraphs, the top post, a line per highlight and tile, next month's plan in the client's words (`.md`, `.json`) | OpenAI text model (official API)                |
| translate-subtitles | `/translate-subtitles` | a video already transcribed            | English-only and Nepali-only subtitles (`.vtt`, `.srt`), cue for cue with the same times as the mixed-language ones                                                       | OpenAI text model (official API)                |
| draft-insights | `/draft-insights` | one month's triggers (`.json`) and its numbers | draft strategic insights: per flagged result, hypotheses to test, a proposed asset request and a client card, each `Proposed` (`.md`, `.json`)                      | OpenAI text model (official API)                |

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

`/generate-copy` then drafts social media copy from the same material plus the topic
tags: opening hooks, an edit script that picks soundbites and B-roll from the footage,
a caption for each platform (Instagram Reels, TikTok, LinkedIn, YouTube Shorts),
hashtags (niche, broad, brand) and, if asked, a translation (Nepali, for example). Every
hook and script line cites the footage it rests on, people are never named, and the
result is a draft for someone to approve. Nothing is published. The organisation's own
name comes from `organisation.json`, because speech-to-text can mishear it (a name heard
as a better-known place).

`/draft-report` writes the narrative of a client's monthly results report (Pulse C17b)
from that month's numbers: totals with the change from last month, each platform, each
post's snapshot, the Top 3 highlights and, if written, the strategist's plan for next
month. Until Pulse's analytics exist, the numbers come from a hand-written file
(`fixtures/report-input.example.json` shows the shape; mock months go in
`input/reports/`). For posts made from a video in `input/`, it also reads the topic tags
and the hook used. Every sentence cites the data it rests on, and every number in it must
be one the month's data holds (48,200 may read 48.2K, 38.11% may read 38%): a number
that matches nothing makes the draft incomplete. It describes what happened, not why;
the next-month list only rewords the strategist's plan. The draft is for the strategist
to review, edit and sign off; nothing is sent.

`/draft-insights` drafts strategic insights (Pulse C18b) for the results Pulse's anomaly
rules flag: a post's engagement above 2 × the 90-day average, more than 45% of viewers
gone in the first 3 seconds, posting 2 or more behind the monthly quota. Until those
rules exist, the triggers come from a hand-written file
(`fixtures/insights-input.example.json` shows the shape; mock months go in
`input/insights/`), and the posts from the report inputs in `input/reports/` whose
months the 90-day window covers. Prepare re-checks each trigger against the numbers,
holds back one on a post whose data is incomplete (and leaves that post out of
everything), and works out every number the model may use: each trigger's size (10.23%
is 2.2× the average) and comparisons between groups of posts with complete data
(pillar, platform, language, video or picture, hook style, what the pictures show), each
side with 2 or more different pieces of content (a video posted on two platforms counts
once) and a difference of at least 10%; a trigger's comparisons leave out its own post
(and the same video posted again), so a post never explains itself. Each client card's
first sentence is written from the trigger's numbers, not by the model.
For each trigger the model gives an observation, one or two hypotheses worded as
possibilities, each with a measured test of what would confirm or refute it, a proposed
asset request for next month that tests one of them (title, category, a quantity from 1
to 3, language, brief) and a client card draft in the Results card's style; or says there
is not enough evidence. For posting behind the quota it gives no hypotheses (the numbers
cannot say why fewer posts went out), only what to send to catch up. Every insight is
`Proposed` and the file a draft for the strategist; nothing reaches the client, and
acceptance and asset requests belong to Pulse.

`/transcribe` also writes subtitles (`transcript.vtt`, `transcript.srt`) in the language
spoken, which for many videos mixes Nepali and English. `/translate-subtitles` turns them
into an English-only and a Nepali-only track, in one text request. The track in the
language most of the speech is in is put together by the scripts: each cue exactly as
said, with only the words said in the other language replaced by the model's rendering,
so nothing said in that language is reworded. That gives two Nepali tracks: one with
the English words translated (`transcript.ne`), one with them written in Devanagari by
their sound (`transcript.ne-spoken`, "market" as मार्केट). The other track translates each
whole cue. Forms of the organisation's name that speech-to-text writes, listed as
`heard_as` in `organisation.json`, are left for the model to correct from context (the
same word can be a real place).
All tracks keep the same cues and times and stay in step with the video. Spoken
names stay (subtitles say what was said), the organisation's name is spelled as
`organisation.json` gives it, and the result is a draft for a speaker of each language
to check.

## Setup (once)

```fish
sudo pacman -S --needed ffmpeg uv
cd ~/programming/work/media-processor
cp .env.example .env          # put your ElevenLabs and OpenAI keys in it
cp organisation.example.json organisation.json   # your organisation's name, website, hashtags,
                                                 # and how speech-to-text mishears it (heard_as)
claude                        # or open this folder in the Claude Desktop app's Code tab
```

In Claude Code, run `/setup`. It checks ffmpeg, uvx, both keys, the ElevenLabs MCP
server and whether your OpenAI key can use the models (vision, and the topic, copy and
report and translation models if you set them apart), and lists the ElevenLabs
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
/draft-report input/reports/2026-10.json
/translate-subtitles input/interview.mov
/draft-insights input/insights/2026-10.json
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
├── transcript.vtt    subtitles (WebVTT): short cues of at most two lines, speaker
│                     labels as voices; times estimated within each part
├── transcript.srt    the same cues as SRT, without speaker labels
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

output/generate-copy/interview-1a2b3c4d/
├── copy.md           hooks, the script (soundbites with their text and times, subtitles,
│                     B-roll with time ranges, on-screen text, editor notes), captions,
│                     hashtags, each hook's and caption's translation, notes from the
│                     model, and what is missing or needs checking before posting
├── copy.json         the same, plus the request (platforms, language, tone, brief), the
│                     organisation details and inputs it read, hooks and segments
│                     dropped, review status (`draft`), tokens used
├── metadata.json     inputs, model, request plan, status
└── history/<time>/   earlier results that `force` replaced (only after a `force`)

output/draft-report/2026-10-1a2b3c4d/       (named after the month's input file)
├── report.md         the report as the client page lays it out (headline, the three
│                     paragraphs, the numbers with a line under each, the top post,
│                     highlights, next month), what needs checking, and the data each
│                     part rests on
├── report.json       the same, sentence by sentence with its evidence, plus what was
│                     dropped, review status (`draft`), tokens used
├── metadata.json     month, inputs, model, request plan, status
└── history/<time>/   earlier results that `force` replaced (only after a `force`)

output/translate-subtitles/interview-1a2b3c4d/
├── transcript.en.vtt, transcript.en.srt    English-only subtitles
├── transcript.ne.vtt, transcript.ne.srt    Nepali-only subtitles: Nepali as said, the
│                                           English words translated into Nepali
├── transcript.ne-spoken.vtt, .srt          Nepali as spoken, all in Devanagari: the
│                                           English words written by their sound
├── translation.json  every cue with its times, original text and translations, what
│                     needs checking, review status (`draft`), tokens used
├── metadata.json     inputs, languages, model, request plan, status
└── history/<time>/   earlier results that `force` replaced (only after a `force`)

output/draft-insights/2026-10-1a2b3c4d/     (named after the month's trigger file)
├── insights.md       per trigger: what it found, the hypotheses with how to test them,
│                     the proposed request and the client card; what was held back or
│                     lacked evidence, what needs checking, the data each part rests on
├── insights.json     the same, sentence by sentence with its evidence, each insight
│                     `Proposed`, plus what was dropped, review status (`draft`), tokens
├── metadata.json     month, inputs, baseline, quota, model, request plan, status
└── history/<time>/   earlier results that `force` replaced (only after a `force`)
```

You can then ask Claude things like "summarize the transcript" or "in which scenes does
a laptop appear?". Claude asks permission before reading anything in `output/`.

## Safety and cost

- **Paid steps always ask.** `.claude/settings.json` puts ElevenLabs `speech_to_text`
  and the OpenAI scripts (visual tags, topics, copy, reports, subtitle translation and insights) under `ask`, and blocks every
  other paid ElevenLabs tool (voice cloning, text-to-speech, music, phone calls, ...).
- **No double charges by accident.** The same source file is not processed twice unless
  you say `force`, and then the previous result is kept in `history/<time>/` (named after
  when it was made) instead of being overwritten. Failed requests are never retried. An interrupted tagging run keeps
  the batches it finished, and running `tag.py` on that job again pays only for the rest.
- **Free when there is nothing to do.** Silent audio is not sent to ElevenLabs; an
  audio-only file is not sent to OpenAI.
- **Providers only see prepared files.** ElevenLabs reads only `work/` (extracted
  audio); OpenAI receives only the sampled frames (at most 768 px), plus, for text too
  small to read, a full-resolution crop around that text. For topics and copy, OpenAI
  receives the transcript text, the visual tags and the clearly read on-screen text
  (copy also the topic tags and your brief), never a file. For reports, OpenAI receives
  the month's numbers and, for posts made from a video, its topic tags and hook; for
  subtitle translation, the subtitle cues' text; for insights, the triggers, the
  baseline, the comparisons prepare worked out and the posts with complete data (for a
  video post also its topic tags, hook, call to action and visual tags). Neither sees
  your originals or other files.
- **ElevenLabs keeps the audio.** The pinned MCP server (`elevenlabs-mcp` 0.12.2) always
  sends requests with logging on, so ElevenLabs stores the audio and transcript under its
  normal retention. The tool can't turn this off; zero retention would need another route
  (and, per ElevenLabs, an enterprise plan). `transcript.json` records it
  (`provider.request_logging`).
- **Results stay out of the chat.** Transcripts and tags are written to files; the
  scripts print paths and counts, not content.
- **Keys stay out of the chat.** Claude is not allowed to read `.env`.
- **Client data stays out of git.** `input/`, `work/`, `output/` and `organisation.json`
  are ignored.
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
├── lib/material.py                earlier results as text for a model (topics, copy)
├── lib/numbers.py                 numbers in model text checked against the data given
├── lib/report_input.py            a month's report input read and checked (reports, insights)
├── lib/wording.py                 causal, internal and jargon wording checks
├── fixtures/                      example inputs (report-input, insights-input)
├── lib/organisation.py            the organisation's own name, hashtags and misheard forms (organisation.json)
├── organisation.json              your organisation's details (not in git; see the example)
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
python3 processors/transcribe/subtitles.py --all    # subtitles for transcripts made before

python3 processors/tag-visuals/prepare.py input/interview.mov --interval 5
python3 processors/tag-visuals/tag.py work/tag-visuals/<job-folder>     # paid

python3 processors/generate-copy/prepare.py input/interview.mov --platforms linkedin,tiktok --translate ne
python3 processors/generate-copy/generate.py work/generate-copy/<job-folder>   # paid

python3 processors/draft-report/prepare.py input/reports/2026-10.json
python3 processors/draft-report/draft.py work/draft-report/<job-folder>       # paid

python3 processors/translate-subtitles/prepare.py input/interview.mov --languages en,ne
python3 processors/translate-subtitles/translate.py work/translate-subtitles/<job-folder>   # paid

python3 processors/draft-insights/prepare.py input/insights/2026-10.json
python3 processors/draft-insights/draft.py work/draft-insights/<job-folder>   # paid
```

## Settings

Optional values in `.env` (see `.env.example`):

| Variable                       | Default      | Meaning                                                  |
| ------------------------------ | ------------ | -------------------------------------------------------- |
| `OPENAI_VISION_MODEL`          | `gpt-6-luna` | any OpenAI model with image input                        |
| `OPENAI_REASONING_EFFORT`      | `none`       | tagging needs little reasoning; `unset` sends no setting |
| `OPENAI_COPY_MODEL`            | vision model | text model for `/generate-copy`                          |
| `OPENAI_COPY_REASONING_EFFORT` | `low`        | reasoning for copy; `unset` sends no setting             |
| `OPENAI_REPORT_MODEL`          | vision model | text model for `/draft-report`                           |
| `OPENAI_REPORT_REASONING_EFFORT` | `low`      | reasoning for reports; `unset` sends no setting          |
| `OPENAI_TRANSLATE_MODEL`       | vision model | text model for `/translate-subtitles`                    |
| `OPENAI_TRANSLATE_REASONING_EFFORT` | `low`   | reasoning for translation; `unset` sends no setting      |
| `OPENAI_INSIGHT_MODEL`         | vision model | text model for `/draft-insights`                         |
| `OPENAI_INSIGHT_REASONING_EFFORT` | `low`     | reasoning for insights; `unset` sends no setting         |

## Limits

- The ElevenLabs MCP tool returns plain text: no word-level timestamps, no detected
  language, no model name. Timestamps come from splitting into parts, so they are per
  part, not per sentence. The pinned server version always uses the `scribe_v2` model and
  writes sounds such as (laughter) into the text; `transcript.json` records both. Its
  success message names the input audio, not the transcript file.
- Subtitle times are estimates. Only each part's start and end are measured; the cues
  inside a part (a sentence, or a piece of a long one) share its time by their length, so
  a pause inside a part shifts the cues after it. Shorter parts (`timestamps 15`) give
  closer times; exact cue times need word timings, which the MCP tool does not return.
  The `.vtt` says this in a NOTE line. Check subtitles against the video before
  publishing.
- `/translate-subtitles` keeps each cue's times, so a translation that runs longer than
  its cue stays on screen as briefly as the original. The model is asked to translate
  concisely; a translation still too long for two lines is shown as several cues within
  its cue's time, and `checks` lists it, as it does a track that kept less than 90% of
  the words said in its own language (it reworded what was said). Line width counts what
  takes room on screen
  (Devanagari signs drawn over or under a letter do not), for every subtitle. Its checks catch an untranslated cue (no Devanagari in Nepali, Devanagari
  left in English) and a dropped number, not a wrong meaning: a speaker of the language
  checks the tracks before they are published.
- With `speakers` and several parts, speaker numbers restart in each part.
- `/generate-copy` soundbites name their sentence, but their times are those of the
  transcript part they are in (a short video is often one part), so an editor finds the
  exact in and out points by ear. B-roll cues carry the time ranges of their visual tag.
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
- `/draft-report` checks numbers, not meaning: a sentence can cite the right data and
  still misread it. Each number must be in the month's data, and is flagged when it is
  not in what its sentence cites (it may belong to another post); a number can still
  match by chance within that data. The checker also flags ratios ("three times"),
  claimed causes ("drove", "because", unless the sentence explains missing data),
  internal terms ("engine", "snapshot") and jargon ("impressions"), rankings of posts
  while some posts' numbers are incomplete, and, without earlier months, superlatives
  ("strongest month", "so far") for the strategist, but cannot catch every wording.
  Rankings of posts are worked out by prepare (the leaders per measure among posts with
  complete data) and every "most" or "fewest" claim about a post is checked against
  them, as far as the sentence's wording shows the measure. People
  are never named, but nothing detects a name the model wrote anyway. Video plays are
  D2's `views_count`, which counts plays, not people.
- `/draft-insights` checks numbers and wording, not reasoning: a hypothesis can cite the
  right comparison and still be a poor explanation, which is why each is a possibility
  with its own test and the strategist decides. Comparisons rest on little content (2 or
  3 videos or pictures a side is common), and with only a few videos tagged, visual-tag
  comparisons rarely have 2 on each side. The baseline's average comes from the trigger file, while comparisons
  use only the posts in `input/reports/`, so they can disagree (prepare warns). The
  anomaly thresholds, the quota (16 posts a month here; Pulse's calendar documents say
  20) and the quota's unit are not agreed in Pulse (DEFINITIONS_TO_AGREE 15 and 26).
- A failed transcription keeps the parts that succeeded (`"complete": false`);
  re-running needs `force` and pays for every part again.
