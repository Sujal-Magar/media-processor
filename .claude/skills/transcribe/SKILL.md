---
name: transcribe
description: Transcribe speech in an audio or video file with ElevenLabs speech-to-text (paid). Runs only when the user types /transcribe.
argument-hint: <file> [speakers] [language nepali|english] [timestamps [seconds]] [track N] [normalize] [force]
disable-model-invocation: true
---

# Transcribe

Request: `$ARGUMENTS`

Processor: `processors/transcribe/`. Three steps: prepare (free, local) → one request per
part (paid, MCP) → finalize (free, local). Do not open or print transcript text at any
point unless the user asks for it.

## 1. Prepare

Turn the request into flags for `python3 processors/transcribe/prepare.py <file>`:

| User says                                | Flag                                                                                                     |
| ---------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| speakers, diarize, who said what         | `--diarize`                                                                                              |
| a language (Nepali, English, Hindi, ...) | `--language <ISO 639-3>`: `nep`, `eng`, `hin`, ... (ask first, see below)                                |
| timestamps, parts, chunks                | `--part-seconds <N>` (use 120 if no number is given; a part may run up to 10 % longer to end at a pause) |
| track N, second track, other mic         | `--track <N>` (0 = first track; "track 1" may mean the first, so check the error's track list)           |
| quiet, normalize                         | `--normalize`                                                                                            |
| again, redo, force                       | `--force`                                                                                                |

If the file is not found, look in `input/` for a close match and ask before using it.

If the request names a language, ask before running prepare: "Forcing <language> can make
ElevenLabs translate speech in other languages into it, or leave it out; auto-detect
keeps mixed speech as spoken. Force <language>, or auto-detect?" Wait for the answer and
add `--language` only if the user keeps it.

Run it and read the JSON it prints:

- `"status": "already_done"` or `"previous_incomplete"`: tell the user where the output is
  and that `force` would be charged again (the current result is then kept in `history/`).
  Stop.
- `"status": "silent"`: pass on the message (it may suggest another track). Stop. Nothing
  was sent to ElevenLabs.
- `"status": "ready"`: tell the user the number of paid requests (`paid_requests`) and the
  audio length (`audio_seconds`), and quote each entry of `warnings` word for word. If
  `replaces` is set, say that the current result moves to `history/` in the output folder
  when the new one is saved. Continue.

Describe only the options prepare printed (`language_code`, `diarize`, `part_seconds`,
`normalize`). Never say an option was requested or applied when the output shows it was
not. A warning's suggestion (such as `--normalize`) is something the user may choose for a
re-run (`normalize force`); don't present it as done.

## 2. Transcribe each part

For each entry in `parts`, in order, one at a time (never in parallel), call
`mcp__elevenlabs__speech_to_text` exactly once with:

| Parameter                              | Value                                                              |
| -------------------------------------- | ------------------------------------------------------------------ |
| `input_file_path`                      | the part's `audio`                                                 |
| `output_directory`                     | the part's `transcript_dir`                                        |
| `save_transcript_to_file`              | `true`                                                             |
| `return_transcript_to_client_directly` | `false`                                                            |
| `diarize`                              | `diarize` from the prepare output                                  |
| `language_code`                        | `language_code` from the prepare output; omit it when it is `null` |

A successful call only answers "Transcription saved to ...". That path is the part's input
audio (`audio.m4a` or `part_NNN.m4a`), not the transcript: the server version used here
names the wrong file. This is normal, not an error; carry on. The transcript is in
`transcript_dir`; do not read it.

If a call fails:

- Do not retry it and do not continue with later parts. ElevenLabs may already have
  charged for it.
- Go to step 3 anyway, so the parts that succeeded are saved.
- Explain the error: `invalid_api_key` = wrong key; `quota_exceeded` = out of credits;
  `missing_permissions` = the key lacks speech-to-text access; `429` or
  `too_many_concurrent_requests` = rate limit, try again later; `outside of allowed directory`
  = file not in `work/` (re-run step 1).

If the `mcp__elevenlabs__*` tools are not available, stop and suggest `/setup`. Never use
curl, the ElevenLabs REST API or any other tool instead.

## 3. Finalize

Run `python3 processors/transcribe/finalize.py <job_dir>` with `job_dir` from the prepare
output.

Report back in a few lines: the output folder, the files written (`transcript.md`,
`transcript.json`, `metadata.json`), parts transcribed out of total, where the replaced
result went (`previous_result`, if set), and any warnings. If
the status is `incomplete`, say which part failed and that re-running needs `force` (and
is charged again for every part).
