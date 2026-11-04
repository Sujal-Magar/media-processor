---
name: process-video
description: Run every video processor on one video at once - speech transcription (ElevenLabs) and visual tagging (OpenAI) - in parallel (paid). Runs only when the user types /process-video.
argument-hint: <video> [speakers] [language ...] [timestamps [s]] [track N] [normalize] [every N seconds] [high detail] [force]
disable-model-invocation: true
---

# Process video

Request: `$ARGUMENTS`

Runs the `transcribe` and `tag-visuals` processors on the same video, with visual tagging
in the background while the transcription runs. Read
`.claude/skills/transcribe/SKILL.md` and `.claude/skills/tag-visuals/SKILL.md` now: they
define each processor's flags, statuses, paid calls and error messages. Follow them,
except for the order below.

Split the request between them:

- speech words (speakers, language, timestamps, track, normalize) → transcribe;
- picture words (every N seconds, max frames, high detail) → tag-visuals;
- `force` → both.

## 1. Prepare both (free)

Run both prepare commands in one message so they run at the same time:

- `python3 processors/transcribe/prepare.py <video> [transcribe flags]`
- `python3 processors/tag-visuals/prepare.py <video> [tag-visuals flags]`

Handle each status as its own skill says. If one has nothing to do (already done, silent
audio, no picture), continue with the other. Then tell the user the plan in two lines:
ElevenLabs requests and audio length; OpenAI requests, frames, model and detail.

## 2. Start visual tagging in the background

If tag-visuals is `ready`, run `python3 processors/tag-visuals/tag.py <job_dir>` with the
Bash tool's `run_in_background` option, and do not wait for it.

## 3. Transcribe meanwhile

If transcribe is `ready`, do steps 2 and 3 of the transcribe skill: one
`speech_to_text` call per part, in order, then `finalize.py`.

## 4. Collect

When the background tagging finishes you are notified; read the JSON it printed. If
the transcription finished first, wait for that notification. Never start `tag.py` a
second time for the same job.

## 5. Report

One short section per processor (output folder, files, counts, warnings, as each skill
describes), then one line with the paid requests per provider. A failure in one
processor does not undo the other; report it with that skill's guidance. Do not open
or quote the transcript or the tags unless the user asks.
