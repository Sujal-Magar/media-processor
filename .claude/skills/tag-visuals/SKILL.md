---
name: tag-visuals
description: Tag the objects, scenes, activities and visual attributes in a video or photo with an OpenAI vision model (paid). Runs only when the user types /tag-visuals.
argument-hint: <file> [every N seconds] [max N frames] [high detail] [force]
disable-model-invocation: true
---

# Tag visuals

Request: `$ARGUMENTS`

Processor: `processors/tag-visuals/`. Steps: prepare (free, local) → tag (paid, OpenAI,
also runs finalize). Do not open frames, `tags.md` or `tags.json` unless the user asks.

## 1. Prepare

Turn the request into flags for `python3 processors/tag-visuals/prepare.py <file>`:

| User says                                        | Flag                                   |
| ------------------------------------------------ | -------------------------------------- |
| every N seconds, a frame every N s               | `--interval <N>` (default 5)           |
| max N frames, more frames, more detail over time | `--max-frames <N>` (default 60)        |
| high detail, small objects, fine detail          | `--detail high` (costs more per frame) |
| don't re-read text, cheapest                     | `--no-text-pass`                       |
| again, redo, force                               | `--force`                              |

If the file is not found, look in `input/` for a close match and ask before using it.

Read the JSON it prints:

- `"status": "already_done"`: tell the user where the output is and that `force` would be
  charged again. Stop.
- `"status": "previous_incomplete"`: an earlier run stopped part-way. Offer to finish it
  with `python3 processors/tag-visuals/tag.py <resume_job_dir>`, which pays only for the
  missing frames. `force` starts over and pays for everything again.
- `"status": "ready"`: tell the user the kind (video or image), the number of frames, the
  number of paid requests (`paid_requests`), the model and detail, plus any `warnings`.
- An error saying there is no picture to tag means the file is audio only; suggest
  `/transcribe`.

## 2. Tag

Run `python3 processors/tag-visuals/tag.py <job_dir>` once, with `job_dir` from step 1. It
sends the frames to OpenAI one batch at a time and then writes the outputs. At low detail
it then re-reads text that was visible but too small to read: one frame per run of such frames, taken again from the original file at full resolution and cropped to the box where the model saw the text (or the whole frame when it gave none), sent at high detail, and its text is applied to the whole run. That can add a few requests beyond
`paid_requests` (none when no frame has such text). Never run it twice at the same time for one job, and never reach OpenAI any other
way.

Read the JSON it prints:

- `"status": "complete"`: go to step 3.
- `"status": "incomplete"` or `"failed"`: explain `error.code`, and if `resume_job_dir` is
  set say that running `tag.py` on it again pays only for the missing frames:
  - `invalid_api_key` or status 401: the OpenAI key is wrong.
  - `model_not_found`, status 403 or 404: the key cannot use this model; set
    `OPENAI_VISION_MODEL` in `.env` to one it can use.
  - `insufficient_quota`: no credits left on the OpenAI account.
  - `rate_limit_exceeded`: too many requests; try again later.
  - `network`: the connection failed; that batch may or may not have been charged.
  - `missing_key`: `OPENAI_API_KEY` is not in `.env`; suggest `/setup`.

## 3. Report

In a few lines: the output folder, the files (`tags.md`, `tags.json`, `metadata.json`,
`frames/`), frames tagged out of total, the number of distinct tags and how many are
new to the library (`new_tags`), how many pieces of on-screen text were read
(`on_screen_texts`), how many frames with small text were covered by the cropped full-resolution re-read
(`text_pass`: `frames_covered` of `frames_flagged`, from `frames_reread` re-read frames), requests and tokens used, and any warnings. Do not list the tags or
the text unless the user asks. If the user relies on read text (registration numbers,
prices, dates), remind them it was read by the model and should be checked against the
frame.

Tags are free-form so the library fits any organisation. To keep wording consistent,
`prepare.py` offers the model the tags already used in `output/tag-visuals/` and the
model reuses them when the meaning matches; truly new tags are marked `new` in
`tags.json` and `(new)` in `tags.md`.
