---
name: tag-visuals
description: Tag the objects, scenes, activities and visual attributes in a video or photo with an OpenAI vision model (paid). Runs only when the user types /tag-visuals.
argument-hint: <file> [every N seconds] [max N frames] [high detail] [no text pass] [force]
disable-model-invocation: true
---

# Tag visuals

Request: `$ARGUMENTS`

Processor: `processors/tag-visuals/`. Steps: prepare (free, local) → tag (paid, OpenAI,
also runs finalize). Do not open frames, `tags.md` or `tags.json` unless the user asks.

## 1. Prepare

Turn the request into flags for `python3 processors/tag-visuals/prepare.py <file>`:

| User says                                        | Flag                                                                                                           |
| ------------------------------------------------ | -------------------------------------------------------------------------------------------------------------- |
| every N seconds, a frame every N s               | `--interval <N>` (default 5)                                                                                   |
| max N frames, more frames, more detail over time | `--max-frames <N>` (default 60)                                                                                |
| high detail, small objects, fine detail          | `--detail high` (about 5× the tokens per landscape frame, 13× per portrait phone frame; no small-text re-read) |
| don't re-read text, cheapest                     | `--no-text-pass`                                                                                               |
| again, redo, force                               | `--force`                                                                                                      |

If the file is not found, look in `input/` for a close match and ask before using it.

Read the JSON it prints:

- `"status": "already_done"`: tell the user where the output is and that `force` would be
  charged again (the current result is then kept in `history/`). Stop.
- `"status": "previous_incomplete"`: an earlier run stopped part-way. Offer to finish it
  with `python3 processors/tag-visuals/tag.py <resume_job_dir>`, which pays only for the
  missing frames. `force` starts over and pays for everything again.
- `"status": "ready"`: tell the user the kind (video or image), the number of frames, the
  number of paid requests (`paid_requests`), the model and detail, the estimated input
  tokens for tagging (`estimated_input_tokens`, a rough figure), and, if
  `text_reread_estimate` is set, what the small-text re-read could add: "only if frames
  show text too small to read, up to `max_requests` more request(s), about
  `input_tokens_per_frame` input tokens per re-read frame (at most `max_input_tokens`);
  usually one re-read frame per shot with such text". Quote any `warnings` word for word
  (for example when `max N frames` stretched the interval). If
  `replaces` is set, say that the current result moves to `history/` in the output folder
  when the new one is saved.
- An error saying there is no picture to tag means the file is audio only; suggest
  `/transcribe`.

## 2. Tag

Run `python3 processors/tag-visuals/tag.py <job_dir>` once, with `job_dir` from step 1. It
sends the frames to OpenAI one batch at a time and then writes the outputs. At low detail
it then re-reads text that was visible but too small to read: one frame per run of such
frames, taken again from the original file at full resolution and cropped with a wide
margin around the boxes where the model saw the text (or the whole frame when it gave
none), sent at high detail. Text under 80 px in the original is not sent (too small to
read), so that run costs nothing. The re-read can add a few requests beyond
`paid_requests` (none when no frame has such text). Its text is added to the run's
frames; first-pass text the re-read didn't read again is kept but marked unconfirmed
(`confirmed: false`). High detail and `--no-text-pass` skip the re-read. Never run it twice at the same time for one job, and
never reach OpenAI any other way.

Read the JSON it prints:

- `"status": "complete"`: go to step 3.
- `"status": "incomplete"` or `"failed"`: if `resume_job_dir` is set, say that running
  `tag.py` on it again pays only for the missing frames. If `previous_result` is set (a
  `force` run), say that the previous result was moved to `history/<time>/` and the
  output folder now holds this partial result, which `tag.py <resume_job_dir>` can
  finish. Explain `error.code`:
  - `invalid_api_key` or status 401: the OpenAI key is wrong.
  - `model_not_found`, status 403 or 404: the key cannot use this model; set
    `OPENAI_VISION_MODEL` in `.env` to one it can use.
  - `insufficient_quota`: no credits left on the OpenAI account.
  - `rate_limit_exceeded`: too many requests; try again later.
  - `network`: the connection failed; that batch may or may not have been charged.
  - `missing_key`: `OPENAI_API_KEY` is not in `.env`; suggest `/setup`.
  - `batch_mismatch`: the job's saved answers don't fit its plan; nothing was sent.
    Offer `force` to start over (charged again).

## 3. Report

In a few lines: the output folder, the files (`tags.md`, `tags.json`, `metadata.json`,
`frames/`), where the replaced result went (`previous_result`, if set), frames tagged out of total, the number of distinct tags and how many are
new to the library (`new_tags`), how many pieces of on-screen text were read
(`on_screen_texts`), and the small-text re-read from `text_pass`: its `status`, the frames
with text too small to read (`frames_flagged`), and for `done` how many of the
`frames_covered` got text (`frames_with_text`) and how many re-reads came back empty
(`rereads_empty`); `frames_skipped` are frames whose text was too small in the original to
re-read. Never call flagged frames "no small text": `frames_flagged` counts them
even when the re-read was off or skipped. Then requests and tokens used (`usage`: the
totals, with `usage.tagging` and `usage.text_reread` apart), and any warnings. Do not list the tags or
the text unless the user asks. If the user relies on read text (registration numbers,
prices, dates), remind them the model can misread it or complete it from context, even
text marked `partial`, so every text must be checked against the frame. Text marked
`partial` (its `…` may not sit where the doubt is) or `confirmed: false` (read only at
low detail, and the re-read of its frame didn't read it again) is not confirmed; `tags.md`
lists both under "Partly readable or unconfirmed". Never present it as read, and never
fill in the missing characters. Confidence is the model's own estimate
and mostly `high`; tags can differ between runs and between requests for one video, and
a library tag is sometimes reused where it doesn't quite fit. Never present tags,
confidence or text as verified.

Tags are free-form so the library fits any organisation. To keep wording consistent,
`prepare.py` offers the model the tags already used in `output/tag-visuals/` as a
vocabulary (reused only when they describe exactly what is visible), and each request
after the first also sees what earlier requests for the same video answered. Truly new
tags are marked `new` in `tags.json` and `(new)` in `tags.md`; with `force`, the file's own
earlier tags are offered again but still count as new.
Tags are English, lowercase, with words joined by hyphens (`speaking-to-camera`).
Results saved before this rule still show spaces until tagged again with `force`, but
count as the same tags in the library.
