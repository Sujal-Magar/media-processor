---
name: generate-copy
description: Draft social media copy for a video from its transcript, visual tags and topic tags (hooks, an edit script with soundbites and B-roll, captions per platform, hashtags, an optional translation), with one OpenAI text request (paid). Runs only when the user types /generate-copy.
argument-hint: <file> [platforms] [tone] [language] [translate to] [brief] [force]
disable-model-invocation: true
---

# Generate copy

Request: `$ARGUMENTS`

Processor: `processors/generate-copy/`. Steps: prepare (free, local) → generate (paid, one
OpenAI request, text only, also runs finalize). It reads the results `/transcribe`,
`/tag-visuals` and, if run, `/tag-topics` saved for the same file, and never sends the
file itself. The organisation's own details come from `organisation.json` (its name as
written, other names, website, hashtags, a note); speech-to-text can mishear a name, so
this file is the spelling the copy uses. The copy is a draft for a person to approve;
nothing is published. Do not open `copy.md` or `copy.json` unless the user asks.

## 1. Prepare

Run `python3 processors/generate-copy/prepare.py <file>` with these options when the
request gives them (leave the rest out; the defaults are in brackets):

- `--platforms instagram-reels,tiktok,linkedin`: any of `instagram-reels`, `tiktok`,
  `linkedin`, `youtube-shorts` [the first three]
- `--language <name or en/ne/hi>`: the language to write in [English]
- `--translate <name or en/ne/hi>`: also give the hooks and captions in this language
  [none]
- `--tone "<words>"`: tone of voice, at most 200 characters [natural for each platform]
- `--brief "<text>"`: what the copy is for (a campaign, an intake, a call to action), at
  most 1000 characters [none]
- `--force` if the user says again, redo or force

Quote the tone and brief for the shell exactly as the user wrote them. If the file is
not found, look in `input/` for a close match and ask before using it. If prepare stops
with an error about an option, tell the user what it accepts and stop.

Read the JSON it prints:

- `"status": "missing_inputs"`: name the skills in `missing` (`/process-video` runs
  both). Stop.
- `"status": "already_done"`: tell the user where the output is and that `force` would
  be charged again (the current result then moves to `history/`). Stop.
- `"status": "outdated"`: the transcript, visual tags or topic tags were made again, or
  added, or `organisation.json` changed, after this copy was written. Offer `force`
  (charged again). Stop.
- `"status": "different_options"`: list each entry of `changed` as "<option>: saved
  <saved>, now <requested>". When a saved tone or brief would become null, say plainly
  that `force` writes the copy without it, and that repeating it in the request keeps
  it. Offer `force` (charged again; the current result moves to `history/`). Stop.
- `"status": "ready"`: before step 2, show `summary` as a bulleted list, every line
  word for word and in order, with nothing left out or merged into a sentence. A lack
  of warnings is not approval: the user approves the paid step at its permission
  prompt.

## 2. Generate

Run `python3 processors/generate-copy/generate.py <job_dir>` once, with `job_dir` from
step 1. Never retry it, and never reach OpenAI any other way. If it stopped after the
answer arrived, running it again on the same job sends nothing and only writes the
outputs.

Read the JSON it prints:

- `"status": "complete"` or `"incomplete"`: go to step 3.
- `"status": "failed"`: explain `error.code`:
  - `invalid_api_key` or status 401: the OpenAI key is wrong.
  - `model_not_found`, status 403 or 404: the key cannot use this model; set
    `OPENAI_COPY_MODEL` in `.env` to one it can use.
  - `insufficient_quota`: no credits left on the OpenAI account.
  - `rate_limit_exceeded`: too many requests; try again later.
  - `network`: the connection failed; the request may or may not have been charged.
  - `missing_key`: `OPENAI_API_KEY` is not in `.env`; suggest `/setup`.
  - `refusal`: the model declined to write it (charged). Do not run it again without
    asking the user.
  - `bad_output`: the answer arrived (and was charged) but could not be read. Do not
    run it again without asking the user.
  - `max_output_tokens`: the answer was cut off at the output limit (charged, nothing
    saved). Do not run it again without asking the user; fewer platforms or no
    translation make the answer shorter.

## 3. Report

In a few lines: the output folder, the files (`copy.md`, `copy.json`, `metadata.json`),
where the replaced result went (`previous_result`, if set), how many hooks and script
segments it kept, the platforms with a caption (`captions`), the hashtags per cluster,
the translation language (each hook and caption carries its own translation), how many
hooks and segments were dropped because they cited no footage that was sent or
repeated another (`dropped`), the requests and tokens used (`usage`), and any warnings.
Then quote word for word, each under its own heading when it has any entry:

- `missing` (when the status is `incomplete`): parts the request asked for and the copy
  lacks.
- `checks`: what a reviewer must look at before posting (a caption too long, a brand
  hashtag nothing confirms, a soundbite cut mid-sentence, on-screen text repeated word
  for word).
- `review_notes`: what the model flags (the brief not fitting the footage, a name
  spelled differently in the speech and on screen, a claim to check).

Do not show the copy unless the user asks.

The copy is drafted by a model (`review_status: draft`). Every hook, soundbite and
B-roll cue lists the footage it rests on so it can be checked; soundbite times are per
transcript part, not per sentence. People are never named. Never present the copy as
approved or its claims as verified. A rewrite, shortening or other change the user asks
for goes into a new file next to `copy.md`; never edit the saved result.
