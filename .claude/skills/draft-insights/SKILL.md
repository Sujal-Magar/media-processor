---
name: draft-insights
description: Draft strategic insights for a month (why each flagged result may have happened, as hypotheses to test, plus a proposed asset request and a client card draft) from the anomaly rules' triggers and the month's numbers, with one OpenAI text request (paid). Runs only when the user types /draft-insights.
argument-hint: <trigger file, e.g. input/insights/2026-10.json> [force]
disable-model-invocation: true
---

# Draft insights

Request: `$ARGUMENTS`

Processor: `processors/draft-insights/` (Pulse C18b, strategic insight inference). Steps:
prepare (free, local) → draft (paid, one OpenAI request, text only, also runs finalize).
The input is one month's triggers as Pulse's anomaly rules (C18a) would raise them
(shape: `fixtures/insights-input.example.json`): the 90-day baseline, the posting quota
and each rule that fired. Prepare reads the posts from the report inputs in
`input/reports/` whose months the baseline window covers, re-checks every trigger
against the numbers, works out the comparisons between groups of posts and, for posts
made from a video in `input/`, reads the topic tags, hook, call to action and visual tags
earlier processors saved. It never sends a file. Every insight is `Proposed`, for the
strategist to review; nothing is sent to the client, and acceptance and asset requests
are not part of it. Do not open `insights.md` or `insights.json` unless the user asks.

## 1. Prepare

Run `python3 processors/draft-insights/prepare.py <trigger file>`, with `--force` if the
user says again, redo or force. If no file is given, list `input/insights/` and ask which
month. If prepare stops with an error, quote it: it names the field of the input that
does not fit the shape, or the trigger the month's numbers do not bear out. Stop.

Read the JSON it prints:

- `"status": "nothing_to_send"`: every trigger was held back (or there were none). Quote
  `held_back` and `warnings`; nothing was charged. Stop.
- `"status": "already_done"`: tell the user where the output is and that `force` would
  be charged again (the current result then moves to `history/`). Stop.
- `"status": "outdated"`: a report input in the baseline window, a post's topic tags,
  copy or visual tags, or `organisation.json` changed after these insights were drafted.
  Offer `force` (charged again). Stop.
- `"status": "ready"`: before step 2, copy `summary_text` into your reply exactly as
  printed, inside a fenced text block, and nothing in its place: do not reword, shorten,
  merge, reorder or describe it, and do not leave out a line or a warning (the triggers
  held back and the posts the baseline counts but the inputs lack are the lines the user
  most needs). You may add one sentence after the block. A lack of warnings is not
  approval: the user approves the paid step at its permission prompt.

## 2. Draft

Run `python3 processors/draft-insights/draft.py <job_dir>` once, with `job_dir` from
step 1. Never retry it, and never reach OpenAI any other way. If it stopped after the
answer arrived, running it again on the same job sends nothing and only writes the
outputs.

Read the JSON it prints:

- `"status": "complete"` or `"incomplete"`: go to step 3.
- `"status": "failed"`: explain `error.code`:
  - `invalid_api_key` or status 401: the OpenAI key is wrong.
  - `model_not_found`, status 403 or 404: the key cannot use this model; set
    `OPENAI_INSIGHT_MODEL` in `.env` to one it can use.
  - `insufficient_quota`: no credits left on the OpenAI account.
  - `rate_limit_exceeded`: too many requests; try again later.
  - `network`: the connection failed; the request may or may not have been charged.
  - `missing_key`: `OPENAI_API_KEY` is not in `.env`; suggest `/setup`.
  - `refusal`: the model declined to write it (charged). Do not run it again without
    asking the user.
  - `bad_output`: the answer arrived (and was charged) but could not be read. Do not
    run it again without asking the user.
  - `max_output_tokens`: the answer was cut off at the output limit (charged, nothing
    saved). Do not run it again without asking the user.

## 3. Report

In a few lines: the output folder, the files (`insights.md`, `insights.json`,
`metadata.json`), where the replaced result went (`previous_result`, if set), each
insight's trigger, hypotheses, proposed request and the hypothesis it tests (`insights`;
`total_ask` adds the month's requests up;
the quota trigger has none, since the numbers cannot say why fewer posts went out), the
triggers answered
with not enough evidence (`not_enough_evidence`), how many were held back (`held_back`)
and dropped for citing no data that was sent (`dropped`), the requests and tokens used
(`usage`), and any warnings. Then quote word for word, each under its own heading when
it has any entry:

- `missing` (when the status is `incomplete`): parts an insight needs and lacks, a
  trigger with no answer, a quantity the request may not ask for.
- `checks`: what the strategist must look at: a number that matches nothing in the data
  (this also makes the draft `incomplete`), a number from data the sentence does not
  cite, a ratio the comparisons do not give, a cause stated as fact, a hypothesis not
  worded as a possibility or without its test, a test that names no measure, a request
  that does not say which hypothesis it tests, a test whose bar is below the 90-day
  average or the cited group's average, a hypothesis worded as advice, a request
  category the format comparison contradicts, two requests for the same kind of post
  that nothing sets apart, a card action that repeats its finding, an engagement rate given as a count on the client card, an
  internal term or jargon on the card (including "catch up"), a reference (P2) written into the text, a button longer than 5 words or
  without a quantity.
- `review_notes`: what the model flags for the strategist.

Do not show the insights unless the user asks.

Some parts are not the model's: each client card's first sentence is written from the
trigger's numbers, comparisons for a trigger leave out its own post (and the same video
posted again), a hypothesis citing no comparison for its trigger is dropped (and a
trigger no comparison bears on becomes "not enough evidence"), and the quota trigger's
request size is set from the gap (at most 3).

The insights are written by a model (`review_status: draft`, each `Proposed`) from
numbers that stand in for Pulse's analytics and anomaly rules. The hypotheses are
possibilities to test, never findings: present them that way. Every number was worked
out by prepare; every sentence lists the data it rests on. People are never named, not
even the strategist. Never present an insight as accepted, a request as created, or a
hypothesis as verified. A rewrite or edit the user asks for goes into a new file next to
`insights.md`; never edit the saved result.
