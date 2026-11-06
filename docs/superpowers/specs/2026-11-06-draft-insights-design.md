# draft-insights: strategic insight drafts (Pulse C18b)

Agreed in chat on 2026-11-06.

## Problem

Pulse's anomaly rules (C18a, deterministic) flag posts and months that stand out:
engagement far above the tenant's usual, viewers leaving in the first 3 seconds, posting
behind quota. Pulse wants each flag turned into a proposal the client can accept: why it
may have happened and what to make next ("Success-story videos got 3.2× your average
reach. Send us two more this month."). That is C18b (DFD_05 §5.6). C18a, C15 analytics,
the insights store (D5), acceptance and C07 asset requests do not exist here, so their
inputs are mocked and only the model part is built.

Sources: DFD_05_Reports_and_Results.md:195-220, :302-315, :352-358, :435;
PROCESS_DETERMINISM_MAPPING.md:25-27; COMPONENT_DETERMINISM.md:49;
PROJECT_COMPONENT_ANALYSIS.md:305-308; DFD_04_Request.md:244-253, :357-359;
DEFINITIONS_TO_AGREE.md:19, :30; the cards in Assets and Results.dc.html:243-246 and
Approvals and Home.dc.html:214-216; PRD:102, :132, :218; Pulse Design System.dc.html:622.

## Decisions

1. **New processor `draft-insights`**, run as `/draft-insights <trigger file> [force]`.
   prepare (free) → `draft.py` (paid, one OpenAI text request, never retried, runs
   finalize). Results in `output/draft-insights/<month>-<hash8>/`, hashed from the
   trigger file; `history/` on force.
2. **Mock C18a input:** `input/insights/<YYYY-MM>.json` (git-ignored), shape in
   `fixtures/insights-input.example.json`: the baseline, the quota and the triggers
   (below). Prepare reads the same month's `input/reports/<YYYY-MM>.json` for the posts
   and snapshots (D1/D2) and records it among the inputs, so a changed report file makes
   the result `outdated`.
3. **The rules as mocked:**
   - `engagement_gt_200pct_mean`: a post's `true_engagement_rate` above 2.0 × the
     baseline's 90-day mean.
   - `hook_dropoff_gt_45pct`: 3-second drop-off, read as `100 − retention_3s_pct`, above
     45.
   - `pace_behind_quota`: `quota − published` of at least 2, with a quota of 16 posts a
     month (the screens; the calendar DFDs say 20).

   Prepare re-checks every trigger against the snapshot and stops with an error naming the
   field when one does not hold. A trigger on a Partial or Stale post is held back: it is
   listed as incomplete, never sent, and that post is left out of every comparison.
4. **All numbers come from prepare.** It computes each trigger's size (10.23% is 2.2× the
   90-day mean of 4.6%), the drop-off, the slots behind, and the group comparisons (item 5).
   The model gets these results and may only cite them. Finalize checks every number,
   sentence by sentence, against the data that sentence cites (`lib/numbers.py`).
5. **Group comparisons:** among Full posts in the baseline window (the report files in
   `input/reports/` whose posts fall inside it), prepare compares groups by content
   pillar, platform, language, hook style and visual tag (such as `speaking-to-camera`)
   on engagement rate, reach and 3 s / 10 s retention. A group needs 2 or more posts on
   each side. Every comparison carries its post counts and is given a reference (`G1`).
6. **"Why" as labelled hypotheses**, never as fact. Each one is worded as a possibility,
   cites its evidence and post counts, and says what result would confirm or refute it.
   Finalize flags causal wording ("because", "drove", "led to") outside a hypothesis, and a
   hypothesis that is not worded as a possibility. This meets "hypothesize why"
   (DFD_05:213) without breaking "never invent causal relationships"
   (PROCESS_DETERMINISM_MAPPING:27).
7. **The action** carries the fields an asset request (I03/F19) needs, as a draft: `title`,
   `category` (`photo`, `video`, `story`), `quantity`, `due_month` (next month),
   `language` (`en`, `ne` or `any`), a one-sentence `brief`, and refs. Prepare gives the
   allowed quantities (1 to 3, capped by the open quota slots); finalize checks the
   quantity is one of them, so the model never picks a number freely.
8. **Two texts per insight:** for the strategist, the observation, hypotheses and action;
   and a client card draft in the style of the Results card: one finding sentence in
   people terms, one action sentence, and a button label (at most 5 words). No names, not
   even the strategist's (the card's "for Anisha" is filled in by the portal, not the
   model).
9. **Status:** every insight is `Proposed` (D5) and the file is `review_status: draft`.
   The strategist reviews it first; nothing reaches the client. Acceptance, dismissal and
   conversion are out of scope.
10. **Counts:** at most one insight per trigger and 3 a month. The model may answer "not
    enough evidence" for a trigger instead (PROJECT_COMPONENT_ANALYSIS:308); that is kept
    and shown, not dropped.
11. **Language:** text in English. An action may ask for Nepali footage when a comparison
    supports it.
12. **Material per post made from a video in `input/`:** its topic summary and tags
    (`/tag-topics`), the hook it used and its platform caption's call to action
    (`/generate-copy`), and its most-seen visual tags (`/tag-visuals`). No full transcript.
    Other posts have only platform, pillar, language and snapshot.
13. **Model:** `OPENAI_INSIGHT_MODEL`, defaulting to the vision model, in `.env.example`,
    `scripts/check_setup.py` and the `/setup` skill.
14. **Shared code:** the causal, jargon and internal-term patterns move from
    `processors/draft-report/finalize.py` to `lib/wording.py`, and reading a month's
    report input (`read_month` and its helpers) moves from draft-report's prepare to
    `lib/report_input.py`, so both processors use one copy (the processors' scripts share
    module names and cannot import each other). draft-report's behaviour and tests stay
    the same.
15. **Comparisons are merged:** groups holding the same posts (several visual tags of
    the same videos; TikTok posts that are also the Nepali ones) are one comparison
    naming each, and one that only swaps the sides of another is left out.
16. **A hypothesis's test** (what would confirm or refute it) may use its trigger's and
    the baseline's numbers as well as what the hypothesis cites; the dry run showed these
    were the only false alarms otherwise.

## Changes after the first paid October run (F-036 to F-044)

- Comparisons group a video by every visual tag it has (the model still reads the 8 on
  screen longest), add video vs picture posts, need 2 different pieces of content on
  each side (a video posted twice is one), leave out differences under 10%, and say when
  a side holds the own post of a trigger they bear on (F-036, F-037, F-040).
- The quota trigger gets no hypotheses: the numbers cannot say why fewer posts went out.
  finalize drops any the model writes and keeps its reason (F-042).
- Each request names the one hypothesis it tests (`tests`; 0 for the quota trigger), asks
  for 2 by default and up to 3 for the quota trigger, and changes only what that
  hypothesis is about (F-037, F-038). Quantities stay capped by next month's quota, not
  this month's gap, since the requests are for next month.
- Tests name their measure; the card gives an engagement rate as a share or its ratio,
  carries its number, and its button says how many; "slots" is an internal term
  (F-039, F-041, F-043). finalize checks each, and flags two requests asking for the same
  thing.
- `insights.md` lists every report input in the window (F-044). The token estimate is
  left as it is (the shared estimator is rough by design; 7.6% under here).

## Changes after runs 2 and 3 (F-045 to F-051; user's choices 2026-11-06)

- The client card's finding is written by code from the trigger, one sentence per rule
  ("A bigger share of the people who saw your Nepali TikTok video liked, commented on,
  shared or saved it: 2.2× your usual."); the model writes only the card's action and
  button (F-048, user's choice over keeping the model's sentence with a check).
- A trigger's comparisons are the groups its post belongs to, worked out without the
  post and the same video posted again, so a post never explains itself; the pace
  trigger's are groups doing better than the rest; at most 8 per trigger (F-051, user's
  choice over keeping the post and flagging).
- Each post trigger gives the bar a test must beat (the 90-day average engagement rate,
  or the average still watching after 3 s); finalize flags a test confirmed below it
  (F-045).
- The quota trigger's request size is set from the gap (at most 3) (F-049); prepare
  works out which format the numbers favour, and finalize flags a category against it
  (F-047). The look-alike check reads title and brief at 0.25 (F-046). Visual tags
  equally long on screen list activities first, up to 12 (F-050). "catch up" and
  "pillars" are client-card terms.

## Changes after runs 4 and 5 (F-052 to F-055)

- A hypothesis about a post trigger must cite a comparison that bears on that trigger;
  finalize drops one that does not, and a post trigger no comparison bears on becomes
  "not enough evidence" in code. Prepare tells the model when a trigger has none (F-052).
- The request changes only what the cited comparison is about (pillar, platform,
  language, format, hook style); the instruction's "another opening" example is gone
  (F-053).
- The card action and button may use their trigger's numbers, so they raise no false
  "not in what it cites" check; an action that gives the trigger's numbers again, or
  shares half its words with the finding, is flagged as repeating it (F-054).
- Two requests are the same when they share the category and the first pillar their
  title or brief names ("educational videos"); word overlap could not separate them
  (F-055). On runs 1 to 5 this flags exactly the three duplicates.

## Changes after runs 6 and 7 (F-053, F-057 to F-059)

- Requests may ask for the same kind of post when the evidence points there; each brief
  then says what sets it apart. The look-alike check leaves out the quota request and
  flags a pair only when nothing sets it apart (language, platform named, kinds of
  comparison behind the tested hypothesis); the result gives the month's total ask
  ("Requests for November 2026: 7 videos (T1 2, T2 2, T3 3).") (F-057).
- A hypothesis's bar is the higher of the 90-day average and the average of each group it
  cites on the trigger's measure, checked per hypothesis by finalize (F-058).
- The request's language is the one its title or brief names, when it names exactly one
  (F-059).
- A hypothesis is a possible reason, never advice; finalize flags "worth testing",
  "consider", "should" and the like (F-053).

## Trigger file (example)

```json
{
  "month_period": "2026-10",
  "evaluated_at": "2026-10-31T23:59:00+00:00",
  "baseline": {
    "window_days": 90, "window_start": "2026-08-03", "window_end": "2026-10-31",
    "posts": 21, "engagement_rate_mean": 4.6, "engagement_rate_sd": 1.9,
    "retention_3s_mean": 58.0
  },
  "quota": { "monthly_posts": 16, "published": 8 },
  "triggers": [
    { "trigger_rule_id": "engagement_gt_200pct_mean", "content_item_id": "ci-2610-02" },
    { "trigger_rule_id": "hook_dropoff_gt_45pct", "content_item_id": "ci-2610-03" },
    { "trigger_rule_id": "pace_behind_quota", "content_item_id": null }
  ]
}
```

## Result (example, one insight)

```json
{
  "month_period": "2026-10",
  "review_status": "draft",
  "insights": [
    {
      "trigger": "T1", "status": "Proposed",
      "observation": { "text": "…", "refs": ["T1", "P2"] },
      "hypotheses": [
        { "text": "…may…", "refs": ["G2", "P2"], "confirm_if": "…", "refute_if": "…" }
      ],
      "action": { "title": "…", "category": "video", "quantity": 2, "due_month": "2026-11",
                  "language": "any", "brief": "…", "refs": ["G2"] },
      "client_card": { "finding": "…", "action": "…", "button": "Send us 2 more videos" }
    }
  ],
  "not_enough_evidence": [],
  "held_back": [],
  "checks": [],
  "review_notes": []
}
```

## Mock months

- **2026-10:** `engagement_gt_200pct_mean` on ci-2610-02, `hook_dropoff_gt_45pct` on
  ci-2610-03, `pace_behind_quota` (8 of 16).
- **2026-09:** `hook_dropoff_gt_45pct` on ci-2609-01 and ci-2609-06, a trigger on Partial
  ci-2609-04 (held back), `pace_behind_quota` (6 of 16).
- A month with no triggers is a unit test: prepare stops with nothing to send and no cost.

## Tests

1. Unit tests in `tests/`: prepare (trigger re-checks, Partial held back, baselines,
   ratios, group comparisons and their minimum size, allowed quantities, no triggers),
   draft (schema and instructions, payload), finalize (numbers per sentence, ratios,
   causal wording, hypothesis wording, quantity, category, due month, button length,
   unknown refs dropped, not-enough-evidence kept, status, partial data).
2. A free dry run on both mock months with a hand-written answer through finalize.
3. After approval, one paid run per month, checked against the Results card; a reviewer
   subagent logs it in `TEST_FINDINGS.md`.

## Later (not built)

Acceptance and conversion to C07 (C18a); whether accepted actions should feed the
strategist's plan that `/draft-report` rewords (C17b); the client card's strategist name
and button behaviour; a checklist field for the language of requested footage
(DFD_04:244-253 has none).
