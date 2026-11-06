---
name: draft-report
description: Draft a month's client report narrative (headline, three short paragraphs, top post, highlights, tile lines, next month's plan in the client's words) from that month's numbers, with one OpenAI text request (paid). Runs only when the user types /draft-report.
argument-hint: <month file, e.g. input/reports/2026-10.json> [force]
disable-model-invocation: true
---

# Draft report

Request: `$ARGUMENTS`

Processor: `processors/draft-report/` (Pulse C17b, report narrative synthesis). Steps:
prepare (free, local) → draft (paid, one OpenAI request, text only, also runs finalize).
The input is one month's numbers as Pulse's analytics and report compilation would give
them (shape: `fixtures/report-input.example.json`): totals with the change from last
month, each platform, each post with its snapshot, the Top 3 highlights, the
strategist's plan for next month if written, earlier months, the brand voice. For posts
made from a video in `input/`, it also reads the topic tags and the hook used that
`/tag-topics` and `/generate-copy` saved. It never sends a file. The draft is for the
strategist to review, edit and sign off; nothing is sent to the client. Do not open
`report.md` or `report.json` unless the user asks.

## 1. Prepare

Run `python3 processors/draft-report/prepare.py <month file>`, with `--force` if the user
says again, redo or force. If no file is given, list `input/reports/` and ask which
month. If prepare stops with an error, quote it: it names the field of the input that
does not fit the shape. Stop.

Read the JSON it prints:

- `"status": "already_done"`: tell the user where the output is and that `force` would
  be charged again (the current result then moves to `history/`). Stop.
- `"status": "outdated"`: a post's topic tags or copy were made again (or added), or
  `organisation.json` changed, after this draft was written. Offer `force` (charged
  again). Stop.
- `"status": "ready"`: before step 2, copy `summary_text` into your reply exactly as
  printed, inside a fenced text block, and nothing in its place: do not reword,
  shorten, merge, reorder or describe it, and do not leave out a line or a warning (the
  incomplete data, the missing plan and the missing earlier months are the lines the
  user most needs). You may add one sentence after the block. A lack of warnings is
  not approval: the user approves the paid step at its permission prompt.

## 2. Draft

Run `python3 processors/draft-report/draft.py <job_dir>` once, with `job_dir` from
step 1. Never retry it, and never reach OpenAI any other way. If it stopped after the
answer arrived, running it again on the same job sends nothing and only writes the
outputs.

Read the JSON it prints:

- `"status": "complete"` or `"incomplete"`: go to step 3.
- `"status": "failed"`: explain `error.code`:
  - `invalid_api_key` or status 401: the OpenAI key is wrong.
  - `model_not_found`, status 403 or 404: the key cannot use this model; set
    `OPENAI_REPORT_MODEL` in `.env` to one it can use.
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

In a few lines: the output folder, the files (`report.md`, `report.json`,
`metadata.json`), where the replaced result went (`previous_result`, if set), the
sentences kept per part (`sentences`), the highlights and tiles with a line, how many
next-month items it kept (`next_month`; none when the input has no plan), how many
lines were dropped for citing no data that was sent (`dropped`), the requests and
tokens used (`usage`), and any warnings. Then quote word for word, each under its own
heading when it has any entry:

- `missing` (when the status is `incomplete`): parts the report needs and the draft
  lacks.
- `checks`: what the strategist must look at before approving: a number that matches
  nothing in the month's data (this also makes the draft `incomplete`), a number from
  data the sentence does not cite, a ratio, a claimed cause, an internal term or jargon,
  a comparison beyond last month without earlier months, a line resting on Partial or
  Stale data, a ranking of posts while some have incomplete numbers, a post said to
  lead (or trail) a measure that another post leads, a reference (P2) written into the
  text, a headline that hides a fall in people reached, a highlight that cites another
  post, a paragraph outside 2 to 4 sentences, an item the model wrote as several
  sentences.
- `review_notes`: what the model flags for the strategist.

Do not show the draft unless the user asks.

The draft is written by a model (`review_status: draft`) from the numbers in the input,
which stand in for Pulse's analytics. Every sentence lists the data it rests on. People
are never named. The next-month list only rewords the strategist's plan; with no plan
it stays empty, because planning the month is the strategist's (and strategic insight,
C18b, is a separate component). Never present the draft as approved or its claims as
verified. A rewrite or edit the user asks for goes into a new file next to `report.md`;
never edit the saved result.
