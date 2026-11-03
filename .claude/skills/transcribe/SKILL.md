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

| User says                                | Flag                                                 |
| ---------------------------------------- | ---------------------------------------------------- |
| speakers, diarize, who said what         | `--diarize`                                          |
| a language (Nepali, English, Hindi, ...) | `--language <ISO 639-3>`: `nep`, `eng`, `hin`, ...   |
| timestamps, parts, chunks                | `--part-seconds <N>` (use 120 if no number is given) |
| track N, second track, other mic         | `--track <N>` (0 = first track)                      |
| quiet, normalize                         | `--normalize`                                        |
| again, redo, force                       | `--force`                                            |

If the file is not found, look in `input/` for a close match and ask before using it.

Run it and read the JSON it prints:

- `"status": "already_done"` or `"previous_incomplete"`: tell the user where the output is
  and that `force` would be charged again. Stop.
- `"status": "silent"`: pass on the message (it may suggest another track). Stop. Nothing
  was sent to ElevenLabs.
- `"status": "ready"`: tell the user the number of paid requests (`paid_requests`) and the
  audio length (`audio_seconds`), plus any `warnings`. Continue.

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

A successful call only answers "Transcription saved to ...". The transcript is in
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
`transcript.json`, `metadata.json`), parts transcribed out of total, and any warnings. If
the status is `incomplete`, say which part failed and that re-running needs `force` (and
is charged again for every part).
