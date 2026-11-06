---
name: translate-subtitles
description: Turn a transcribed video's mixed-language subtitles into English-only, Nepali-only and Nepali-as-spoken (all Devanagari) tracks (WebVTT and SRT), cue for cue with the same times, with one OpenAI text request (paid). Runs only when the user types /translate-subtitles.
argument-hint: <file> [languages en,ne] [force]
disable-model-invocation: true
---

# Translate subtitles

Request: `$ARGUMENTS`

Processor: `processors/translate-subtitles/`. Steps: prepare (free, local) → translate
(paid, one OpenAI request, text only, also runs finalize). It reads the transcript
`/transcribe` saved for the file and builds the same cues and times as its
`transcript.vtt`; it never sends the file. The track in the language most of the speech
is in (Nepali, for most videos) is put together by the scripts: each cue exactly as said,
with only the words said in the other language (spans) replaced by the model's rendering,
so no word said in that language can be reworded. It makes two such tracks: the spans
translated (`transcript.ne`) and the spans written in Devanagari by their sound
(`transcript.ne-spoken`). Words matching `heard_as` in `organisation.json` are spans too;
the model writes the organisation's name there only where the cue is about it. The other
track is the model's translation of each whole cue. Every track keeps the same cues and times, so they stay in
step with the video. The organisation's name is spelled
as `organisation.json` gives it. Spoken names stay in every track: subtitles say what was
said. The translations are drafts for a speaker of each language to check. Do not open
the subtitle files or `translation.json` unless the user asks.

## 1. Prepare

Run `python3 processors/translate-subtitles/prepare.py <file>`, adding
`--languages en`, `--languages ne` or `--languages en,ne` when the request names them
[both], and `--force` if the user says again, redo or force. If the file is not found,
look in `input/` for a close match and ask before using it. If prepare stops with an
error about a language, tell the user it accepts English (en) and Nepali (ne). Stop.

Read the JSON it prints:

- `"status": "missing_inputs"`: run `/transcribe` on the file first. Stop.
- `"status": "no_speech"`: the transcript holds no speech; there is nothing to
  translate. Stop.
- `"status": "already_done"`: tell the user where the output is and that `force` would
  be charged again (the current result then moves to `history/`). Stop.
- `"status": "outdated"`: the transcript was made again, or `organisation.json`
  changed, after this translation. Offer `force` (charged again). Stop.
- `"status": "different_options"`: say which languages were saved and which are asked
  for (`changed`). Offer `force` (charged again). Stop.
- `"status": "ready"`: before step 2, copy `summary_text` into your reply as printed,
  inside a fenced text block. The user approves the paid step at its permission prompt.

## 2. Translate

Run `python3 processors/translate-subtitles/translate.py <job_dir>` once, with `job_dir`
from step 1. Never retry it, and never reach OpenAI any other way. If it stopped after
the answer arrived, running it again on the same job sends nothing and only writes the
outputs.

Read the JSON it prints:

- `"status": "complete"` or `"incomplete"`: go to step 3.
- `"status": "failed"`: explain `error.code`:
  - `invalid_api_key` or status 401: the OpenAI key is wrong.
  - `model_not_found`, status 403 or 404: the key cannot use this model; set
    `OPENAI_TRANSLATE_MODEL` in `.env` to one it can use.
  - `insufficient_quota`: no credits left on the OpenAI account.
  - `rate_limit_exceeded`: too many requests; try again later.
  - `network`: the connection failed; the request may or may not have been charged.
  - `missing_key`: `OPENAI_API_KEY` is not in `.env`; suggest `/setup`.
  - `refusal`: the model declined (charged). Do not run it again without asking the
    user.
  - `bad_output`: the answer arrived (and was charged) but could not be read. Do not run
    it again without asking the user.
  - `max_output_tokens`: the answer was cut off at the output limit (charged, nothing
    saved). Do not run it again without asking the user; one language at a time makes
    the answer shorter.

## 3. Report

In a few lines: the output folder, the files (`transcript.en.vtt`, `transcript.en.srt`,
`transcript.ne.vtt`, `transcript.ne.srt`, `transcript.ne-spoken.vtt`, `transcript.ne-spoken.srt`
for the tracks made, `translation.json`,
`metadata.json`), where the replaced result went (`previous_result`, if set), the cues
and how many were translated per language (`translated`), answers for cues that were not
sent (`dropped`), the requests and tokens used (`usage`), and any warnings. `translated`
counts whole cues per translated language and spans for the assembled one. Then quote
word for word, each under its own heading when it has any entry:

- `missing` (when the status is `incomplete`): spans or cues without a translation; they
  keep the words as said.
- `checks`: what a speaker should look at (a Nepali cue without Devanagari, Latin
  letters left in the as-spoken track, an English one with Devanagari left in, a number the translation lacks, a track that kept less
  than 90% of the words said in its own language, a cue too long for two lines that
  shows as several cues within its time).
- `review_notes`: what the model flags (unclear cues, names it was unsure how to write).

Say that the times are those of `transcript.vtt` (estimated within each transcript part)
and that the translations are machine-made drafts for a speaker of each language to
check before publishing. Do not show the subtitles unless the user asks. A correction the
user asks for goes into a new file next to the track; never edit the saved result.
