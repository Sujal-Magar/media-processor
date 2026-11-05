---
name: tag-topics
description: Tag what a video, audio file or photo is about (type, topics, named things) from its transcript, visual tags and on-screen text, with one OpenAI text request (paid). Runs only when the user types /tag-topics.
argument-hint: <file> [force]
disable-model-invocation: true
---

# Tag topics

Request: `$ARGUMENTS`

Processor: `processors/tag-topics/`. Steps: prepare (free, local) → tag (paid, one OpenAI
request, text only, also runs finalize). It reads the results `/transcribe` and
`/tag-visuals` saved for the same file and never sends the file itself. Do not open
`topics.md` or `topics.json` unless the user asks.

## 1. Prepare

Run `python3 processors/tag-topics/prepare.py <file>`, adding `--force` if the user says
again, redo or force. If the file is not found, look in `input/` for a close match and
ask before using it.

Read the JSON it prints:

- `"status": "missing_inputs"`: nothing to read yet. Suggest `/transcribe`, `/tag-visuals`,
  or `/process-video` for both. Stop.
- `"status": "already_done"`: tell the user where the output is and that `force` would be
  charged again (the current result then moves to `history/`). Stop.
- `"status": "outdated"`: the transcript or the visual tags were made again, or one was
  added, after these topics were made. Offer `force` (charged again). Stop.
- `"status": "ready"`: tell the user which inputs it read (`inputs`), that it is one paid
  request, the model and reasoning effort, and the estimated input tokens
  (`estimated_input_tokens`, rough; reasoning adds output tokens). Quote any `warnings`
  word for word. If `replaces` is set, say that the current result moves to `history/`
  in the output folder when the new one is saved.

## 2. Tag

Run `python3 processors/tag-topics/tag.py <job_dir>` once, with `job_dir` from step 1.
Never retry it, and never reach OpenAI any other way. If it stopped after the answer
arrived, running it again on the same job sends nothing and only writes the outputs.

Read the JSON it prints:

- `"status": "complete"`: go to step 3.
- `"status": "failed"`: explain `error.code`:
  - `invalid_api_key` or status 401: the OpenAI key is wrong.
  - `model_not_found`, status 403 or 404: the key cannot use this model; set
    `OPENAI_TOPIC_MODEL` in `.env` to one it can use.
  - `insufficient_quota`: no credits left on the OpenAI account.
  - `rate_limit_exceeded`: too many requests; try again later.
  - `network`: the connection failed; the request may or may not have been charged.
  - `missing_key`: `OPENAI_API_KEY` is not in `.env`; suggest `/setup`.
  - `bad_output`: the answer arrived (and was charged) but could not be read. Do not
    run it again without asking the user.
  - `max_output_tokens`: the answer was cut off at the output limit (charged, nothing
    saved). Do not run it again without asking the user; a very long transcript is the
    usual cause.

## 3. Report

In a few lines: the output folder, the files (`topics.md`, `topics.json`,
`metadata.json`), where the replaced result went (`previous_result`, if set), the number
of tags per category (`tags`: type, topic, entity), how many are new to the library
(`new_tags`), how many tags the model gave that were dropped because their evidence was
not in what was sent, or because they repeated another (`tags_dropped`), the requests
and tokens used (`usage`), and any warnings. Do not list the tags or the summary unless
the user asks. Topic tags are made by a model: each lists its evidence (speech times,
on-screen text, visual tags) so it can be checked, and they await review
(`review_status: staging_pending`). People are never named. Never present them as
verified.

Tags are English, lowercase, with words joined by hyphens. To keep wording consistent,
`prepare.py` offers the topic tags already used in `output/tag-topics/` as a vocabulary;
tags new to it are marked `new` in `topics.json` and `(new)` in `topics.md`.
