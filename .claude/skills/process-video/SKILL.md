---
name: process-video
description: Run every video processor on one video - speech transcription (ElevenLabs) and visual tagging (OpenAI) in parallel, then topic tagging (OpenAI) from both results (paid). Runs only when the user types /process-video.
argument-hint: <video> [speakers] [language ...] [timestamps [s]] [track N] [normalize] [every N seconds] [max N frames] [high detail] [no text pass] [force]
disable-model-invocation: true
---

# Process video

Request: `$ARGUMENTS`

Runs the `transcribe` and `tag-visuals` processors on the same video, with visual tagging
in the background while the transcription runs, then `tag-topics` on both results. Read
`.claude/skills/transcribe/SKILL.md`, `.claude/skills/tag-visuals/SKILL.md` and
`.claude/skills/tag-topics/SKILL.md` now: they define each processor's flags, statuses,
paid calls and error messages. Follow them, except for the order below.

Split the request between them:

- speech words (speakers, language, timestamps, track, normalize) → transcribe;
- picture words (every N seconds, max N frames, high detail, no text pass) → tag-visuals;
- `force` → all three.

## 1. Prepare both (free)

If the request names a language, first ask the language question from the transcribe
skill and wait for the answer.

Run both prepare commands in one message so they run at the same time:

- `python3 processors/transcribe/prepare.py <video> [transcribe flags]`
- `python3 processors/tag-visuals/prepare.py <video> [tag-visuals flags]`

Handle each status as its own skill says. If one has nothing to do (already done, silent
audio, no picture), continue with the other. Then tell the user the plan in two lines:
ElevenLabs requests and audio length; OpenAI requests, frames, model, detail and the
estimated input tokens (`estimated_input_tokens`), plus, if `text_reread_estimate` is set,
"up to `max_requests` re-read request(s) of about `input_tokens_per_frame` tokens per
frame, only if small text is found". Below
them, quote each prepare's `warnings` word for word, and describe only options that
prepare printed. Add a third line: one more OpenAI request (topics, text only) follows
once both are done; its estimate is shown before it is sent.

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

## 5. Tag topics

Wait until both have finished. Run tag-topics only if each one completed in this run or
had nothing to do (already done, silent audio, no picture). If either failed or ended
`incomplete`, skip it: topics made from partial or old material would be paid for and
then be outdated as soon as that processor is finished. Say that topics wait until both
are complete, and that `/tag-topics <video>` makes them afterwards.

Otherwise follow steps 1 and 2 of the tag-topics skill on the same video, with `--force`
if the request had `force`. Show its plan (step 1, `ready`) in one line before running
`tag.py`. If prepare says `missing_inputs`, `already_done` or `outdated`, report that and
go on to the report. A failure here does not undo the other two.

## 6. Report

One short section per processor (transcribe, tag-visuals, tag-topics: output folder,
files, counts, warnings, as each skill describes), then one line with the paid requests
per provider. A failure in one processor does not undo the others; report it with that
skill's guidance. Do not open
or quote the transcript or the tags unless the user asks.
