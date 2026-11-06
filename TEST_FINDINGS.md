# Test findings: /generate-copy, /draft-report, /draft-insights

Paid test campaign for the new `generate-copy` processor. Each run's result was reviewed
read-only against `.claude/skills/generate-copy/SKILL.md`,
`processors/generate-copy/{prepare,generate,finalize}.py` and the run's inputs. Nothing
was re-run or fixed during review.

## Runs

| # | Video | Command | Status | Counts | Tokens (est / in / out) | Verdict |
| - | ----- | ------- | ------ | ------ | ----------------------- | ------- |
| 1 | `video_003.MOV` (48 s, Nepali + English speech, one talking-head shot) | `/generate-copy input/video_003.MOV translate to Nepali` | complete, `review_status` draft, `missing` [] , `checks` [] | 4 hooks, 4 segments, 3 captions (instagram-reels, tiktok, linkedin), hashtags 5 niche / 4 broad / 1 brand, translation Nepali (4 hooks, 3 captions) | 1,882 / 1,626 / 1,504 | Pass with findings (F-001 to F-009) |
| 2 | `video_014.MOV` (84 s, Nepali + English speech, 8 transcript parts of about 15 s, diarized, one shot) | `/generate-copy input/video_014.MOV platforms linkedin,tiktok tone "warm, encouraging" brief "Promote our student visa counselling"` | complete, `review_status` draft, `missing` [], `checks` [] | 4 hooks, 4 segments, 2 captions (linkedin, tiktok), hashtags 5 niche / 4 broad / 1 brand, `translation` null | 2,416 / 2,204 / 1,253 | Processor pass, but the copy is not usable as it is: the organisation name is probably wrong (F-011) |
| 3 | `video_014.MOV` (again, free) | `/generate-copy input/video_014.MOV platforms linkedin,tiktok tone "playful"` | `different_options`, stopped before paying | none written: saved `copy.json` unchanged (`created_at` 10:12:17, tone "warm, encouraging"), no job folder in `work/generate-copy/` | none | Pass; the message does not say which option changed (F-016) |
| 4 | `video_006.MOV` (free) | `/generate-copy input/video_006.MOV` | `missing_inputs` (`/tag-visuals`) | nothing written, no job folder | none | Pass: named only the missing skill and noted the transcript already exists |
| 5 | `video_003.MOV` (again, free) | `/generate-copy input/video_003.MOV translate to Nepali` | `already_done`, stopped before paying | nothing written | none | Pass |
| 6 | `video_003.MOV` (force, paid) | `/generate-copy input/video_003.MOV translate to Nepali force` | complete, draft, `missing` [], `checks` [] | 4 hooks (4 translated), 4 segments (hook, context, story, call-to-action), 3 captions each with a call to action, 3 translated captions, hashtags 5 / 3 / 1 | ? / 1,626 / 1,592 | Pass: old result in `history/20261105-095553/` (3 files), `metadata.replaces` = old `created_at`, no job folder left. F-010 seen again |
| 7 | `video_014.MOV` (force, paid, after fixes) | `/generate-copy input/video_014.MOV platforms linkedin,tiktok tone "warm, encouraging" brief "Promote our student visa counselling" force` | complete (wrongly, F-018) | 5 hooks, 1 segment (call-to-action, B-roll T1 only, no soundbite), 4 segments dropped, 2 captions, hashtags 4 / 3 / 2 (brand `tilichoconsultinggroup`, `tilicho`), 3 review notes | 2,961 / 2,737 / 1,706 | F-011 and F-012 fixed (Tilicho spelling, brief mismatch noted by the model); new F-017 to F-019; F-010 seen again |
| 8 | `video_003.MOV` (force, paid, after fixes) | `/generate-copy input/video_003.MOV translate to Nepali force` | complete | 5 hooks, 4 segments (hook, story, proof, call-to-action, each with a soundbite), 3 captions with Nepali, hashtags 4 / 3 / 2 (Tilicho), 0 dropped, 2 review notes, one-part warning shown | 2,269 / ? / ? | Pass: the one-part warning, per-item translation and review notes all work |
| 9 | `video_014.MOV` (force, paid, after F-017 fix) | same as run 7 | complete | 5 hooks, 5 segments each with soundbites and on-screen-text B-roll, split sentences joined by listing both parts (S8+S9, S18+S19), 0 dropped, 2 captions, hashtags 5 / 3 / 2 (Tilicho), 2 review notes (brief mismatch, spoken name differs) | ? / 2,792 / 1,326 | Pass: F-017 fixed. "Tilottama" appears only in a review note and in organisation.json's note, never in the copy; no speaker labels in soundbites; no cut opening or closing. F-010 seen again: the ready message was still a paraphrase without the summary lines (inputs, brief, cost) |
| 10 | `video_007.MOV` (new video, after `/process-video`; visual tags from before legibility checks) | `/generate-copy input/video_007.MOV` | complete | 5 hooks, 4 segments, 3 default captions, hashtags 4 / 2 / 2, 0 dropped, 2 review notes (a 28-day timeframe to verify; an outcome claim deliberately left out), both warnings (one-part transcript, no on-screen text) shown | ? / 2,071 / 1,538 | Pass. The ready message was paraphrased again (F-010, accepted) |

Run 1, checked and passing:

- Counts the test session reported match `copy.json`. `inputs` match the `created_at`
  and `complete` of `transcript.json` (2026-11-04T05:31:04), `tags.json`
  (2026-11-04T09:00:05) and `topics.json` (2026-11-05T08:42:33), so topic tags were read.
  `options`: the three default platforms, English, translate Nepali, `tone` and `brief`
  null.
- `metadata.json` has `status` complete, `replaces` null and no `context` or `refs`.
  `work/generate-copy/` is empty.
- Every evidence ref (S1 to S7, V:speaking-to-camera, V:office, V:desk, V:certificate,
  V:gesturing) exists. Soundbite `text` matches the transcript's sentences split at the
  danda. B-roll `ranges` match `tags.json` (gesturing `[[0,30.012],[35.013,45.017]]`, the
  rest `[[0,48.167]]`).
- Segment order: hook (S2), context (S3, S4), story (S5), call-to-action (S6, S7).
- No person's name appears anywhere. The transcript and on-screen text contain none
  (`on_screen_text` is empty), and the copy says "the client" and "they". The only
  name is the organisation, Cleary Consulting Group (S6). The brand hashtag
  `clearyconsultinggroup` is supported by S6.
- Every soundbite is mostly Nepali, so each of the 4 segments has an English subtitle.
  "today" in `segments[0].subtitle` is supported by "आज" in S2. No price, number, date,
  guarantee or invented quote appears.
- Captions contain no `#`, and none is over its platform's limit (191, 164 and 381
  characters). Hashtags have no `#`, spaces or hyphens.
- The translation is in Devanagari, with 4 hooks in the same order as the English ones
  and a caption for each of the 3 platforms. It reads as natural, code-mixed Nepali
  (क्लाइन्ट, ग्रान्ट, एक्सटेन्सन, as the speaker talks) and matches the English meaning. No
  claims were added.
- `copy.md` renders the header, hooks with style and sentence numbers, soundbites with
  times and sentence numbers, B-roll with ranges, captions with call to action,
  hashtags with `#`, and the Translation section.
- The token estimate was 16% over (1,882 vs 1,626 input tokens), which is a safe
  overestimate. Output used 1,504 of `MAX_OUTPUT_TOKENS` 12,000 (13%).

Run 2, checked and passing:

- Counts the session reported match `copy.json`. `inputs` match the `created_at`
  and `complete` of `transcript.json` (2026-11-04T09:24:32), `tags.json`
  (2026-11-05T05:09:37) and `topics.json` (2026-11-05T08:52:13).
- `options`: `platforms` [linkedin, tiktok], `language` English, `translate` null,
  `tone` "warm, encouraging", `brief` recorded word for word. `translation` is null,
  and `copy.md` has no Translation section.
- `metadata.json` has `status` complete, `replaces` null and no `context` or `refs`.
  `work/generate-copy/` is empty.
- Every ref exists (S1 to S21, V:speaking-to-camera, V:office, V:gesturing,
  V:text-on-screen). Soundbite times are the real part times. B-roll ranges match
  `tags.json`.
- Segment order: hook (S6), context (S1, S2, S7 to S9), story (S10 to S13, S15),
  call-to-action (S18 to S21).
- No person's name appears anywhere. The clear on-screen name (T5) and the phone number
  (T1) were both left out. Captions contain no `#`, and hashtags have no `#`, spaces or
  hyphens.
- No success rates, guarantees, prices or invented services. The copy did not take the
  "Study Abroad" or "Test Preparation" on-screen menu items as services. The editor
  notes even warn against implying a guaranteed outcome.
- The token estimate was 10% over (2,416 vs 2,204), in line with run 1. Output used
  1,253 of 12,000 tokens.

Run 2 note: the test session's closing paragraph came through garbled ("…not the exact
sentence", "any changesew file next to copy.md"). This is probably damage from pasting
into the terminal, so it is not logged as a finding.

## draft-report runs

Paid test of `/draft-report` (Pulse C17b) on the mock months in `input/reports/`.
Reviewed read-only against `processors/draft-report/{prepare,draft,finalize}.py`,
`lib/numbers.py`, the skill, the input JSON and the July example on screen 7 of the
Pulse design. Nothing was run again.

| # | File | Status | Sentences: items saved / real sentences (headline, happened, worked, didn't land, top post) | Checks | Tokens (est / in / out) | Verdict |
| - | ---- | ------ | ------------------------------------------------------------------------------------------- | ------ | ----------------------- | ------- |
| 1 | `2026-10.json` (8 posts, all Full; plan N1 to N3; 3 earlier months) | complete, 0 missing, 0 dropped | 1/1, 1/3, 1/3, 1/2, 1/2; 3 highlights, 4 tiles, next month 3 | 1 (a false positive, F-021) | 3,255 / 3,178 / 1,205 | Pass with findings. Every number is right and next month follows N1 to N3, but the strategist has to edit it (F-022, F-024, F-025, F-027). F-020 applies |
| 2 | `2026-09.json` (6 posts, P4 TikTok Partial; no plan; no earlier months) | complete, 0 missing, 0 dropped | 1/1, 2/3, 2/4, 1/2, 1/2; 3 highlights, 4 tiles, next month 0 | 2 (the "because" one is a false positive, F-021; the P4 one is met) | 2,844 / 2,744 / 1,087 | Pass on honesty: the falls are stated with their numbers, P4 is called incomplete, no superlatives, next month is empty. One highlight ranks against Partial P4 without a warning (F-023). F-020 applies |
| 3 | `2026-10.json` re-test after the fixes (`force`; run 1 in `history/20261105-113910/`) | complete, 0 missing, 0 dropped, 0 split | 1/1, 3/3, 2/2, 1/1, 2/2; 3 highlights, 4 tiles, next month 3 | 1, correct ("What didn't land has 1 sentence") | 3,496 / 3,399 / 1,273 | Pass with findings. Every number right and on the right post; one sentence per item; no internal terms; P1 and P6 treated as one video; retention line names its measure. The engagement line says P2 had the "highest result" for likes, comments, shares or saves, though P1 led every count (F-025, seen again). Earlier months still unused (F-027). F-010 seen again |
| 4 | `2026-09.json` re-test after the fixes (`force`; run 2 in `history/20261105-114012/`) | complete, 0 missing, 0 dropped, 3 split | 1/1, 3/3, 1/2, 1/2, 1/2; 3 highlights, 4 tiles, next month 0 | 15: 5 accurate (3 split notes, the Partial and ranking checks on what worked sentence 1), 10 false alarms (8 Partial, 1 ranking, 1 superlative) | 3,096 / 2,970 / 1,140 | Fail on accuracy. What worked sentence 1 gives P2 the highest reach among complete posts, but P1 had it (F-028). No check names that error, and 10 false alarms surround it (F-029, F-030). Highlights use the codes "P1", "P2" and "P4" (F-022, seen again). The model ignored one sentence per item in 3 of 5 sections (F-031). Falls are stated honestly in what happened, but the headline no longer says the month fell (F-032). F-010 seen again |
| 5 | `2026-10.json` re-test after the F-028 to F-032 fixes (`force`; run 3 in `history/20261105-115227/`) | complete, 0 missing, 0 dropped, 0 split | 1/1, 3/3, 3/3, 1/1, 2/2; 3 highlights, 4 tiles, next month 3 | 1, correct ("What didn't land has 1 sentence") | 3,845 / 3,785 / 1,146 | Pass with findings. Every number and every ranking is right (all agree with LEADERS); the engagement lines are now a share (10.23%), no internal terms or codes, N1 to N3 faithful. What didn't land is one sentence again (F-034). What worked s3 presents the two posts of one video "using the same question as their opening hook" as a pattern (F-024 regressed). Earlier months still unused, 15,400 now given three times (F-027) |
| 6 | `2026-09.json` re-test after the F-028 to F-032 fixes (`force`; run 4 in `history/20261105-115326/`) | complete, 0 missing, 0 dropped, 0 split | 1/1, 4/4, 2/2, 2/2, 2/2; 3 highlights, 4 tiles, next month 0 | 4, all real (Partial + ranking on what worked s1 and s2, which cite P4 and rank without leaving it out) | 3,456 / 3,371 / 1,332 | Pass with findings. Every number and ranking is right (F-028 not repeated); the headline says reach fell (F-032); no codes in the text (F-022); no false alarms (F-029). What worked s1 and s2 do not say P4 is left out (F-023 residual; s2 is harmless in fact, as P4's reach is recorded and lower). The order check would still miss the run-4 error on its real refs (F-033) |

What was checked and passes in both runs:

- **Numbers:** every number was checked by hand against the input: totals, differences
  (13,300; 3,300; 22; three), post counts, retention 49% and 41% for October's P6, and
  the counts (two, one) for P8. All are right, and each is on the right post, metric and
  direction. The refs are correct, with one exception: October's what_worked cites P6
  only as the second "financial documents video" (F-024).
- **Falls (September):** stated plainly. Reach "down from 38,200 in August", followers
  "22 fewer", enquiries "down by three", and the headline "down 3,300". Nothing is
  softened or put in a better light.
- **Changes marked "not shown":** never stated. Video plays in both months and the
  engagement rate in September are not compared. August's 45,000 plays and 7.9% never
  appear.
- **Partial P4 (September):** "The TikTok post's numbers are incomplete, so we have not
  compared it with the other posts". Rankings in the paragraphs say "among the posts
  with complete data". The one exception is F-023.
- **Superlatives:** September uses no "best", "ever", "yet" or "so far", only rankings
  within the month (most, lowest, longest). October does not use its earlier months at
  all.
- **Names:** none in either month. People appear only as "students", "viewers" or
  "a client's" (F-022).
- **Next month:** October's three items are N1 to N3 reworded as "We'll …", with no
  added promise and the same meaning. `plan_text` is kept next to each item.
  September's list is empty, and `report.md` shows the strategist placeholder.
- **Tiles:** all four have a line. Video plays read "played 54,400 times" and "played
  28,600 times; this number is incomplete", never as people.
- **Highlights:** each cites the post the report engine chose (P1, P2 and P6 in October;
  P1, P2 and P2 in September).
- **Lengths:** both headlines have 10 words. Counted as real sentences, the paragraphs
  have 3/3/2 (October) and 3/4/2 (September), within 2 to 4 and as dense as screen 7
  (3/4/2). The top post has 2 sentences.
- **`review_notes`:** stored in full in the file. October's second note ends "…not a
  count of people.", so the cut seen in the terminal happened only on screen.
- **`metadata.json`:** `status` complete, the posts' `inputs` (topics and copy times)
  and organisation, `replaces` null, and no `context`, `refs`, `allowed_numbers` or
  `work/` path. `work/draft-report/` is empty. The token estimate was 2% and 4% over.
- **Pasted summary:** the session reported "1 sentence" for September's what_happened,
  but 2 items are saved, so the paste is wrong there. The session's "1 each" is the
  item count (F-020).

### Re-test (runs 3 and 4)

Both months were run again with `force` after the fixes listed under Fix status. Their
`report.json` files were checked by hand against the input JSON, `finalize.py` and
`draft.py`. The session's paste counted 10 "rests on P4" checks for September, but
`report.json` holds 9, so the total is 15.

- **Numbers (both months):** all are right and each is on the right post or metric.
  October: 48,200, 27, 34,900, 54,400, 214/128, 27/18, 15,400 (P1), 41% (P6 to the end),
  and the plan's "two", "30-second" and "one … a week". September: 34.9K, 18, 34,900,
  3,300, 28,600, 128/22, 18/three and 9,900 (P1). No number check fired, and none should
  have. The one wrong claim has no number in it (F-028).
- **September checks, one by one:**

  | Check | Line | Verdict |
  | ----- | ---- | ------- |
  | superlative "strongest" | what worked s1: "…was among the strongest posts…" | false: a ranking of posts within the month, not of the month (F-030) |
  | P4 Partial | what worked s1 | real: "more than any other post" ranks likes, comments, shares or saves against P4, whose shares and saves are not recorded, without leaving it out |
  | P4 Partial | what worked s2: "…the post rankings leave out the TikTok post because its data is incomplete." | false: it says so |
  | P4 Partial | didn't land s1: "Among posts with complete data, the LinkedIn case study reached the fewest people." | false: it is qualified, and cites P4 only because s2 leaves it out |
  | P4 Partial | didn't land s2: "The TikTok post's data is incomplete, so it is left out of this comparison." | false |
  | P4 Partial | top post s1: "The Instagram video explained a student visa grant…" (P1, P4) | false: P4 was inherited from s2 |
  | P4 Partial | top post s2: "It reached 9,900 people; the highest-reach ranking leaves out the TikTok post because its data is incomplete." | false |
  | P4 Partial | the three highlights, each ending "P4 is left out because its data is incomplete." | false (3) |
  | ranking "more than any" | what worked s1 | real (as above) |
  | ranking "fewest" | didn't land s1 | false: "Among posts with complete data" is not in `DATA_GAP`, and the "left out" clause went to s2 when the item was split |
  | split | what worked, didn't land, top post: item 1 held 2 sentences | accurate |

  All 9 Partial flags come from the model citing P4 in order to leave it out. Six are on
  split sentences that inherited P4 from their item; the three highlights cite it
  directly. `partial_checks` has no `DATA_GAP` exemption, so each one fires.
- **Honesty in September:** the falls are stated with their numbers in what happened
  ("down 3,300 from August", "down 22 from August", "down three"). Video plays are called
  incomplete and not compared, and engagement rate is not mentioned. The headline gives
  only the counts (F-032).
- **Kept from runs 1 and 2:** no names; video plays are never called people; changes
  marked "not shown" are not stated; September's next month is empty; October's N1 to
  N3 keep their meaning ("including one in Nepali" for "one of them in Nepali");
  `work/draft-report/` is empty; `replaces` matches each `history/` folder.
- **October, minor:** what didn't land is one sentence without its number ("…had the
  quietest reach among this month's posts."). It is correct and plain, but run 1 also
  gave 1,900 and the counts, so this paragraph is thinner than before, and the check
  fires rightly. In what worked s2, "Both were practical advice videos" means P1 and
  P2, but the sentence cites P1 and P6. "Shared on Instagram and YouTube" (meaning
  posted on both) can be read as the shares count. The top post's "was liked,
  commented on, shared or saved" says nothing, and 15,400 appears in both the top post
  and the reach highlight.

### Re-test (runs 5 and 6)

Both months were run again with `force` after the F-028 to F-032 fixes. Their
`report.json` files were checked by hand against the input JSON. LEADERS was worked out
again from the inputs, and `order_checks`, `reference_checks` and `wording_checks` were
replayed on the saved texts in a scratch script (free; nothing written to `output/`).
The session's "happened ?" for September is 4.

- **Rankings (F-028):** all 15 ranking lines agree with the leaders among Full posts.
  September: P1 most reach (9,900), P2 highest engagement rate (7.55%) and most watched
  to the end (36%), P5 fewest reach (1,900). October: P1 most reach and every count
  (15,400; 820/96/214/310), P2 highest engagement rate (10.23%), P6 most watched to the
  end (41%), P8 fewest reach and every count (1,900; 41/2/1/1). No false ranking was
  missed in these runs. The replay of the run-4 sentence is a different story (F-033).
- **September checks, one by one:**

  | Check | Line | Verdict |
  | ----- | ---- | ------- |
  | P4 Partial + ranking "highest" | what worked s1: "Your English-language Instagram videos stood out: the educational video about visitor-visa refusals had the highest share of people reached who liked, commented on, shared or saved, and the most viewers watched it to the end." (P2, P1, P4) | real: ranks on engagement rate and retention, which P4 lacks, cites P4, and says nothing about leaving it out |
  | P4 Partial + ranking "highest" | what worked s2: "The highest-reach post was also an English-language Instagram video, about a student visa grant for master's study." (P1, P4) | real by the rule, harmless in fact: P4's reach (5,100) is recorded and lower, and the top post and highlight qualify the same claim |

  Neither sentence has any wording of exclusion, so no `DATA_GAP` word is missing here.
  The five lines that cite P4 in order to leave it out (didn't land s1, top post s1, the
  three highlights) raise nothing, so F-029 holds. Each gap gives two checks (Partial and
  ranking), so 4 checks cover 2 sentences. `DATA_GAP` would still miss "excluding",
  "except", "apart from", "not counting" or "without the TikTok post" (latent).
- **Numbers (F-026):** all right and each in what its sentence cites. October: 48,200,
  34,900, 54,400, 27, nine, 15,400 (P1), 10.23% (P2), 1,900 (P8), 41% (P6), 214, and the
  plan's two, 30-second, one … a week. September: 34,900, 38,200, 28,600, 128, 22, 18,
  three, 310/25/30/22 (P1). No wrong number appeared to exercise the check.
- **Client text:** no names, no codes (`reference_checks` empty), no engine, snapshot or
  "client" for the people in posts. September uses "posts with complete data" and "its
  numbers are incomplete", which the rule needs.
- **Highlights (F-025):** each names its measure; both engagement lines are a share
  ("highest share of people reached who liked, commented on, shared or saved", October
  with 10.23%). September's retention line says "The most viewers watched … to the end",
  count wording for a share (true either way here).
- **Same video (F-024):** October what worked s3: "The two posts about student visa
  applications used the same question as their opening hook, and the video on YouTube
  had the highest share of viewers watch to the end." (P1, P6). They are one video
  (`video_007.MOV`, hook 1). The model's own review note asks to check this. Regressed
  from run 3.
- **Headlines:** September "September reached 34,900 people, fewer than in August, and
  brought 18 enquiries." says reach fell (F-032); the fall in enquiries is only in what
  happened. October "You reached 48,200 people, up from September, and received 27
  enquiries." does not use the earlier months, although 48,200 and 27 are the highest of
  the four (F-027, third time).
- **Honesty and held-back data:** September states every fall with its number (38,200,
  22, three) and that reach fell on all four platforms. Video plays are called incomplete
  in both what happened and the tile; the held-back plays change (45,000) and the
  engagement rate are not stated. October says plays "can't" be compared with September.
  No superlatives in either month.
- **Next month:** October's three items are N1 to N3 with the same meaning ("including
  one in Nepali"); September's list is empty.
- **One sentence per item (F-031):** items equal real sentences in every section of both
  months; `split` is empty, and each sentence cites only its own data (September's top
  post s2 cites only P1).
- **October what didn't land:** one item in all three October runs; one real sentence in
  runs 3 and 5 (F-034). "Your intake-dates carousel reached the fewest people, with
  1,900, and had the fewest likes, comments, shares and saves." is correct, but LEADERS
  offers a second quiet spot that goes unused (P3 last on all three retention measures).
- **Other:** both `metadata.json` are `complete` with `replaces` matching the archived
  run; `work/draft-report/` is empty; the token estimate was 2% and 2.5% over.

## draft-insights runs

Paid test of `/draft-insights` (Pulse C18b) on the mock months: the triggers in
`input/insights/2026-10.json` and the posts in `input/reports/2026-09.json` and
`2026-10.json`. Reviewed read-only against `processors/draft-insights/{prepare,draft,finalize}.py`,
`lib/numbers.py`, `lib/wording.py`, the skill, the design, the inputs and the Results card
in `Assets and Results.dc.html:243-246`. The plan the model got was regenerated for free
with `prepare.py --force`. It is identical, with the same `estimated_input_tokens` of
4,956 and `replaces` equal to the result's `created_at`, and its job folder was then
deleted. finalize's checks were replayed on the saved texts in a scratch script. Nothing
paid was run again.

| # | File | Status | Insights (trigger: hypotheses, request) | Checks | Tokens (est / in / out) | Verdict |
| - | ---- | ------ | --------------------------------------- | ------ | ----------------------- | ------- |
| 1 | `2026-10.json` (T1 engagement 2.2× on ci-2610-02, T2 52% gone in 3 s on ci-2610-03, T3 8 of 16 behind; BL 21 posts, 13 with complete data in the window; G1 to G24) | complete, 0 missing, 0 dropped, 0 held back, 0 not enough evidence; 3 review notes | T1: 2 (G2; G1, P7), 1 video; T2: 2 (G17, P8; G13, P8), 1 video; T3: 2 (G2; G4), 1 photo | 0. Correct for what the checks cover (the replay gives 0 too), but there are false negatives the checks cannot see (F-036, F-041) | 4,956 / 5,331 / 1,370 | Pass on numbers, refs, wording and names. Not usable as is. T1's second hypothesis and its brief rest on a visual-tag comparison that is wrong for video_003 (F-036). All three requests ask for 1 item, and T1 and T2 ask for the same video (F-037, F-038). The T1 client card states in count words a lead the counts contradict (F-041). T3's hypotheses do not address the trigger (F-042) |
| 2 | `2026-10.json force` (same triggers and BL as run 1; G1 to G18, none on visual tags; replaces run 1, now in `history/20261106-083956/`) | complete, 0 missing, 0 dropped, 0 held back, 0 not enough evidence; 3 review notes | T1: 1 (G2, P7), 2 videos, tests 1; T2: 1 (G15, P8), 2 promo videos (en), tests 1; T3: none (why_unknown kept), 3 videos | 1: T1's card says "engagement rate", which is correct (F-048). Missed: T1 and T3 ask for the same videos (F-046) | 5,422 / 5,734 / 1,541 | Pass on numbers, refs, ratios, causes, names and structure. F-039, F-041, F-042, F-043 and F-044 hold. Usable after edits: both tests set a bar below the 90-day average (F-045), T1 and T3 both ask for educational visa-guidance videos (F-046), T2's hypothesis rests mostly on the flagged video and does not say so (F-051), and the card names the engagement rate (F-048) |
| 3 | `2026-09.json`, first run (T1 48% gone in 3 s on ci-2609-01, T2 56% on ci-2609-06, T3 6 of 16, 10 behind; Partial ci-2609-04 held back; BL 17 posts, 5 with complete data in the window; G1 to G7, none on still watching) | complete, 0 missing, 0 dropped, 1 held back, 2 not enough evidence (T1, T2); 2 review notes | T1, T2: not enough evidence; T3: none (why_unknown kept), 2 photos | 1: T3's card says "engagement rate", which is correct (F-048). Missed: the photo category goes against G4 and G6 (F-047), and "pillars" on the card | 3,228 / 3,184 / 846 | Pass on numbers, refs, held back, and "not enough evidence" (correct and specific). T3 is not usable as is: photos contradict the format comparisons it was given (F-047), 2 for a 10-post gap (F-049), and the card gives a pillar comparison with "engagement rate" instead of its own trigger (F-048) |
| 4 | `2026-10.json force`, after the F-045 to F-051 fixes (same triggers and BL; G1 to G17: T1's G1 to G4 worked out without P2 and P7, T2's G5 to G9 without P1 and P8, T3's G10 to G17; none on visual tags; replaces run 2, now in `history/20261106-085727/`) | complete, 0 missing, 0 dropped, 0 held back, 0 not enough evidence; 3 review notes | T1: 1 (G3), 2 videos, tests 1; T2: 1 (G7), 2 promo videos (en), tests 1; T3: none (why_unknown kept), 3 videos | 2: T1/T3 look-alike, real (0.35; F-046 still occurs). T2/T3 look-alike, false alarm (0.27 on "please, send, video(s), visa, explaining, different": F-055) | 5,288 / 5,555 / 1,751 | Pass on numbers, refs, ratios, causes, names, test bars, categories, quantities and the code-written card findings. Usable after edits: T1 and T3 still both ask for educational visa-advice videos (F-046), and T2's request changes the opening while its hypothesis and comparison are about the promo pillar (F-053) |
| 5 | `2026-09.json force`, after the fixes (same triggers and BL; G1 to G7, all bearing on T3 only: none bears on T1 or T2; replaces run 3, now in `history/20261106-085818/`) | complete, 0 missing, 0 dropped, 1 held back, 1 not enough evidence (T2); 3 review notes | T1: 1 (P1 only, the flagged post), 2 promo videos with a new opening (en), tests 1; T3: none (reason left empty), 3 educational videos (en) | 1: "16" in T3's card action, a false alarm caused by the card-action rule (F-054) | 3,359 / 3,313 / 1,270 | Pass on numbers, refs, causes, names, held back, test bar, category and quantity. Not usable as is: T1's hypothesis rests only on the flagged post itself, where run 3's "not enough evidence" was right (F-052), and both card actions repeat the finding, T3's word for word (F-054) |
| 6 | `2026-10.json force`, after the F-052 to F-055 fixes (same triggers and BL; G1 to G17 as in run 4: G1 to G4 bear on T1, G5 to G9 on T2, G10 to G17 on T3; replaces run 4, now in `history/20261106-091326/`) | complete, 0 missing, 0 dropped, 0 held back, 0 not enough evidence; 4 review notes | T1: 1 (G4), 2 "Nepali TikTok" educational videos (language any), tests 1; T2: 1 (G7), 2 English educational Instagram videos keeping P8's opening style, tests 1; T3: none (why_unknown empty, reason in note 1), 3 educational videos opening with a question | 3: T1/T2, T1/T3 and T2/T3 "both ask for educational videos". All three are true by the check's rule, but the overlap comes from the evidence, and the advice is wrong for T1/T2 (F-057). Repeat check: nothing, correctly | 5,357 / 5,615 / 1,535 | Pass on numbers, refs, ratios, causes, names, categories, quantities, bars, the code-written card findings and the card actions (no repeats). Every hypothesis cites a comparison for its trigger, and T2's request changes only the pillar. Usable after normal strategist edits: decide whether the client gets three asks for educational videos (F-057), raise T1's bar (F-058), set T1's language (F-059), and reword both hypotheses as reasons (F-053). Nothing blocks |
| 7 | `2026-09.json force`, after the fixes (same triggers and BL; G1 to G7, all bearing on T3; prepare now tells the model that no comparison bears on T1 or T2; replaces run 5, now in `history/20261106-091405/`) | complete, 0 missing, 0 dropped, 1 held back, 2 not enough evidence (T1, T2, both by the model); 0 review notes | T1, T2: not enough evidence; T3: none (why_unknown kept), 3 English educational Instagram videos (G1 to G4) | 0. Correct: no repeat, no look-alike (one request), and nothing else was due | 3,483 / 3,417 / 663 | Pass on everything checked. Usable as it is: "not enough evidence" for both drop-off triggers is right (as in run 3), and T3's request follows `format_lean` and the comparisons it cites. Nothing blocks |
| 8 | `2026-10.json force`, after the F-053 and F-057 to F-059 fixes and the video_003 re-tag (same triggers and BL; G1 to G17 as in run 6; P1 and P8 now carry video_003's new topic tags; replaces run 6, now in `history/20261106-093032/`) | complete, 0 missing, 0 dropped, 0 held back, 0 not enough evidence; 3 review notes; total ask "Requests for November 2026: 7 videos (T1 2, T2 2, T3 3)." | T1: 1 (G3, pillar), 2 educational Nepali TikTok videos (ne), tests 1, bar 5.94%; T2: 1 (G7, pillar), 2 English educational Instagram videos (en), tests 1, test at 67.53%; T3: none (why_unknown kept), 3 educational videos (any) | 0. Right for everything the checks cover (the replay gives 0 too). One false negative no check can see: T1's brief calls the flagged video "question-led", but P7 used a curiosity hook (F-060) | 5,452 / 5,711 / 1,564 | Pass on numbers, refs, ratios, causes, names, categories, quantities, languages, bars, the code-written card findings and card actions. F-057, F-058 and F-059 confirmed fixed, and both hypotheses are now reasons (F-053). Usable after one small strategist edit: take "question-led approach" out of T1's brief (F-060). Optional: different titles for T1 and T2 (both "2 more educational videos"), and decide on the 7-video total ask. Nothing blocks |
| 9 | `2026-09.json force`, after the same fixes (same triggers and BL; G1 to G7, all bearing on T3; P1 now carries video_003's new topic tags; replaces run 7, now in `history/20261106-093102/`) | complete, 0 missing, 0 dropped, 1 held back, 2 not enough evidence (T1, T2, both by the model); 2 review notes; total ask "Requests for October 2026: 3 videos (T3 3)." | T1, T2: not enough evidence; T3: none (why_unknown kept), 3 educational videos (any; G3, G5, G4, G6, with P2 as the model) | 0. Correct: one request, no hypotheses, nothing else was due | 3,579 / 3,510 / 729 | Pass on everything checked. Usable as it is, as run 7 was. Nothing blocks |

What was checked and passes:

- **Numbers:** every number in all 36 texts was checked by hand against the regenerated
  refs, and each one is in what its sentence cites:
  - observations: 10.23%, 2.2×, 4.7% (T1, BL); 52%, 48%, 58% (T2, BL); 8 of 16 (T3)
  - hypotheses: 6 and 7 posts, 6.92% and 3.43% (G2); 4 posts across 2 videos and 2
    posts from 1 video (G1); 3 posts from 2 videos (G17); 4 posts (G13); 6 and 7 posts
    (G2, G4)
  - request titles: 1, the quantity
  - cards: 48% and 3 seconds (T2); 8 and 16 (T3)

  The only ratio is "2.2×", in T1's observation, which cites T1. There is no "twice",
  "half" or "double". The replay of `number_checks`, `cited_number_checks` and
  `ratio_checks` is empty.
- **Hypotheses:** all 6 say "may". Each has a confirm_if and a refute_if, cites a G that
  bears on its trigger, and points the right way on the right measure:
  - T1: engagement (G2, G1)
  - T2: still watching after 3 s (G17, G13)
  - T3: engagement and reach (G2, G4)

  Each states its post counts. The two that rest on 2 or 3 posts on a side (T1 H2,
  T2 H1) call the pattern early, and so do T1 H1 and T2 H2. T1 H2 and T2 H1 give their
  counts in videos ("4 posts across 2 videos", "3 posts from 2 videos"). The other four
  do not (F-040).
- **Causes:** outside the hypotheses, nothing states a cause, including the wording the
  regex misses: no "since", "as a result", "helped", "boosted" or "thanks to". "So we
  can plan" and "to help us plan" in T3 give a purpose. "May have helped" appears only
  inside T1 H2. The replay of `wording_checks` is empty.
- **Observations:** each states its trigger correctly. T2 calls P8 "the video posted
  again on Instagram", and P8 is video_003, first posted as P1.
- **Client cards:** none uses engagement rate, retention, trigger, baseline, quota,
  impressions or a reference code. No person is named, including the strategist. No
  card promises a visa outcome. Each button has 4 words ("Send us a video" twice, "Send
  us a post"). They are weaker than the Pulse card (F-041, F-043).
- **Reference codes:** none appear in any text, and the replay of `reference_checks` is
  empty. `insights.md` shows the refs only in italics after each hypothesis, and in the
  References list.
- **Request fields:** category `video`, `video` and `photo`; quantity 1 each, which is
  in the allowed 1 to 3; language `any`; due 2026-11. Each brief is one sentence, and
  the evidence lists hold 5, 2 and 2 refs.
- **`review_notes`:** all 3 are stored in full in `insights.json` and `insights.md`
  ("…do not imply or promise visa outcomes."). The cut was on screen only. Note 2 flags
  the repeated videos generically, and note 1 says the evidence does not explain the
  shortfall (F-042).
- **`metadata.json`:** `status` complete and `replaces` null. It records the model
  (gpt-6-luna, low), the inputs (both window reports with hashes, the 6 posts' topics,
  copy and visual times, and the organisation), the baseline, the quota, the triggers
  and the warning. It holds no `context`, `refs`, `allowed_numbers` or
  `general_numbers`. `usage` is in `insights.json`. `work/draft-insights/` is empty, as
  is `history/` (this is the first result).
- **Pasted summary:** it matches the files: status complete; each trigger's label as
  prepare words it; 2 hypotheses each; 1 video, 1 video, 1 photo; nothing in not enough
  evidence, held back, dropped, missing or checks; and 3 review notes. The session
  paraphrased prepare's ready summary instead of pasting `summary_text`. This is the
  F-010 pattern the user accepted, so it is a note, not a finding. Only the session's
  short version was available to check. The line that mattered was the warning "The
  baseline counts 21 posts in the window; input/reports/ holds 14 of them", and nothing
  given contradicts it.

### Re-test (runs 2 and 3)

Reviewed read-only in the same way as run 1. Both plans were regenerated for free with
`prepare.py --force`. The estimates, 5,422 (October) and 3,228 (September), equal the
runs' `estimated_input_tokens`. `replaces` equals each result's `created_at`. Both job
folders were deleted, and `work/draft-insights/` is empty. Nothing paid was run.

What now passes:

- **Numbers:** every number in all texts was checked by hand against the regenerated
  refs, and each one is in what its sentence cites. The quantity appears only in request
  and card texts.
  - October:
    - 10.23%, 2.2× and 4.7% (T1, BL)
    - 48%, 52% and 58% (T2, BL)
    - 8 and 16 (T3)
    - 6.92%, 3.43% and 4 pieces of content (G2)
    - 68.7%, 54.67% and 2 pieces of content (G15)
    - the tests' 3.43% and 54.67% (each cites its own G)
    - quantities 2, 2 and 3
  - September: 6, 16 and 10 (T3); 1.5× (G5) and 1.9× (G3); quantity 2.

  The only ratios are 2.2×, 1.5× and 1.9×, each in a sentence that cites the T or G that
  gives it. There is no "twice", "half" or "double".
- **Comparisons (F-036, F-040):** neither plan has a visual-tag comparison: October has
  G1 to G18 and September has G1 to G7. Every side says "N posts of M pieces of content"
  when the two differ. Every label for a comparison that bears on a post trigger says
  which side holds that trigger's own post and its twin. Video vs picture comparisons
  exist in both months (October G1 and G7, September G4 and G6).
- **Hypotheses:** October has 2, one per post trigger. Each says "may", gives its pieces
  of content and calls the pattern early. T1's says the comparison "includes the flagged
  post itself" (T2's does not: F-051). Each test names its measure, a number to beat and
  "2 new" posts (F-039; the bar is weak: F-045).
- **Quota trigger (F-042):** neither month has a hypothesis for it. `why_unknown` says
  what the material lacks (what was sent, approvals, the schedule), and `insights.md`
  shows "Why posting fell behind: the numbers cannot say". Nothing was dropped, so the
  model wrote no hypotheses for it.
- **Not enough evidence (September):** the answer is correct. None of G1 to G7 measures
  still watching. The 3 videos (P1 video_003, P2 video_014, P5 YouTube with no video in
  `input/`) cannot form 2 pieces of content on each side, so nothing bears on T1 or T2.
  Both reasons are specific: T1 has "no comparison that connects either [opening or
  pictures] to people still watching". T2 has "no topic, opening, picture details", and
  P5 has no video in `input/`.
- **Requests (F-037, F-038):**
  - `tests` is 1, 1 and 0. Quantities are 2, 2 and 3 in October and 2 in September.
  - T2 is what F-038 asked for: "two English promo videos in the same success-story
    style, each opening with a question instead of a statement".
  - T1 and T2 now differ, but T1 and T3 do not (F-046). September's category is not
    backed (F-047).
- **Cards (F-041, F-043):**
  - Every finding carries a number or ratio ("2.2× your usual 4.7%", "48% … compared
    with your usual 58%", "8 of the 16").
  - Every button gives a quantity: "Send 2 more videos", "Send 2 promo videos", "Send 3
    videos", "Send us 2 posts".
  - Posting is "we" ("We posted 8 of the 16 posts planned for October").
  - There are no slots and no count words for engagement.
  - Both months name "engagement rate" (F-048).
- **Causes, names and refs:** there is no causal wording outside the hypotheses. "So 52%
  stopped watching" is arithmetic, and "so we can catch up" gives a purpose. No person
  is named, no reference code is in any text, and nothing promises a visa outcome.
- **Held back:** September's Partial ci-2609-04 is in `held_back`, out of every
  comparison and never mentioned.
- **`metadata.json`:**
  - Both have `status` complete.
  - October's `replaces` is 2026-11-06T08:39:56, which is run 1's `created_at`. Run 1's
    three files are in `history/20261106-083956/`, with their own `replaces` null.
  - September's `replaces` is null, and it has no `history/`.
  - `window_reports` is right: both reports for October, and for September only
    2026-09.json, the only report in its window.
  - Neither holds `context`, `refs`, `allowed_numbers` or `general_numbers`.
- **`insights.md` (F-044):** October's header lists reports/2026-09.json and
  reports/2026-10.json.
- **Tokens:** October's estimate ran 5.4% under (run 1: 7.6%). September's ran 1.4% over.
- **Pasted summaries:** both match the files. October's output tokens (1,541) were not
  shown, and its truncated T3 request is 3 videos.
- **False negatives (finalize):**
  - T1's and T3's requests ask for the same thing (F-046).
  - The photo category goes against the format comparisons (F-047).
  - The test bars are below the 90-day average (F-045).
  - T2's hypothesis does not say its comparison holds the flagged video (F-051).
  - "pillars" is on September's card (F-048).

### Re-test (runs 4 and 5)

Reviewed read-only in the same way. The pasted terminal output was garbled, so only the
files were trusted. Both plans were regenerated for free with `prepare.py --force`. The
estimates, 5,288 (October) and 3,359 (September), equal the runs'
`estimated_input_tokens`. `replaces` equals each result's `created_at`. Both job folders
were deleted, and `work/draft-insights/` is empty. A replay of finalize's checks on the
saved results, with the regenerated plans, gives exactly the saved checks (2 and 1).
Nothing paid was run.

What now passes:

- **Numbers:** every number in all texts was checked by hand against the regenerated
  refs, and each one is in what its sentence cites.
  - October:
    - 10.23%, 2.2× and 4.7% (T1's observation, T1)
    - 3 pieces of content and 5.94% (G3), and the bar 4.7% (T1, BL) in T1's test
    - 52% and 3 seconds (T2)
    - 2 pieces of content (G7), and the bar 58% (T2, BL) in T2's test
    - 8 and 16 (T3, the code's sentence)
    - quantities 2, 2 and 3 in the titles, briefs, card actions and buttons
  - September:
    - 48%, 52% and 57% (T1's observation and card action, which cite T1 and P1)
    - 57% in T1's test
    - 6 and 16 (T3; in the card action "16" is flagged, a false alarm: F-054)
    - quantities 2 and 3

  The only ratio is 2.2×, in October's T1 observation (which cites T1) and in the code's
  card finding. There is no "twice", "half" or "double".
- **Causes, names and refs:** "as" and "since" appear only inside hypotheses. October's
  `why_unknown` has "because it does not include what you sent", which explains missing
  data. No person is named, no reference code is in any text, and nothing promises a visa
  outcome. "catch up" appears nowhere.
- **Fixes F-045 to F-051 on the actual output:**
  - **Bars (F-045):** every test is at or above its trigger's bar: October T1 "each above
    5.94%" (bar 4.7%), T2 "more than 58%" (bar 58%), September T1 "above 57%" (bar 57%).
    Each refute_if sits at the average (4.7%, 58%, 57%). The bar check fired on nothing,
    and nothing was due.
  - **Card finding (F-048):** all 5 card findings are prepare's `card` sentence, word for
    word. No card says "engagement rate" or "pillars". October's T2 observation copies
    the same sentence, which is fine for the strategist.
  - **Own post left out (F-051):** October T1's G1 to G4 are "worked out without the
    flagged post (P2, P7)", and T2's G5 to G9 "without the flagged post (P1, P8)". The
    posts lists confirm it: G3 holds P3, P6, P9 and P11. No hypothesis cites a comparison
    that holds its own post. But September's T1 hypothesis now cites the post itself
    (F-052).
  - **Quota request (F-049):** 3 in both months (gaps 8 and 10), taken from the trigger.
  - **Category (F-047):** `format_lean` is video in both months, and all 5 requests are
    video. September's T3 moved from photos to videos.
  - **Visual tags (F-050):** video_003 (P1, P8) is now "sitting, speaking-to-camera,
    office, white-suit, blinds, certificate, chair, desk, glasses, keyboard,
    microphone, person": 12 of its 13 tags tied at 48.2 s, activities first. Only
    "plant" is cut. Neither plan has a visual-tag comparison.
  - **"catch up":** in no text in either month. The cards say "this month" (October)
    and "for October" (September's T3).
- **Hypotheses:** 3 in all, 1 per insight. Each says "may", gives its pieces of content
  (3, 2, "one piece of video content") and calls the pattern early or not established.
  Each test names its measure, the bar and "2 new" posts.
- **Requests:** each tests one hypothesis (`tests` 1, 1, 0 / 1, 0) and keeps the
  flagged kind. October T2 and September T1 ask for English promo success-story videos,
  and October T1 asks for educational videos with `language` any. September's two
  requests differ (promo vs educational). October's T1 and T3 do not (F-046 still
  occurs), and the T2/T3 check is a false alarm (F-055).
- **Not enough evidence (September T2):** correct and specific: "no opening, topic, or
  comparison". No video of P5 is in `input/`.
- **Held back:** September's Partial ci-2609-04 is in `held_back`, out of every
  comparison and never mentioned.
- **`metadata.json`:** both have `status` complete, `replaces` set to the run before
  (2026-11-06T08:57:27 for October, 08:58:18 for September), and the history folders
  hold runs 1, 2 and 3 unchanged. `window_reports` is right (both reports for October,
  only 2026-09.json for September). `triggers` now records `card`, `bar` and
  `quantity`, and `format_lean` is kept. Neither holds `context`, `refs`,
  `allowed_numbers` or `general_numbers`. Both `insights.md` headers list every window
  report.
- **Tokens:** October's estimate ran 5.0% under (5,288 against 5,555; run 2: 5.4%).
  September's ran 1.4% over (3,359 against 3,313; run 3: 1.4%). Output tokens rose to
  1,751 and 1,270 (runs 2 and 3: 1,541 and 846).
- **Session summaries:** both match the files: the hypotheses, quantities, `tests`,
  held back, not enough evidence, tokens, checks and review notes.

September T1's new hypothesis (F-052): it cites only P1, which is T1's own post. Its
material is the opening hook "(statement)". In September none of G1 to G7 bears on T1
or T2. All seven are marked "bears on T3", and with P1 left out a drop-off comparison
cannot have 2 pieces of content on each side (the other videos are P2 and P5). So no
comparison bears on a drop-off trigger at all. The plan T1 got is, apart from the
excluded own post, the one run 3 answered "not enough evidence" to. Only the model's
answer changed. The model's own note 2 says it "is based on one piece of content and
does not establish a pattern", and in the same answer it gave T2 "not enough evidence"
for the same lack. Run 3's answer was the right one. Finalize should enforce it, because
the prompt alone gave both answers on the same plan.

October's look-alike checks: T1/T3 is a real duplicate. Both ask for educational videos
on practical visa-application questions, and T3's own review note says to check it. T2/T3
is a false alarm: a promo success-story video with a new opening against educational
how-to videos. Its 0.27 comes from request boilerplate. The scores are title and brief
words of 4 or more letters minus `FILLER`, Jaccard, as in `same_request_checks`:

| Run | Pair | Categories | Shared / all | Score | Same request? | Flagged at 0.25 |
| --- | ---- | ---------- | ------------ | ----- | ------------- | --------------- |
| 1 | T1/T2 | video, video | 9/18 | 0.50 | yes | yes (replay) |
| 1 | T1/T3 | video, photo | 3/28 | 0.11 | no | no (categories differ) |
| 1 | T2/T3 | video, photo | 5/23 | 0.22 | no | no (categories differ) |
| 2 | T1/T2 | video, video | 4/22 | 0.18 | no | no |
| 2 | T1/T3 | video, video | 7/25 | 0.28 | yes | yes (replay) |
| 2 | T2/T3 | video, video | 2/28 | 0.07 | no | no |
| 4 | T1/T2 | video, video | 6/26 | 0.23 | no | no |
| 4 | T1/T3 | video, video | 8/23 | 0.35 | yes | yes |
| 4 | T2/T3 | video, video | 7/26 | 0.27 | no | yes (false alarm) |
| 5 | T1/T3 | video, video | 5/29 | 0.17 | no | no |

Run 3 has one request. Duplicates score 0.28 to 0.50, and different requests up to 0.27,
so 0.25 no longer separates them. Run 4's T1/T2 (0.23) is close too. The shared words of
the different pairs are boilerplate: please, send, video(s), visa, explaining, different,
like. See F-055.

September's "16" check is a false alarm caused by the card rule. T3's card action is "We
posted 6 of the 16 posts planned for September; send us three educational videos for
October, and we'll post them." Card action and button texts are checked against the
action's evidence (G2 to G6) plus the quantity. The finding's 16 (T3) is not there.
"6" passes only because G3's 5.76% rounds to 6. Allowing the trigger's numbers clears
the check, and nothing else changes in either month (replayed). The real defect is that
the action repeats the finding (F-054).

Client cards:

| Run | Trigger | Action | Button |
| --- | ------- | ------ | ------ |
| 4 | T1 | "Send us two more educational visa-advice videos this month, and we'll post them for you." | "Send us 2 videos" |
| 4 | T2 | "Send us two English promo videos with a different opening this month, and we'll post them for you." | "Send us 2 promo videos" |
| 4 | T3 | "Please send us three educational videos this month, and we'll post them for you." | "Send us 3 videos" |
| 5 | T1 | "Your English Instagram video had 52% of viewers still watching after 3 seconds, below the 90-day average of 57%; send us two more this month with a different opening, and we'll post them." | "Send us 2 more videos" |
| 5 | T3 | "We posted 6 of the 16 posts planned for September; send us three educational videos for October, and we'll post them." | "Send us 3 educational videos" |

- Each action asks for the request with its quantity, and each button has 4 or 5 words
  with a number. They are plain English, use "we" for posting, and promise nothing
  about visas or catching up.
- October's three actions follow from the finding without repeating it.
- September's two do repeat it. The rendered T3 card reads "We posted 6 of the 16 posts
  planned for September. We posted 6 of the 16 posts planned for September; send us…".
  The T1 card gives the same drop-off twice and puts "90-day average" on the card, where
  the code's wording is "your usual" (F-054).
- October's T1 action asks for "educational visa-advice videos", which is the request,
  not the "Nepali TikTok" the finding names. It is consistent with the request
  (`language` any).

False negatives (finalize):

- September T1's hypothesis cites no comparison, only the flagged post (F-052).
- October T2's request changes the opening while its hypothesis and comparison are about
  the pillar. September T1's request does the same with no comparison (F-053).
- September's card actions repeat the finding (F-054).
- September T3's `why_unknown` is empty: the model put its reason in review note 1, and
  `insights.md` shows only "the numbers cannot say." Nothing flags it. It is harmless
  here, so it is a note, not a finding.
- video_003's topic tags, made before `organisation.json`, send the misheard
  "cleary-consulting-group" to the model in both months (F-056; no output used it).

### Re-test (runs 6 and 7)

Reviewed read-only in the same way. The pasted output was garbled, so only the files
were trusted. Both plans were regenerated for free with `prepare.py --force`. The
estimates, 5,357 (October) and 3,483 (September), equal the runs'
`estimated_input_tokens`, and `replaces` equals each result's `created_at`. Both job
folders were deleted, and `work/draft-insights/` is empty. A replay of finalize's checks
on the saved results, with the regenerated plans, gives exactly the saved checks (3 and
0). Nothing paid was run.

What now passes:

- **Numbers:** every number in all texts was checked by hand against the regenerated
  refs, and each one is in what its sentence cites. The replay of the number, cited
  number and ratio checks is empty.
  - October:
    - 10.23%, 2.2×, 90 and 4.7% (T1's observation: T1, BL)
    - 6 posts and 4 pieces of content (G4) in T1's hypothesis
    - 4.7% and 2 new posts in T1's test (the bar)
    - 52%, 48% and 3 seconds (T2)
    - 2 posts and 2 pieces of content (G7), and 58% (the bar) in T2's test
    - 8, 16 and 8 behind (T3)
    - quantities 2, 2 and 3 in titles, briefs, card actions and buttons
  - September: 6, 16 and 10 (T3), and quantity 3.

  The only ratio is 2.2×, in T1's observation and the code's card finding. There is no
  "twice", "half" or "double".
- **Causes, names and refs:** "since" appears only inside the two hypotheses.
  September's `why_unknown` has "because it does not include what you sent", which
  explains missing data. No person is named, the organisation is not named, and no
  reference code is in any text. Nothing promises a visa outcome or to catch up.
- **Categories and quantities:** all 4 requests are video, which follows `format_lean`
  (video in both months). The quota request is 3 in both months, from the trigger. The
  post-trigger requests are 2 each.
- **Card findings and actions:** all 4 findings are prepare's `card` sentence. The 4
  actions start from the ask, carry only the quantity, and say "you" and "we":
  - "You could send us two more videos in this style, and we'll post them for you next
    month." [Send us 2 videos]
  - "You could send us two English educational videos, and we'll post them for you next
    month." [Send us 2 videos]
  - "Please send us three educational videos that open with a question, and we'll plan
    their posts together for next month." [Send us 3 videos]
  - "Send us three more English educational videos, and we'll post them on Instagram."
    [Send us 3 videos]
- **Held back:** September's Partial ci-2609-04 is in `held_back`, out of every
  comparison and never mentioned.
- **`metadata.json`:** both have `status` complete. `replaces` is 2026-11-06T09:13:26
  (October, run 4) and 09:14:05 (September, run 5), and the history folders hold runs 1
  to 5 unchanged (run 4's own `replaces` is still run 2's 08:57:27). `window_reports` is
  right: both reports for October, only 2026-09.json for September. `triggers` records
  `card`, `bar` and `quantity`, and `format_lean` and `pillars` are kept. Neither holds
  `context`, `refs`, `allowed_numbers` or `general_numbers`. Both `insights.md` headers
  list every window report.
- **Tokens:** October's estimate ran 4.6% under (5,357 against 5,615; run 4: 5.0%).
  September's ran 1.9% over (3,483 against 3,417; run 5: 1.4%). Output tokens were
  1,535 and 663 (runs 4 and 5: 1,751 and 1,270). September's fell because two triggers
  are now answered in one sentence each.

F-052 to F-055 on the actual output:

- **A comparison for every hypothesis (F-052):** both hypotheses cite one comparison
  that bears on their trigger: T1 cites G4 (bears on T1) and T2 cites G7 (bears on T2).
  Neither cites a post alone.
- **September T1 and T2 (F-052):** both are "not enough evidence", and the model decided
  it, not the code. The reason, "No comparison bears on this result, and the video
  cannot explain its own result.", is the model's. The code's would end "(decided by
  the scripts)". The model followed prepare's new line under each trigger, "no
  comparison bears on this trigger: answer enough_evidence false". The code's fallback
  was not exercised. It was checked by a replay of `clean_answer` with run 5's T1 answer
  (hypothesis citing only P1) on the regenerated plan. The hypothesis goes to `dropped`
  with "it cites no comparison for this trigger", and T1 goes to `not_enough_evidence`
  with the code's reason. Both reasons are correct, but they are now identical and
  generic: run 5's "no opening, topic, or comparison" for T2 was more specific.
- **Each request changes only what its comparison is about (F-053):**
  - T2 (G7, pillar): it changes only the pillar: "keeping the format, platform,
    language and opening style of your flagged video, but changing its pillar from
    promotional to educational".
  - T1 (G4, format): P7 is already a video, so there is nothing to change. The request
    repeats P7 ("keeping its topic and opening approach"), which the rule allows.
  - Neither post-trigger request changes the opening, and no "another opening" wording
    appears. T3's question opening comes from G16, and the quota request asks for what
    works best, so the rule does not apply to it.
  - Both hypotheses are still advice, not reasons: "Video format may be one factor worth
    testing" and "A promotional pillar may be worth reconsidering". The HEDGE check
    passes them on "may". This is F-053's second half, which the fix did not cover.
- **Card actions (F-054):** the repeat check raised nothing, and that is right. No
  action gives a trigger number other than the quantity: "two" and "three" match the
  quantities 2 and 3. No action shares half its words with the finding. The most it
  shares is "english" in T2's action, 1 of 9 words. "90-day" is still not in
  `CLIENT_TERMS`, but no card used it (latent).
- **Look-alike check (F-055):** it now reads the first pillar named in each title and
  brief. In October that is "educational" for all three requests: T2's brief also says
  "promotional", but its title names educational first. So the three checks are right
  by the rule. September has one request and no check.

Do all three October requests ask for educational videos? Yes:

| Trigger | Request | Tests | Measure, bar | What sets it apart |
| ------- | ------- | ----- | ------------ | ------------------ |
| T1 | "2 more Nepali TikTok videos": "two educational TikTok videos in the same Nepali style as your successful video, keeping its topic and opening approach" | 1 (G4, video vs other formats) | engagement, 4.7% | TikTok, Nepali, P7's curiosity opening |
| T2 | "2 educational Instagram videos": English, keeping P8's format, platform, language and opening style, pillar promo → educational | 1 (G7, promo vs other pillars) | still watching after 3 s, 58% | Instagram, English, P8's statement opening |
| T3 | "3 question-hook educational videos": "open with a question, using the same platform, language and visual approach as each video you already make" | 0 (G16 question hook, G11 educational 2×) | none | a question opening |

Each of the three follows its evidence:

- T1's comparisons (G1 to G4) are all about P7's own features (video, educational), so
  keeping the rest like P7 means an educational video.
- G7's other side (P2, P6, P7, P11) is all educational, so changing only the pillar
  means educational.
- The quota request asks for "what the comparisons show works best", and the strongest
  comparison is G11 (educational, 2×).

The instruction also says "never the same kind of post for two triggers". With one
pillar leading every comparison, that rule cannot be met together with the other three,
and the model broke it. Its own note 4 asks the strategist to "confirm the three
requested items are … distinct from the other requests". October has had a shared-kind
pair in every run: run 1 T1/T2, run 2 T1/T3, run 4 T1/T3, and run 6 all three. So this
is a design problem, not model noise (F-057).

Does T2's request still test its hypothesis? Yes, and it is the cleanest test of the
three:

- It holds P8's platform, language, format and statement opening, and changes the one
  thing G7 is about.
- If 2 such educational videos average more than 58% still watching after 3 seconds,
  the pillar is supported against P8's 48%. If not, it counts against it.
- It is "only what the comparison is about": the pillar is the only change.
- Two caveats for the strategist:
  - The new videos cannot keep P8's opening line itself (a visa-grant statement), only
    its statement style.
  - It stops testing promos: nothing tells the client what to do about the success-story
    promo that lost viewers.
- Its controls are only in the brief. The card says "two English educational videos".
  T3's card asks in the same month for educational videos that open with a question, so
  a client who sends question-opening videos for both breaks T2's test without knowing.

Recommendation on the overlap: leave the decision to the strategist, but give them a
correct check. Do not merge the requests in code, and do not let T3 take them over:

- A code merge would destroy two different tests. T1 measures engagement at 4.7% on a
  Nepali TikTok repeat. T2 measures 3-second retention at 58% on an English Instagram
  video with a statement opening. One merged request would test neither.
- If T3 took over, two tests would become one untested ask (`tests` 0) with no confirm
  or refute.
- The quota request is the one that overlaps by design. It is told to ask for what works
  best, and a positive post trigger's request will usually be exactly that.
- So the design should accept a shared kind when the evidence points there. Each brief
  (and each card, for a test) then says what sets it apart. The check should alert only
  where nothing sets two requests apart. The month's total ask should be one
  informational line, not three "merge them" alerts. The current advice, "merge them or
  make each test its own hypothesis", is wrong for T1/T2, which already test their own.
  Three such alerts on an overlap the evidence produces are the F-029 pattern. See F-057.

September T3 alone is usable:

- "3 more educational Instagram videos" (English) cites G1 and G2 (Instagram: reach
  3.2×, engagement 2×), G3 (educational: engagement 1.9×) and G4 (video: reach 1.8×).
  All four bear on T3.
- Its category is video, which follows `format_lean` (video, G4 and G6). Its pillar,
  platform and format each follow a cited comparison.
- English is not backed by a language comparison, but all 5 September posts are in
  English, and the instruction restricts only "ne".
- The topic ("a practical question about preparing a visa application") comes from P2's
  material, not from a comparison. The strategist may change it.
- `why_unknown` is kept, and the card does not repeat the finding.
- With no hypotheses and no review notes, nothing says that every comparison has 2 or 3
  posts on a side. That is acceptable for a request that tests nothing.

T1's test is weak (F-058). The bar it uses is the 90-day average (4.7%). That is allowed,
but G4's own videos, without P7, already average 5.02%. So an ordinary video would
confirm "video format" as the reason for a 2.2× result, and a 1.4× comparison cannot
account for 2.2×. Run 4's T1 used G3 and set the bar at its 5.94%. The model's note 2
says as much: "check whether the proposed repeat is a useful test".

T1's request asks for Nepali TikTok videos with `language` any (F-059). The instruction
allows "ne" only when a comparison about Nepali posts supports it. No such comparison
bears on T1: with P7 left out, only one other Nepali post remains (F-051). But the same
instruction also says to keep the rest like the flagged post.

False alarms: the three look-alike checks are true by their rule, but their advice is
wrong for T1/T2, and the overlap is by design (F-057). There are no other checks.

False negatives (finalize):

- T1's bar is below what its comparison's own side already averages (F-058).
- T1's language field disagrees with its title and brief (F-059).
- Both hypotheses are advice ("worth testing", "worth reconsidering"), not reasons
  (F-053, second half).
- October's `why_unknown` is empty again: the reason went to review note 1, and
  `insights.md` shows only "the numbers cannot say." That is 2 of the last 4 quota
  insights (run 5 and run 6). It is still harmless, so it is a note.
- video_003's outdated topic tags still send "cleary-consulting-group" in both plans
  (F-056). No text used it.

Overall: September (run 7) is usable as it is. October (run 6) is usable after normal
strategist edits:

- choose whether the client sees one or three asks for educational videos
- raise T1's bar to 5.02% or cite G3
- set T1's language to ne
- reword the two hypotheses as reasons

Nothing blocks either month.

### Re-test (runs 8 and 9)

Reviewed read-only in the same way. The pasted output was garbled, so only the files
were trusted. Both plans were regenerated for free with `prepare.py --force`. The
estimates, 5,452 (October) and 3,579 (September), equal the runs'
`estimated_input_tokens`, and `replaces` equals each result's `created_at` (09:45:18 and
09:45:47). Both job folders were deleted, and `work/draft-insights/` is empty. A replay
of finalize's checks on the saved results, with the regenerated plans, gives exactly the
saved checks (0 and 0) and the same `total_ask`. Nothing paid was run.

The video_003 re-tag (F-056):

- `/tag-topics input/video_003.MOV force` gave 7 tags for 1,453 input and 416 output
  tokens (estimate 1,543, 6% over). The old result is in `history/20261105-084233/`, and
  `metadata.replaces` is its 2026-11-05T08:42:33. The new `inputs` record
  `organisation.json`, so the result is no longer outdated.
- The tags and their evidence:
  - type: educational-advice (S4, S6), advertisement (S6, V:speaking-to-camera)
  - topic: student-visa (S1 to S6), visa-success-story (S2, S5; `new`), further-study
    (S4 to S6), visa-application (S6)
  - entity: tilicho-consulting-group (S6)

  The old result also had 7 tags, but every one cited only S1 (F-009). Its entity was
  cleary-consulting-group, and it had bachelor-degree and masters-degree topics.
- **The misheard name is gone.** S6 ends "you can contact Cleary Consulting Group". The
  entity is spelled as `organisation.json` gives it, and it cites S6, the sentence that
  names the organisation. "Cleary" is not in `heard_as` (Tilottama, तिलोत्तमा), so the model
  corrected it from the ORGANISATION section, not from a listed mishearing.
- **Rules:** every tag is English, lowercase and hyphenated. Each cites the sentence that
  states it, checked against the transcript's sentences S1 to S7. No person is named in
  the tags or the summary ("A consultancy describes helping a client…").
- **One judgement call (a note, not a finding):** educational-advice (high) is given to a
  video whose Pulse pillar is Promo. It cites S4 (guidance given to that client) and S6
  (the invitation to get in touch). The comparisons take the pillar from Pulse, not from
  the tags, and no text in runs 8 or 9 used the type.
- **The October and September material:** P1 and P8 carry the new tags and summary. A
  search of both regenerated plans finds no "cleary", "trilochan" or other wrong form.
  "Tilottama" and "तिलोत्तमा" appear only in the ORGANISATION section. Both
  `metadata.json` files record topics created 2026-11-06T09:44:50 for ci-2609-01 and
  ci-2610-03, so both runs used the new tags. All three videos in the reports (003, 007
  and 014) now have topic results made with `organisation.json`.
- **Residual (latent, outside these months):** the tag library still holds
  trilochan-consulting-group, from video_004's result. That result was made on
  2026-11-05, before `organisation.json` was an input, and video_004 is in no report. The
  re-tag offered it to the model as an existing entity tag (uses 1). video_004, video_006
  and video_008 are still outdated. draft-insights' prepare still does not warn about a
  post's outdated topic tags, but every reported video is now current.

What passes in runs 8 and 9:

- **Numbers:** every number in all texts was checked by hand against the regenerated
  refs, and each one is in what its sentence cites. The replay of the number, cited
  number and ratio checks is empty.
  - October:
    - 10.23%, 2.2×, 90 and 4.7% (T1's observation)
    - 5.94%, 3.43% and 3 pieces of content (G3) in T1's hypothesis
    - 2 and 5.94% in T1's test
    - 52%, 48% and 3 seconds (T2's observation)
    - 49.65%, 67.53% and 2 pieces of content (G7) in T2's hypothesis
    - 2 and 67.53% in T2's test
    - 8 and 16 (T3)
    - quantities 2, 2 and 3 in titles, briefs, card actions and buttons
  - September: 6, 16 and 10 (T3), and quantity 3.

  The only ratio is 2.2×, in T1's observation and the code's card finding. There is no
  "twice", "half" or "double".
- **Causes, names, refs and promises:** "as" and "contributed" appear only inside the
  hypotheses. Both `why_unknown` say "because it does not include what you sent,
  approvals, or the schedule", which explains missing data. No person or organisation is
  named, and no reference code is in any text. Nothing promises a visa outcome or to
  catch up. The cards promise only "we'll post them".
- **Categories, quantities and languages:**
  - All 4 requests are video, which follows `format_lean` (video in both months).
  - The quota request is 3 in both months, from the trigger. The post-trigger requests
    are 2 each.
  - October T1 is ne (its brief names Nepali), T2 is en (English), and T3 is any. It
    names neither, and neither does September's T3. A replay of `language_of` agrees
    with each field.
- **A comparison for every hypothesis:** T1 cites G3 (pillar, engagement, bears on T1).
  T2 cites G7 (pillar, still watching after 3 s, bears on T2). Both point the right way
  on their trigger's measure, give their pieces of content and call the pattern early.
- **Test bars:**

  | Trigger | Measure | 90-day average | Cited group's average | Bar | The test |
  | ------- | ------- | -------------- | --------------------- | --- | -------- |
  | T1 | engagement | 4.7% | G3 educational 5.94% | 5.94% | above 5.94% |
  | T2 | still watching after 3 s | 58% | G7 promo 49.65% | 58% | above 67.53% (the other pillars' average, the side the request asks for) |

  Both tests are at or above their bar, and the bar check rightly fired on nothing. An
  ordinary English educational Instagram video already holds about 70% (G8's
  Instagram side is 69.95%), so T2's test would usually pass. That is how a drop-off test
  is meant to work: it asks whether changing only the pillar brings the post back to
  normal (F-058 kept it this way on purpose).
- **Card findings and actions:** all 4 findings are prepare's `card` sentence word for
  word. The 4 actions start from the ask and carry only the quantity. The replay of the
  repeat check is empty:
  - "Send us two more educational videos this month, and we'll post them on TikTok."
    [Send us 2 more videos]
  - "Send us two more educational videos this month, and we'll post them on Instagram."
    [Send us 2 more videos]
  - "Send us three educational videos this month, and we'll post them for you." [Send
    us 3 more videos]
  - September: "Send us three educational videos on different practical
    visa-application questions, and we'll post them for you." [Send us 3 videos]
- **Held back and not enough evidence (September):** the Partial ci-2609-04 is in
  `held_back`, left out of every comparison and never mentioned. T1 and T2 are "not
  enough evidence", decided by the model after prepare's "no comparison bears on this
  trigger" line. The reason now names the measure: "No comparison bears on still
  watching after 3 seconds, and the video cannot explain its own result." That is right:
  G1 to G7 measure reach and engagement only.
- **Total ask:** October's "Requests for November 2026: 7 videos (T1 2, T2 2, T3 3)." is
  2 + 2 + 3, all video. September's is "Requests for October 2026: 3 videos (T3 3)." Both
  are in `insights.json` and in the `insights.md` header.
- **`metadata.json`:** both have `status` complete. `replaces` is 09:30:32 (run 6) and
  09:31:02 (run 7). The history folders hold runs 1, 2, 4 and 6 (October) and 3, 5 and 7
  (September), each with its `replaces` chain intact. `window_reports` is right, and
  neither file holds `context`, `refs`, `allowed_numbers` or `general_numbers`.
- **Tokens:** October's estimate ran 4.5% under (5,452 against 5,711; run 6: 4.6%).
  September's ran 1.9% over (3,579 against 3,510; run 7: 1.9%). Both estimates rose by
  about 95 tokens from runs 6 and 7, for video_003's longer tags and summary. Output was
  1,564 and 729 tokens.

The fixes on the actual output:

- **F-057:** T1 and T2 share a kind (educational) and a kind of comparison (pillar: G3
  and G7). Their language (ne, en) and platform (TikTok, Instagram) set them apart, so
  the check rightly raised nothing. T3 is left out by design, and the total ask replaces
  run 6's three alerts. T3 no longer asks for question openings, so run 6's risk is gone:
  a client sending question-opening videos for both T2 and T3. What sets T1 and T2 apart
  is only in the brief and the Language column, though. Both titles are "2 more
  educational videos", and their cards differ only by platform. A retitle would help the
  strategist, but it is not a defect.
- **F-058:** T1's bar is G3's 5.94%, not the 4.7% below its group's average as in run 6.
- **F-059:** T1's `language` is ne, which matches its brief.
- **F-053:**
  - T1's hypothesis is now a reason: "Educational posts may have contributed to the
    strong result".
  - T2's "The promotional pillar may be one factor to investigate, as promotional posts
    averaged…" names the factor and its direction, which is acceptable. "To investigate"
    is still worded as a next step, and ADVICE does not list it (latent).
  - T2's request changes only the pillar (promo to educational), keeping English,
    Instagram and the flagged video's style.
  - T1's request repeats P7's kind, which the rule allows, since G3 is about the pillar
    and P7 is already educational. But its brief adds "the same … question-led approach
    as your flagged video". P7 used a curiosity hook ("Visitor visa refusals can hinge on
    a factor applicants may overlook."). The question hook is P2's, the same video on
    Instagram. So the brief describes the flagged post wrongly and adds a hook-style
    change that no T1 comparison is about (F-060).

Compared with runs 6 and 7:

- **October:**
  - T1 moved from G4 (format, with a 4.7% bar below that group's own 5.02%) to G3
    (pillar, bar 5.94%), and its language from any to ne.
  - Neither hypothesis says "worth testing" or "worth reconsidering" any more.
  - The checks fell from 3 to 0. All 3 of run 6's checks were the F-057 alerts.
  - T3 dropped its question opening, and `why_unknown` is kept (run 6's was empty).
  - New: T1's brief gets P7's hook wrong (F-060).
- **September:**
  - It has the same structure as run 7.
  - T3's request moved from "3 more English educational Instagram videos" (G1 to G4)
    to "3 educational videos" with no language or platform. It cites G3, G5, G4 and G6,
    with P2 as its model. Instagram is no longer asked for, though G1 (reach 3.2×) is the
    strongest comparison. Both readings follow the evidence.
  - Run 9 has 2 review notes, where run 7 had none. Note 2, that the comparisons favour
    educational and video posts separately but not together, is useful.

False negatives:

- **October:** F-060. No check reads what a brief says about the flagged post's opening.
  T2's "to investigate" is a latent wording gap, not an error.
- **September:** none. "No checks" is right.

Overall:

- **September (run 9)** is usable as it is.
- **October (run 8)** is usable after one edit: take "and question-led approach" out of
  T1's brief, or write "curiosity-led". The optional edits:
  - give T1 and T2 different titles
  - reword T2's hypothesis as a plain reason ("promo videos may lose more viewers in
    their first seconds")
  - decide whether the client sees the 7 educational videos on three cards

  Nothing blocks either month.

Still open across F-036 to F-060, and whether it matters:

- **F-060 (new, low):** one edit. The F-053 proposal it needs was not built: flag a
  brief that changes the opening when no comparison the request tests is about hooks.
- **F-053 residual (latent):** "to investigate" and similar next-step wording pass
  ADVICE. It is harmless in run 8.
- **F-054 residual (latent):** "90-day" is still not in `CLIENT_TERMS`. No card used it.
- **F-056 residual (latent):** prepare does not warn about outdated topic tags, and
  trilochan-consulting-group stays in the tag library from the outdated video_004. It
  does not matter for these months, but re-tagging video_004, video_006 and video_008
  would clear it.
- **F-044:** October's estimate still runs about 4.5% under. This is accepted.
- Nothing else in F-036 to F-059 is open.

## Fix status (2026-11-05, uncommitted; draft-report re-tested in runs 3 to 6, draft-insights in runs 4 to 9)

| Finding | Status | Change |
| ------- | ------ | ------ |
| F-001 | partly fixed | prepare warns when the transcript is one part; the prompt says a tag on screen for most of the video is the main shot, and prefers short shots and on-screen text for B-roll |
| F-002 | fixed | each hook and caption carries its own `translation`, so a dropped hook takes its translation with it; missing translations are named per hook and caption |
| F-003 | fixed (prompt) | every caption's text ends with its call to action, and its translation includes it |
| F-004 | fixed (prompt) | a subtitle covers only its own segment's soundbites |
| F-005 | fixed (prompt + check) | the first soundbite must stand alone; finalize flags an opening or closing soundbite cut at a part edge |
| F-006 | fixed (prompt) | hook styles defined; LinkedIn written as "we" in short paragraphs; the tone applies to every hook, caption and overlay |
| F-007 | fixed (prompt) | terms and abbreviations kept as said; hashtags only for what the material states |
| F-008 | fixed | `dropped` saved in `copy.json` |
| F-009 | fixed (prompt) | cause: the tag-topics instructions' example "(S1, T2, V:office)" was copied at low effort (video_003 and video_006 cite only S1; video_014 spreads over 6 sentences). The example no longer starts at S1, and the instructions say to cite the sentence that states it, not the first |
| F-010 | fixed (skill) | the ready message is a fixed list (inputs, organisation, platforms, language, translation, tone, brief, cost, replaces, warnings) shown in full; no warnings is not approval |
| F-011 | fixed for generate-copy | `organisation.json` (git-ignored, now holds Tilicho) is sent as the trusted spelling; partly read on-screen text is sent for checking names; finalize flags brand hashtags that neither the organisation nor the screen confirms. tag-topics now gets the same organisation section and partly read text, and records `organisation.json` among its inputs, so every saved topic result shows as `outdated` until it is re-made. `organisation.json` website set to tilicho.com.au (read clearly once in the frames; "tilicho.com" was only partly read); no hashtags were seen on screen |
| F-012 | fixed | the model follows the footage when the brief does not fit and says so in `review_notes`, which the skill quotes |
| F-013 | fixed (mark + check) | sentences cut at a part edge are marked (`cut`) in the soundbite and in `copy.md`; finalize flags an opening or closing one |
| F-014 | fixed | the speaker label is kept out of the soundbite text and recorded as `speaker` |
| F-015 | fixed (check) | finalize flags clearly read on-screen text (two words or more, not the organisation's name) that the copy repeats word for word |
| F-017 | fixed, confirmed in run 9 | finalize reads ranges and loose writing (S6-S8, S6–8, [S6], "S6 and S7") as each sentence; the prompt asks for one reference per sentence and to list both parts of a split sentence |
| F-018 | fixed | a video with speech whose script uses no soundbite is `incomplete` ("the script uses none of the speech") |
| F-019 | fixed | `copy.json` `dropped.for_their_references` keeps each dropped hook's and segment's references as written |
| F-010 (again) | accepted (user, 2026-11-05): the permission prompt before the paid step is the approval and the cost is small; prepare keeps printing `summary` | prepare prints `summary`, the seven ready lines already filled in; the skill shows them word for word instead of composing its own sentence |
| F-016 | fixed | `different_options` lists each changed option with its saved and new value; the skill says when a saved tone or brief would be dropped |
| F-020 | confirmed fixed (runs 5, 6): one sentence per item in every section of both months, `split` empty, and each sentence cites only its own data; counts and lengths are per sentence | the prompt asks for one sentence per item; finalize splits any item that still holds several sentences (each keeps the item's references, recorded in `split` with a check) and checks 2 to 4 sentences per paragraph |
| F-021 | confirmed fixed (runs 3 to 6): no "because" check fired; every September "because … incomplete" and "left out because" line is skipped | the cause check skips a sentence that explains missing data (incomplete, missing, not recorded, not shown, held back, not tracked, left out) |
| F-022 | confirmed fixed (runs 5, 6): no engine, snapshot, "client" or post code in either month; September's highlights name posts by subject | the prompt bans how the report is made (engine, snapshots, data quality, references, slots) and calling the people in posts "clients"; finalize flags engine, snapshot, data quality and highlight slot |
| F-023 | partly fixed (runs 5, 6): 5 of 7 September ranking lines say P4 is left out. What worked s1 and s2 cite P4 and do not; both are flagged, correctly (s2 is harmless in fact: P4's reach is recorded and lower). What remains is the model's compliance; the checks work | the highlights header says which posts are incomplete; a sentence about posts that ranks them (most, highest, fewest, more than any ...) while a post is Partial or Stale is flagged unless it says the post is left out |
| F-024 | regressed (run 5; fixed in run 3): "The two posts about student visa applications used the same question as their opening hook" (P1, P6: one video) is presented as a pattern in what worked; the model's own review note asks to check it | prepare marks a post made from the same video as an earlier one ("same video as P1, posted again on youtube: one video, not two"); the prompt says not to count them as different videos |
| F-025 | confirmed fixed (runs 5, 6): every highlight names its measure, and both engagement lines are a share. Minor: September's retention line "The most viewers watched … to the end" uses count wording for a share | a highlight line names the measure it rests on, never a wider claim such as "held viewers longest" |
| F-026 | fixed, still not exercised (runs 3 to 6): every number is in what its sentence cites; no wrong number appeared to test the check | each reference carries its own numbers; a number in the month's data but not in what its sentence cites (or the year, post counts, brand text) is flagged |
| F-027 | partly fixed (runs 5, 6): both headlines carry reach and enquiries. October still does not use its earlier months (third run), gives 15,400 three times and "the most likes, comments, shares and saves" twice; September's top post s2 gives four counts in one sentence | the headline carries people reached and enquiries when tracked; earlier months are used when given; each number once in the paragraphs |
| F-010 (draft-report) | not fixed (runs 3, 4): both ready messages were paraphrased again ("October 2026 has 8 posts … about 3,500 input tokens"), not `summary_text` in a fenced block | prepare prints `summary_text`, one block; the skill says to copy it unchanged into a fenced block, nothing in its place |
| F-028 to F-032 | re-tested in runs 5 and 6; see each row below | see each row below |
| F-028 | partly fixed (runs 5, 6): every ranking in both drafts agrees with LEADERS, so the data side works. The check side does not catch the run-4 error on its real wording and refs (F-033); the test that "flags" it cites only the wrong post and names one measure | prepare works out LEADERS (most and fewest per measure among posts with complete data) and the prompt ranks posts only from it; finalize checks every ranking of a post (most, highest, more ... than any, fewest ...) against it; the run-4 claim (P2 "reached more people than any other post") is flagged in a replay |
| F-029 | confirmed fixed (run 6): the 5 lines that cite P4 to leave it out raise nothing, and all 4 checks are real. Each unqualified line still gets two checks (Partial and ranking); `DATA_GAP` lacks "excluding", "except", "apart from", "not counting" (latent) | the Partial and ranking checks read the sentences split from one item together and skip lines that say the data is incomplete or the post is left out ("with complete data" counts); in the run-4 replay only the one unqualified line is flagged |
| F-030 | fixed, not exercised (runs 5, 6): no superlative check fired and none was due; no "strongest posts" wording appeared | the superlative check fires on comparisons of months (best, strongest ... month; so far; ever; since we started; record), not on "the strongest posts" |
| F-031 | confirmed fixed (runs 5, 6): items equal real sentences in all 10 sections, `split` empty in both | each sentence's `text` is described as "Exactly one sentence." in the schema |
| F-032 | confirmed fixed (run 6): "September reached 34,900 people, fewer than in August, and brought 18 enquiries." The fall in enquiries is not in the headline (the check does not require it) | the headline must say when fewer people were reached; finalize flags a headline in such a month without down, fell, fewer, lower ... |
| F-022 (refs in text) | confirmed fixed (runs 5, 6): no code in either month's text; `reference_checks` is empty in a replay | references (P2, M:reach) are for refs only; finalize flags one written into client text |
| F-025 (engagement) | confirmed fixed (runs 5, 6): October gives P2's 10.23% as the highest share, and gives P1 the most likes, comments, shares and saves, which it had | highest_engagement is the highest share of the people reached, not the most likes; LEADERS lists the engagement rate apart from the counts |
| F-033 | fixed (second replay, 2026-11-06): run 4's sentence (refs P2, P4, P1) gets "…the first is P2 on engagement rate; P1 on people reached: make sure that is the post it puts first.", and run 3's misleading engagement highlight gets "puts P2 first on comments, but P1 is first" (real). Over runs 3 to 6 the order check gives 4 "make sure" prompts, 2 real (run 4 s1, run 3 s1) and 2 on correct lines (F-035), plus 1 hard check, real. Latent: run 4's ranking against P4 ("more than any other post" on likes …) is no longer flagged, because "with complete data" later in the same sentence exempts the whole line | `measures_in` returns every measure named, with the engagement wording taken out before counts; `order_checks` adds a check naming the leader when a line cites it with other complete posts; MOST/FEWEST know widest, topped, came first, led, ahead of, came last, trailed |
| F-034 | open (October runs 3 and 5) | none yet |
| F-035 | partly fixed (second replay, 2026-11-06): the two false "first on engagement rate" checks on October's retention lines are gone, and no retention line is read as engagement in runs 3 to 6. The shared-leader prompt still fires on 2 correct lines (October what worked s3, September what worked s1) | ENGAGEMENT matches only "engag…" and "liked, commented (on), shared or/and saved"; "share of (the) people/viewers …" is a separate SHARE pattern removed only before counts are matched |
| F-010 (draft-report) | accepted (user, 2026-11-05), as for generate-copy | the permission prompt before the paid step is the approval; prepare still prints `summary_text` |
| F-036 | confirmed fixed (runs 4, 5): video_003 is now shown as "sitting, speaking-to-camera, office, white-suit, … person", 12 of its 13 tags tied at 48.2 s with only "plant" cut. Neither plan has a visual-tag comparison, and no text rests on one | prepare groups a video by every visual tag; the model reads the 8 longest on screen (ties no longer cut alphabetically) |
| F-037 | confirmed fixed (runs 4, 5): quantities are 2, 2 and 3 in October and 2 and 3 in September, and all 5 requests are video, which follows `format_lean` | the instruction asks for 2 by default (up to 3 for the quota trigger, 1 only to repeat a post); a video vs picture comparison gives the category evidence. Quantities stay capped by next month's quota (the requests are for next month) |
| F-038 | confirmed fixed for the test design (run 6): each post-trigger request tests one hypothesis (`tests` 1, 1), and T2's changes only the pillar its comparison is about, keeping P8's platform, language and opening. All three October requests now share the educational kind, which their evidence produces (F-057). Earlier: partly fixed (runs 4, 5): each request tests one hypothesis (`tests` 1, 1, 0 / 1, 0) and keeps the flagged kind (English promo videos for both drop-off triggers). October T1 and T3 still ask for educational visa-advice videos (F-046), and the drop-off requests change the opening, which no comparison they cite is about (F-053) | each request names the hypothesis it tests (`tests`) and changes only that, keeping the flagged kind of post; finalize flags two requests with the same category and much the same brief |
| F-039 | confirmed fixed (runs 2, 4, 5): every test names the measure, a number to beat and "2 new" posts; since F-045 the number is at or above the bar | tests name the measure, the number to beat and how many posts; finalize flags a test with no measure word |
| F-040 | confirmed fixed (runs 4, 5): every label gives "N posts of M pieces of content" when the counts differ, every hypothesis gives its pieces of content (3, 2, one), and a post trigger's comparisons no longer hold its own post (F-051) | a comparison needs 2 different pieces of content on each side, shows "N posts of M pieces of content", and says which side holds the own post (and its twin) of a trigger it bears on; differences under 10% are left out (18 comparisons in October, about 5,400 input tokens) |
| F-041 | confirmed fixed (runs 2, 4, 5); the card finding is now written by code (F-048): "A bigger share of the people who saw your Nepali TikTok video liked, commented on, shared or saved it: 2.2× your usual." | the instruction gives the share wording and the ratio; finalize flags a client line on an engagement rate in count words without a share or ratio |
| F-042 | confirmed fixed (runs 2 to 9): neither month has a hypothesis for the quota trigger, and nothing was dropped. `why_unknown` is kept in runs 7, 8 and 9. In runs 5 and 6 the model left it empty and put the reason in a review note, so `insights.md` showed only "the numbers cannot say." (harmless) | the quota trigger gets no hypotheses (the reason says what the data lacks); finalize drops any the model writes and `insights.md` says the numbers cannot tell why |
| F-043 | confirmed fixed (runs 2 to 5): every button has a number ("Send us 2 videos", "Send us 2 promo videos", "Send us 3 videos", "Send us 2 more videos", "Send us 3 educational videos"), and posting is "we". September's card actions repeat the finding (F-054) | the card names the kind of post, carries its number, uses "we" for posting; finalize flags a button without a quantity, and "slots" is an internal term |
| F-044 | confirmed fixed for `insights.md` (runs 2 to 5): both headers list every window report. The estimate, left as it is, ran 5.0% under in October and 1.4% over in September (run 4: 5,288 against 5,555; run 5: 3,359 against 3,313) | `insights.md` lists every report input in the window; the token estimate is left as it is (shared estimator, rough by design) |
| F-045 | confirmed fixed (runs 4, 5): every test is at or above its bar. October T1 is "each above 5.94%" (bar 4.7%), T2 is "more than 58%" (bar 58%), and September T1 is "above 57%" (bar 57%). Each refute_if is at the average. The bar check fired on nothing, and nothing was due | each post trigger gives the bar a test must beat (the 90-day average); finalize flags a test confirmed below it |
| F-046 | closed through F-057 (run 8): the shared kind follows from the evidence. The check now leaves out the quota request and flags only pairs nothing sets apart, and it raised nothing on run 8's T1/T2 (ne TikTok, en Instagram). Earlier (runs 4, 6): it flagged the real run-4 T1/T3 duplicate (0.35) and a false T2/T3 alarm (0.27, F-055), then all three run-6 pairs (F-057) | the look-alike check reads title and brief, without filler words, at 0.25 (duplicates scored 0.28 and 0.50, different requests at most 0.18 in runs 1 to 3) |
| F-047 | confirmed fixed (runs 4, 5): `format_lean` is video in both months, all 5 requests are video, and September's T3 moved from photos to videos. The check fired on nothing, and nothing was due | prepare works out the format the numbers favour (video in both months); finalize flags a request category against it, and the instruction says the category follows the comparisons |
| F-048 | confirmed fixed (runs 4, 5): all 5 card findings are prepare's `card` sentence word for word, and no card says "engagement rate" or "pillars". But September's card actions repeat the finding, and the number check flags the repeat (F-054) | the card's finding is one sentence per rule, written by prepare from the trigger ("…2.2× your usual."); the model writes only the action and button, so "engagement rate" and "pillars" cannot reach the finding |
| F-049 | confirmed fixed (runs 4, 5): the quota request is 3 in both months (gaps 8 and 10), taken from the trigger, and "catch up" is in no text | the quota trigger's request size is set from the gap (at most 3) and overrides the model's; "catch up" is a client-card term and the instruction forbids the promise |
| F-050 | confirmed fixed (runs 4, 5): P1 and P8 show activities first ("sitting, speaking-to-camera"), then "office" and "white-suit", then objects ending in "person". That is 12 of 13 tied tags, with "plant" cut | tags equally long on screen list activities, then scenes, attributes and objects; up to 12 are shown |
| F-051 | confirmed fixed for comparisons (runs 4, 5): October T1's G1 to G4 are worked out without P2 and P7, and T2's G5 to G9 without P1 and P8, so no hypothesis cites a comparison that holds its own post. With no comparison left, September T1's hypothesis cites the post itself (F-052). October T2's hypothesis is still a suggestion ("may be worth testing with a different opening"), not a reason (F-053) | a trigger's comparisons are the groups its post belongs to, worked out without the post and the same video posted again (October T1: the Nepali TikTok comparison disappears, as only one other Nepali post is left) |
| F-052 | confirmed fixed (runs 6, 7, 9): both October hypotheses cite a comparison that bears on their trigger (run 6: G4, G7; run 8: G3, G7). September's T1 and T2 are "not enough evidence" in runs 7 and 9, decided by the model after prepare's "no comparison bears on this trigger" line. In run 9 the reason names the measure ("No comparison bears on still watching after 3 seconds…"). The code's fallback, replayed with run 5's T1 answer, drops the P1-only hypothesis and gives T1 its own reason ("decided by the scripts") | finalize keeps a post trigger's hypothesis only if it cites a comparison bearing on that trigger; a post trigger no comparison bears on becomes "not enough evidence" in code; prepare tells the model so (both September drop-off triggers) |
| F-053 | fixed for the hypotheses (run 8); the request half is let down by F-060. T1's hypothesis is a reason ("Educational posts may have contributed to the strong result"). T2's "may be one factor to investigate, as promotional posts averaged…" names the factor and is acceptable, but "investigate" is a next-step word ADVICE does not list (latent). T2's request changes only the pillar. T1's repeats P7's kind but its brief adds a "question-led approach" P7 does not have (F-060); the proposed check on briefs that change the opening was not built. Run 6: both hypotheses were advice ("worth testing", "worth reconsidering") | the "another opening" example is gone; the request changes only what the cited comparison is about (pillar, platform, language, format, hook style); a hypothesis is a possible reason, never advice, and finalize flags "worth testing", "consider", "should" and the like |
| F-054 | confirmed fixed (runs 6 to 9): none of the 8 card actions repeats its finding. Each starts from the ask and carries only the quantity, and the repeat check rightly raised nothing (the replay on runs 8 and 9 is empty too). "90-day" is still not in `CLIENT_TERMS` (latent; no card used it) | the card action and button may use their trigger's numbers; finalize flags an action that gives the trigger's numbers again (not the quantity) or shares half its words with the finding; the instruction says the card shows the finding just before the action |
| F-055 | confirmed fixed as specified (runs 6, 7): the boilerplate false alarm is gone, and the check reads the kind. In run 6 it flags T1/T2, T1/T3 and T2/T3, and all three requests do ask for educational videos. But the overlap comes from the evidence, and the advice "merge them or make each test its own hypothesis" is wrong for T1/T2, which already test their own (F-057) | two requests are the same when they share the category and the first pillar their title or brief names; prepare records the pillars |
| F-056 | fixed by the re-tag (runs 8, 9): `/tag-topics input/video_003.MOV force` (2026-11-06T09:44:50, records `organisation.json`) gives entity tilicho-consulting-group on S6, which says "Cleary Consulting Group". Both regenerated plans give P1 and P8 the new tags, and neither has "cleary" or any other wrong form. All three reported videos (003, 007, 014) are current. Residual, latent: no code guard (prepare does not warn about outdated topic tags), and the library still holds trilochan-consulting-group from the outdated video_004, which is in no report | none yet |
| F-057 | confirmed fixed (run 8): no look-alike check fired. T1 and T2 share kind and comparison type (educational, pillar) but differ in language (ne, en) and platform (TikTok, Instagram); the quota request is left out. `total_ask` is "Requests for November 2026: 7 videos (T1 2, T2 2, T3 3).", right and in the `insights.md` header. T3 no longer asks for question openings. Minor: T1 and T2 share the title "2 more educational videos" | requests may share a kind when the evidence points there; the check leaves out the quota request and flags a pair only when language, platform named and the kinds of comparison tested are all the same; finalize adds the month's total ask (`total_ask`, in `insights.md`) |
| F-058 | confirmed fixed (run 8): T1's test is "above 5.94%", G3's educational average (bar max(4.7%, 5.94%)). T2's 67.53% is above its bar of 58% (G7's promo side is 49.65%). The bar check rightly fired on nothing. The replay on run 6 flags its 4.7% against 5.02% | a hypothesis's bar is the higher of the 90-day average and each cited group's average on the trigger's measure, checked per hypothesis (a bar raised over all of a trigger's groups was tried and was too strict: T2's became 69.95%) |
| F-059 | confirmed fixed (runs 8, 9): T1's `language` is ne and its brief names Nepali; T2 is en (English); both T3s are any and name neither. A replay of `language_of` agrees with every field | the request's language is the one its title or brief names when it names exactly one; the instruction says to name a language only when it is set |
| F-060 | open, left to the strategist (October run 8): delete "and question-led approach" from T1's brief | no check reads hook wording; not worth one yet |
| Latent items after runs 8 and 9 | fixed, not re-run (2026-11-06) | F-053: "investigate" is advice words; "90-day" (any "N-day") is a client-card term; F-056: prepare warns when a post's topic tags are outdated, as tag-topics would call them. On the real months it warns for video_014 and video_007, which tag-topics' own prepare also reports as outdated, and not for the re-tagged video_003; re-tagging them is a paid /tag-topics run each |

## Findings

### F-001: Edit script is not locatable for single-part / single-shot material (medium)

- **Observed:** Every soundbite cites `speech 00:00:00-00:00:48`. The B-roll cues are the
  talking-head shot itself, so they are not cutaways an editor can use. The script is
  therefore not usable as an edit, and prepare raised no warning.
- **Evidence:** `transcript.json` has `timestamps` "none" and a single entry in
  `parts` (0.0 to 48.167), so every `script.segments[*].soundbites[*].start_seconds`/`end_seconds`
  is 0.0/48.167. In `tags.json`, 13 of 15 tags span `[[0.0, 48.167]]`. The B-roll in
  `segments[0]`, `[2]` and `[3]` is `V:speaking-to-camera` plus `V:office` or `V:desk`.
  The metadata `warnings` is [].
- **Fix direction:** prepare should warn when the transcript has no timestamps or one
  part, and when no visual tag is shorter than the file (no cutaway footage).
  Instruct the model to leave B-roll empty, or to note "no cutaway footage", rather than
  citing the main shot. Consider sentence-level times from transcribe.
- **Seen again: video_014 (partly):**
  - The soundbite half is resolved when the transcript has parts. The 8 parts of about
    15 s give distinct times (for example S6 at 00:00:15-00:00:26), so the half that
    stays open is the B-roll.
  - The B-roll is still whole-video tags: V:speaking-to-camera and V:office
    `[[0,84.392]]`, V:gesturing `[[5,84.392]]`, and the generic V:text-on-screen. No T
    refs are used as B-roll, and `warnings` is again [].

### F-002: Translated hooks are not tied to the kept English hooks (medium, latent)

- **Observed:** `clean_translation` keeps `translation.hooks` exactly as the model
  answered. When finalize drops an English hook (no footage or a repeat), its
  translation stays, without evidence, and the numbering no longer lines up.
  Translated hooks are not capped at `MAX_HOOKS`, and `missing_parts` never compares the
  two counts. Run 1 did not trigger this (4 = 4, none dropped per the session).
- **Evidence:** `processors/generate-copy/finalize.py` `clean_translation` and
  `missing_parts`. The `dropped` count is not saved in the result (see F-008).
- **Fix direction:** keep translated hooks by index for the kept hooks only, and
  report a count mismatch in `missing` or `checks`.

### F-003: Call to action is inconsistent between caption text and field; lost in translation (low)

- **Observed:** The TikTok caption text has no call to action; it is only in
  `call_to_action`. The Instagram text has it in both places. `translation.captions[]`
  has no `call_to_action` field, so the Nepali TikTok caption has no call to action at
  all.
- **Evidence:** `captions[1].text` ends with a question, while
  `captions[1].call_to_action` is "Contact Cleary Consulting Group." The translation
  schema in `generate.py` is `{platform, text}`.
- **Fix direction:** decide on one form. Either the caption text must end with its call
  to action, or the translation also carries `call_to_action`.

### F-004: Subtitles do not match their segment's soundbites (low)

- **Observed:** The segment 3 subtitle starts with content from S4, but S4 is a
  soundbite of segment 2. The segment 2 subtitle leaves that content out. Burned-in
  subtitles would show the wrong words.
- **Evidence:** `script.segments[2].subtitle` opens "After they completed their
  bachelor's degree, we guided them…". Its `soundbites` holds only S5, and S4 sits in
  `segments[1].soundbites`.
- **Fix direction:** tell the model that a subtitle translates exactly the cited
  soundbites, in order. Consider one subtitle per soundbite.
- **Seen again: video_014:** `script.segments[2].subtitle` ends with "age, social,
  financial and family commitments", which is S17. That segment's soundbites are S10 to
  S13 and S15.

### F-005: Script opens on a line that refers back to a cut sentence (low)

- **Observed:** The hook segment opens on S2, which starts with "You heard that right"
  (हजुरले सही सुन्नुभयो), and the note says "Open directly on this line". S1, the line it
  refers to, is not used anywhere in the script.
- **Evidence:** `script.segments[0].soundbites[0].ref` is S2 and
  `segments[0].note` is as quoted. S1 is cited only in `hooks[3].evidence`.
- **Fix direction:** add prompt guidance that a soundbite which refers back needs the
  line it refers to, or an editor note saying so.
- **Seen again: video_014 (milder):** `segments[0]` opens on S6, which begins with "तर"
  ("but"). The subtitle quietly drops the word.

### F-006: Caption and hook style deviations (low)

- **Observed:**
  - The LinkedIn caption is one block, although the instructions ask for short
    paragraphs.
  - It speaks of the organisation in the third person ("Cleary Consulting Group says it
    supported…"), although the organisation posts it.
  - The hook labelled `curiosity` is a plain statement.
- **Evidence:** `captions[2].text` is 381 characters with 0 line breaks.
  `hooks[3].style` is "curiosity".
- **Fix direction:** prompt the model to write in the organisation's voice ("we") and
  to break LinkedIn captions into paragraphs. No code change is needed for hook styles.
- **video_014:** the LinkedIn issues did not recur. `captions[0].text` has a paragraph
  break and speaks to the reader. New evidence: the tone "warm, encouraging" is only
  lightly applied. Most of the copy is cautionary (refusals, careful documentation),
  which the material justifies, but nothing in it encourages the reader.

### F-007: Unflagged inferences beyond the transcript (low)

- **Observed:** The subtitle expands the transcript's "CO" to "CoE", which is plausible
  but not what was said. The broad hashtags `studyabroad` and `internationalstudents`
  assume study abroad, but the material never names a destination.
- **Evidence:** `script.segments[2].subtitle` ("…their master's CoE…"), against S5
  ("Masters को CO निकालेर"). `hashtags.broad`.
- **Fix direction:** instruct the model to keep unclear terms as heard. A reviewer
  should confirm these before posting.

### F-008: `dropped` counts and the raw answer are not kept (low)

- **Observed:** finalize prints `dropped` but does not save it. The job folder, which
  holds `results/answer.json`, is deleted. The session's "none dropped" therefore
  cannot be checked after the run.
- **Evidence:** `copy.json` and `metadata.json` have no `dropped` key, and
  `work/generate-copy/` is empty.
- **Fix direction:** save `dropped` in `copy.json` (and in `metadata.json`).
- **Seen again: video_014:** "none dropped" again cannot be checked.

### F-009: Input issue: every topic tag cites S1 (low, tag-topics)

- **Observed:** All 7 topic tags cite S1 as their evidence, including the entity
  `cleary-consulting-group`, which is spoken only in S6. This belongs to
  `tag-topics`, but it feeds generate-copy.
- **Evidence:** in `output/tag-topics/video_003-da5b3b50/topics.json`,
  `tags[*].evidence[0].ref` is "S1" for every tag.
- **Fix direction:** look into this in a tag-topics test, possibly as an evidence
  check in its finalize.
- **video_014:** not repeated. The topic evidence varies (S6, S1, S19, …). However, the
  `entity` `tilottama-consulting-group` carries the F-011 name problem forward.

### F-010: Test session skipped required parts of the "ready" message (high, conduct; raised from medium after video_014)

- **Observed:**
  - The ready message did not give `inputs` (transcript, visual tags, topic tags) or
    `request` (platforms, language, translation), which SKILL.md step 1 requires.
    Going by the pasted report, it did not name the model either.
  - It also said "I'm proceeding since there are no warnings". SKILL.md does not use
    warnings as a gate; the paid step is gated by the `ask` permission.
- **Evidence:** In the session report, SKILL.md step 1 lists the `"status": "ready"`
  items. `.claude/settings.json` line 26 lists `generate.py` under `ask`.
- **Fix direction:** have prepare print a ready-made one-line summary that the skill
  quotes word for word, or make step 1 a fixed checklist. State that warnings are told
  to the user and are not a go/no-go rule.
- **Seen again: video_014 (worse):** the ready message was only "one paid request to
  gpt-6-luna for LinkedIn and TikTok copy". It left out `inputs`, the
  `estimated_input_tokens`, the `reasoning_effort` and the request's tone and brief.
  The brief left out matters here: it conflicts with the material (F-012), and the
  user had no chance to notice before paying. Raised to high because it happened in
  two runs out of two.
- **Seen again:** run 6 (force). The ready message gave the model, effort and replaced time, but no inputs, token estimate or warnings. That makes all 3 paid runs.
- **Seen again: draft-report (both months):** the session paraphrased the ready message
  as "Prepare found 8 posts … with cost and org details noted". `/draft-report` SKILL.md
  step 1 asks for every `summary` line word for word, as a list. For September, the
  lines left out were the ones that mattered: "Incomplete data: P4 (tiktok, Partial)",
  "Next-month plan: none (the list stays empty)" and "Earlier months: none". The
  generate-copy exception the user accepted does not cover this skill, which kept the
  word-for-word rule. Either enforce the rule (prepare's output already has `summary`
  ready to quote), or accept the paraphrase here too and change the skill to match.
- **Seen again: draft-report runs 3 and 4 (after the skill change):** both ready
  messages were paraphrased again, for example "October 2026 has 8 posts, 4 … all with
  complete data … about 3,500 input tokens". The skill now says to copy `summary_text`
  unchanged into a fenced text block and put nothing in its place, and the session did
  neither. Wording the rule more strongly in SKILL.md has not changed the behaviour in
  4 runs out of 4. What is left is to accept the paraphrase, as for generate-copy, or to
  show `summary_text` without relying on the session, for example by having prepare
  print only that block for the user.

### F-011: Organisation name mistranscribed, repeated in all of the copy (high, confirmed)

- **Observed:** The copy names the organisation "Tilottama Consulting Group" in 7 places:
  - the closing overlay text and subtitle;
  - both captions and both calls to action;
  - the brand hashtag `tilottamaconsultinggroup`.

  The name comes only from the transcript's "तिलोत्तमा Consulting Group" in S19. The
  frame text, however, reads "TILICHO", "tilicho.com" (variant "tilicho.com.au") and
  "…m at Tilicho Consulting Group.". All three were read as `partial`, so
  `lib/material.py` never sent them; only "CONSULTING GROUP" (T3) was sent. The
  organisation is most likely Tilicho, which makes the brand hashtag unsupported.
- **Evidence:**
  - in `copy.json`: `captions[*].text`, `captions[*].call_to_action`,
    `script.segments[3].overlay_text` and `hashtags.brand`;
  - in `tags.json`: the `on_screen_text` items with `legibility` "partial" that
    contain "Tilicho";
  - in `topics.json`: `entity` `tilottama-consulting-group`.
- **Confirmed by the user (2026-11-05):** the organisation is **Tilicho** (Tilicho
  Consulting Group). Tilottama is the municipality its address is in. ElevenLabs heard
  "Tilicho" as the better-known place name, and both downstream processors took the
  transcript's spelling: tag-topics (entity `tilottama-consulting-group`, which is now
  also in the topic library) and generate-copy (6 mentions plus the hashtag). The
  copy for video_014 and its topic tags are wrong as saved.
- **Cause chain:** transcribe (mishearing) → `lib/material.py` sends no `partial`
  on-screen text, so the correct spelling never reaches the model → no check in
  either finalize.
- **Fix direction:**
  - Treat organisation names heard only in speech as needing confirmation. Add a
    check, or put it in `checks`, when a brand name or hashtag does not appear in
    any on-screen text, including partial text.
  - Consider sending partial text marked "unconfirmed" so the model can flag a
    conflict rather than pick one name.
  - Mention name confirmation in the SKILL's report step.
  - Strongest fix: each folder holds one organisation (CLAUDE.md), so give that
    organisation's own names (name, website, handles) to tag-topics and
    generate-copy, and have finalize check brand names and hashtags against them.
    A brief that names the organisation would also help.
  - Tag-topics needs the same fix (its entity is wrong too). Re-running video_014's
    topics and copy after the fix costs 2 paid requests.

### F-012: Brief conflicts with the material; the departure is not reported (medium)

- **Observed:** The brief asks to promote "student visa counselling", but the video is
  about visitor visas for parents. The model rightly wrote about the material and
  turned the brief into "visitor visa counselling", inventing no student-visa content.
  Nothing tells the user that the brief was not followed: `missing`, `checks` and
  `warnings` are all empty, and the session reported none.
- **Evidence:** `options.brief`; `script.title` ("Planning a Visitor Visa
  Application"); `captions[*].call_to_action` ("…about visitor visa counselling");
  `topics.json` `topic` (all visitor-visa). "student" appears in `copy.json` only
  inside `options.brief`.
- **Fix direction:** add a `brief_notes` (or similar) field to the schema, where the
  model says which parts of the brief the material could not support. Surface it in
  `checks`, `copy.md` "Needs attention" and the SKILL report.

### F-013: Soundbites can be sentence fragments cut at fixed 15 s part boundaries (low)

- **Observed:** The transcript was cut into fixed 15 s parts (`options.part_seconds` 15),
  so some S sentences are fragments. S18 ("visitor visa apply गर्दै हुनुहुन्छ") opens
  the call-to-action segment as a fragment. S5 and S14 are single words, and S20 runs
  on into S21. "sentence N" is numbered within each part, which makes fragments harder
  to find.
- **Evidence:** `script.segments[3].soundbites[0].ref` is S18. Part boundaries in
  `transcript.json` are `parts[4..6]`.
- **Fix direction:** in `lib/material.py`, join the trailing fragment of one part to
  the first sentence of the next (keeping both times), or have the model told that
  soundbites starting or ending at a part boundary may be cut.

### F-014: Speaker label leaks into soundbite text (low)

- **Observed:** On the diarized transcript, the first sentence of each part keeps the
  "SPEAKER 0:" prefix in its `text`. `copy.md` quotes it as part of the soundbite.
- **Evidence:** `script.segments[*].soundbites[*].text` for S1, S6, S7, S9, S11, S15,
  S19 and S21, against `transcript.json` `options.diarize` true.
- **Fix direction:** strip the speaker label from sentence text in
  `lib/material.py` `speech_section` and record the speaker separately.

### F-015: Keeping names out relies only on the prompt (low)

- **Observed:** A clearly read person's name (T5) and that person's job title (T4)
  were sent as on-screen text. The model correctly left the name out, but finalize has
  no check of its own.
- **Evidence:** in `tags.json`, `on_screen_text` T5 has `legibility` "clear". It does
  not appear in `copy.json`.
- **Fix direction:** have finalize flag in `checks` any on-screen text that appears
  word for word in the copy, so a reviewer looks at it. Also consider leaving out
  on-screen text that looks like a name caption.

### F-016: `different_options` does not say which option changed (low)

- **Observed:** In run 3 the saved copy differs in tone ("warm, encouraging" vs
  "playful") and also in brief: the brief was not repeated, so it became null. The
  session could only say "another set of platforms, language, translation, tone or
  brief", so the user cannot tell that forcing would also drop the brief.
- **Evidence:** in `processors/generate-copy/prepare.py`, `previous_status` returns only
  the status string. The run 3 output named no field.
- **Fix direction:** have prepare print the changed fields (saved vs requested values)
  with `different_options`, and have the skill quote them. In particular, say when a
  saved brief or tone would be dropped.

### F-017: Script segments dropped because their soundbite references were not recognised (high)

- **Observed:** In run 7 the model gave 5 segments; 4 were dropped as citing nothing
  that was sent, leaving one call-to-action with only on-screen text T1. Hooks and
  captions in the same answer cite S refs normally, and video_003 (run 8, no cut
  sentences) kept all 4 segments.
- **Likely cause (not provable):** video_014 has 12 sentences cut at part edges, and
  the new rule says never to open or close on one. The model probably joined fragments
  as ranges ("S6-S7") or similar, which finalize matched only as exact strings. The raw
  answer was deleted with the job, so the references could not be seen (F-019).
- **Evidence:** in `copy.json`, `dropped.segments` is 4 and `script.segments` has 1
  entry with empty `soundbites`.

### F-018: A script without any soundbite counted as complete (medium)

- **Observed:** In run 7, `complete` was true although the talking-head video's script
  used none of its speech.
- **Evidence:** in `copy.json`, `missing` is [] and every segment's `soundbites` is
  empty.

### F-019: Dropped items leave no trace (low)

- **Observed:** Only counts of dropped hooks and segments were saved, and the job folder
  holding the answer is deleted, so a drop like F-017 cannot be diagnosed.

### F-020: Paragraphs come back as one item, so sentence citations and length checks do nothing (high, draft-report, both months)

- **Observed:**
  - The model put several sentences into one `SENTENCE` item. In October every
    paragraph and the top post is one item holding 2 or 3 sentences. In September,
    what_happened is 2 items holding 3 sentences, and what_worked is 2 items holding 4.
  - October's what_worked item has 3 sentences and cites P1, P2 and P6 together, so
    nothing shows which sentence rests on which post. `report.md` still says "Every
    sentence lists the data it rests on".
  - `length_checks` counts items, not sentences, so the 4-sentence limit for paragraphs
    and the 2-sentence limit for the top post never apply.
  - `checks` point to "What happened, sentence 1" when that is the whole paragraph.
  - The `sentences` count the skill reports is really the item count (the session's
    "1 each").
- **Evidence:** in `output/draft-report/2026-10-d6af7a55/report.json`,
  `summary.what_happened[0].text` holds three sentences ("…13,300 more than in
  September. Your videos were played … You gained 214 …") under 4 refs. In draft.py,
  `SENTENCE = {text, refs}` has no description, and `INSTRUCTIONS` asks for references
  "for every sentence", but never says one sentence per item.
- **Why it matters:** the guarantee that the draft can be traced sentence by sentence,
  and the paragraph-length rule, are both lost without any sign. A paragraph of 10
  sentences would also pass.
- **Fix direction:** say in the instructions (and a schema `description`) that there is
  one sentence per array item. In finalize, split each item's text at sentence ends,
  then count and check per sentence. Add a check (or split the item) when an item holds
  more than one sentence. Name parts in checks by their real sentence.

### F-021: "because" check fires on the explanation of held-back data (low, draft-report, both months)

- **Observed:** the only check in October, and the first one in September, is a false
  positive:
  - October: "Your videos were played 54,400 times; we can't compare that with
    September because its TikTok play data was incomplete."
  - September: "Your videos were played 28,600 times, but this month's number is
    incomplete because one TikTok post's plays are missing."

  Neither sentence gives a cause for how the posts performed. Each says why a number is
  incomplete or held back, which the instructions ask for ("say its numbers are
  incomplete") and the input footnote states.
- **Why it matters:** when a clean draft's only check is a false alarm, strategists
  learn to skip checks.
- **Fix direction:** let `CAUSAL` ignore a clause that mentions incomplete, missing,
  not shown, held back or a Partial or Stale snapshot. Or give the model a fixed
  wording ("…; the change from September is not shown, as its TikTok data is
  incomplete") and tell it not to write "because" at all.

### F-022: Internal and marketing terms reach the client text without a check (medium, draft-report, mostly October)

- **Observed:**
  - October what_worked: "was the engine's highest-engagement pick". The client has
    never heard of the report engine, and "engagement" is the jargon the instructions
    replace with "liked, commented on, shared or saved".
  - October what_didn't_land: "the lowest reach among this month's complete post
    snapshots". All 8 October posts are Full, so "complete" suggests that some were not,
    and "snapshots" is a term from the data model.
  - September: "complete viewing data", the headline's "September reach was …", and the
    top post's "a client's student visa grant". In this report "you" is the client, so a
    reader cannot tell whose client is meant.
- **Evidence:** in finalize.py, `JARGON` covers impressions, CTR, CPC, KPI, conversion,
  funnel and video completions. It has no entry for engagement (except as part of
  "engagement rate", which is not in the regex), snapshot, engine or pick.
- **Fix direction:** add engagement, snapshot(s), engine and data quality to `JARGON`.
  In the instructions, never name the report engine or snapshots, and never qualify a
  ranking as "complete" when every post is Full. Call the organisation's own customers
  "a student" or "one of your students", not "a client".
- **Seen again: September run 4 (post codes):** all three highlights write the codes
  into the client text: "P1 reached more people than any other post with complete data;
  P4 is left out because its data is incomplete.", "P2 had the most likes, comments,
  shares or saves…" and "P2 had the highest share of viewers watching to the end…". The
  client has never seen P1 to P6. The instructions ban "references", but `INTERNAL`
  does not match a code. October names its posts by subject ("the student-visa advice
  video") and is clean.
  - **Fix direction:** flag any `REF_PATTERN` match (P3, N2, M:reach, PL:tiktok) in a
    line the client reads. Tell the model to name a post by its subject or platform and
    never by its code.

### F-023: A ranking that includes a Partial post is not flagged when that post is not cited (medium, draft-report, September)

- **Observed:** the highest-engagement highlight says "The visitor-visa advice video
  received the most likes, comments, shares and saves among your posts." P4's shares
  and saves are not recorded, so "most shares and saves among your posts" cannot be
  known. what_worked has the right qualifier ("among the posts with complete data"),
  but the highlight leaves it out. No check fired, because the highlight cites only P2.
- **Evidence:** in `2026-09.json`, `posts[3].snapshot.shares_count` and `saves_count`
  are null. `partial_checks` looks only at the refs a line cites.
- **Why it matters:** this breaks the agreed rule that Partial posts are never ranked
  or compared on, and it is the case the rule exists for.
- **Fix direction:** when any post is Partial or Stale, flag ranking words (most,
  highest, lowest, longest, best, top) in a line that has no qualifier such as
  "complete data". Or treat such a line as resting on every post with incomplete data.
  Also tell the model to repeat the qualifier in highlights.

### F-024: The same video posted twice is described as "two videos" sharing a hook (low, draft-report, October)

- **Observed:** what_worked ends: "The two videos about financial documents used the
  same question as their opening hook." P1 (Instagram) and P6 (YouTube) are one video,
  `video_007.MOV` with `hook_used` 1, posted twice. Presented as a pattern, it is only
  true because they are the same video, and it tells the reader nothing about which
  hooks hold viewers. The hook itself is never quoted. September does this well: "Its
  opening asked whether viewers were planning a visitor visa application for their
  parents."
- **Evidence:** in `2026-10.json`, `posts[0]` and `posts[5]` share `source_file` and
  `hook_used`. `build_context` never says that two posts come from the same video.
- **Fix direction:** in prepare, mark a post made from the same video as an earlier one
  ("same video as P1"). Instruct that a hook pattern needs posts from different videos,
  and that the observation should quote or paraphrase the hook.
- **Seen again: October run 5 (regressed after run 3):** what worked s3: "The two posts
  about student visa applications used the same question as their opening hook, and the
  video on YouTube had the highest share of viewers watch to the end." (P1, P6). It says
  "posts", not "videos", so the "same video as" rule is kept in the letter, but the
  observation is still only true because they are one video, and the hook is not quoted.
  Read after s1 ("Your educational student-visa video reached the most people"), "the
  video on YouTube" reads as a second video. The model's own review note asks to check
  that they are "described as one video shared on two platforms", so it knew.
  - **Fix direction:** as above: the instructions say a hook pattern needs posts from
    different videos, which they do not yet. Finalize could flag a sentence citing two
    posts with the same source file together with "same", "both" or "two".

### F-025: Best-retention line pairs "longest" with a measure where another post led (low, draft-report, October)

- **Observed:** "The YouTube video … held viewers longest among the videos: 49% were
  still watching after 10 seconds and 41% watched to the end." P6 leads only on watching
  to the end (41% against P2's 38.2% and P1's 34.5%). After 10 seconds P1 had 52% against
  P6's 49%, and after 3 seconds 71.4% against 66.2%. Read together, the sentence
  suggests P6 led at 10 seconds as well.
- **Evidence:** the retention figures of P1, P2 and P6 in `2026-10.json`. The material
  does not say which measure the report engine ranked best retention on.
- **Fix direction:** have prepare send the measure the highlight was ranked on
  ("best_retention: P6, by share watching to the end"), and instruct the model to give
  that measure first or only.
- **Seen again: October run 3 (engagement):** "Highest result for people liking,
  commenting on, sharing or saving: the Nepali visitor-visa video." and in what worked
  s1 "the Nepali visitor-visa video had the strongest result for people liking,
  commenting on, sharing or saving". P2 leads only on engagement rate (10.23% against
  P1's 9.35%). P1 had more of every count: 820/96/214/310 likes, comments, shares and
  saves, against P2's 700/88/120/95. A reader takes "highest result" to mean the most
  likes, comments, shares and saves, which is false. The instructions ban "engagement
  rate" and give only "liked, commented on, shared or saved", so the model has no
  plain words for a rate. September is not affected, because there P2 led on both
  counts and rate.
  - **Fix direction:** as above. Prepare also says that highest_engagement is ranked
    on the share of people reached who liked, commented on, shared or saved. The
    instructions give the plain wording for it ("for the number of people it reached,
    the most people liked, commented on, shared or saved it").

### F-026: The number check matches against every number in the month, not the cited data (low, latent, draft-report)

- **Observed:** `allowed_numbers` is one flat list holding every count, percentage,
  difference, year, plan figure and footnote figure, and `unmatched` checks a line
  against all of it. Every number in these two drafts is right, but some pass only by
  chance:
  - "after 10 seconds" passes because P4 had 10 comments, not because 10 s is a data
    value;
  - "two educational videos" passes on P8's 2 comments.

  A wrong attribution would also pass. "1,900 people" is both October's P8 reach and
  LinkedIn's September reach, and 214 is both new followers and P1's shares, so a line
  saying "214 people shared it" would pass.
- **Why it matters:** the check reports success on numbers it has not really matched,
  so `complete` promises more than it checks.
- **Fix direction:** check each number first against the values of the refs that line
  cites. Report a number found only elsewhere in the month as a softer "matches other
  data than it cites" check. Allow the retention points (3 s, 10 s) and counts of cited
  posts explicitly.

### F-027: Flatter and more number-heavy than the screen-7 example (low, draft-report, both months)

- **Observed:**
  - The headlines are "Your posts reached 48,200 people, up 13,300 from September." and
    "September reach was 34,900 people, down 3,300 from August.". Neither gives
    enquiries, although the target is "48.2K reached, 27 enquiries".
  - October repeats raw counts: P2's four counts appear in what_worked and again in
    its highlight, and P1's four counts in the top post.
  - October has earlier months (July 26,100 and 12, August 38,200 and 21, September
    34,900 and 18), and its 48,200 reach and 27 enquiries are the highest of all four.
    The draft does not use them, so "your highest reach since July" is missed.
  - "you" and "we" appear, but mostly as data readouts, not warm sentences.
- **Fix direction:** in the instructions:
  - put reach and enquiries in the headline, using display forms;
  - use at most two numbers per sentence;
  - do not repeat a paragraph's counts in highlights or the top post;
  - when earlier months are given, use them for one comparison where they support it.

  No code change is needed.
- **Seen again: runs 3 and 4 (partly fixed):** both headlines now carry reach and
  enquiries ("October reached 48,200 people and brought 27 enquiries", with no full
  stop). September repeats no counts. October is given earlier months again (July
  26,100/12, August 38,200/21, September 34,900/18), and 48,200 and 27 are the highest
  of the four, but no line uses them, although the instructions now say to. 15,400
  appears in both the top post and the reach highlight. The text still reads as data,
  for example the top post's "was liked, commented on, shared or saved", which says
  nothing.
- **Seen again: runs 5 and 6:** October's headline "You reached 48,200 people, up from
  September, and received 27 enquiries." and every other line still ignore the earlier
  months, the third October run in a row. The instruction says "use them where they add
  something", which leaves it optional. 15,400 now appears three times (what worked s1,
  top post s2, reach highlight), and "the most likes, comments, shares and saves" twice.
  September's top post s2 gives four counts in one sentence ("liked it 310 times,
  commented 25 times, shared it 30 times and saved it 22 times"); the "at most two
  numbers per sentence" direction was not adopted.
  - **Fix direction:** say "when EARLIER MONTHS show this month's reach or enquiries is
    the highest or lowest of them, the headline or what happened says so"; and "the top
    post and highlights do not repeat a number or ranking the paragraphs give".

### F-028: A ranking is given to the wrong post, and no check can catch it (high, draft-report, September run 4)

- **Observed:** what worked sentence 1 says the visitor-visa video (P2) "reached more
  people than any other post with complete data". P2 reached 8,700. P1 reached 9,900
  and is Full. The same report contradicts itself: the top post says P1 "reached 9,900
  people" as the highest-reach post, and so does the reach highlight. Run 2 had this
  right ("The highest-reach post was also an Instagram video, about a student visa
  grant").
- **Evidence:** `2026-09.json` `posts[0].snapshot.reach_count` 9900 and
  `posts[1].snapshot.reach_count` 8700; `highlights.highest_reach` is ci-2609-01. The
  sentence cites P2, P4 and P1, so it cites the post that really led. The sentence has
  no number, so `number_checks` and `cited_number_checks` (F-026) do not look at it.
  The three checks that do fire on it (F-030, and the Partial and ranking checks) are
  about other things, and 10 false alarms surround them (F-029).
- **Why it matters:** this is a false statement in the client's report about which
  post did best. A strategist who trusts the checks has nothing pointing to it.
- **Fix direction:**
  - Prepare sends each post's rank on reach, engagement and retention among the
    complete posts ("P1: 1st reach; P2: 2nd reach, 1st engagement…").
  - Finalize checks a ranking word together with a measure ("reached the most / more
    than any", "most liked …", "watched to the end") against the leader of that
    measure. A sentence that gives the top spot to a post other than the leader is
    flagged by name.
  - The instructions ask for one claim per sentence, so a ranking is not attached to a
    second post as a side clause.

### F-029: Partial checks fire on lines that leave the post out, and split sentences inherit them, so false alarms bury the real one (medium, draft-report, September run 4)

- **Observed:** September has 15 checks, and 10 of them are false alarms. 8 of the 9
  "rests on P4, whose data is Partial" checks are on lines that already say P4 is
  incomplete and left out, or that inherited P4 from the item they were split from. One
  of the 2 ranking checks ("fewest") is on a sentence that begins "Among posts with
  complete data". Only what worked s1 really ranks against P4. The table under "Re-test
  (runs 3 and 4)" lists each check.
- **Evidence:** in `finalize.py`:
  - `partial_checks` fires on any line that cites a Partial or Stale post. It has no
    `DATA_GAP` exemption, although `wording_checks` and `ranking_checks` have one.
  - `clean_sentences` gives every split sentence all of the item's `evidence`. The
    model cites P4 on an item so that its second sentence can leave P4 out, and the
    first sentence then "rests on P4" too (what worked, didn't land, top post).
  - `ranking_checks` looks at each split sentence alone, so the "left out" clause in
    s2 does not cover the ranking in s1. "with complete data" is not in `DATA_GAP`.
  - The highlights cite P4 only to say that it is excluded, as the instructions ask.
- **Why it matters:** the instructions now make the model cite and exclude Partial
  posts, and every time it does so correctly, the checks fire. A strategist facing 15
  checks in which 2 of 3 are wrong will stop reading them, and the false claim in F-028
  sits among them.
- **Fix direction:**
  - Skip `partial_checks` for a line that matches `DATA_GAP`, as the other two checks
    do.
  - For split items, run the Partial and ranking checks on the item's whole text
    before splitting. Or keep a Partial ref only on the sentences that mention that
    post (its platform, or "incomplete").
  - Add "(with|among) (the )?(posts|videos) with complete data" to the ranking
    exemption.
  - Or give the model a separate `left_out` field for posts a line excludes, so that
    `refs` holds only the data the line rests on.

### F-030: The superlative check fires on a ranking within the month ("among the strongest posts") (low, draft-report, September run 4)

- **Observed:** "What worked, sentence 1 compares beyond last month ("strongest")" is
  raised on "…was among the strongest posts…". This compares posts within September,
  not September with earlier months, so it is not the claim `SUPERLATIVE` exists for.
  The instructions forbid calling the month "the best, strongest or worst" and do not
  forbid ranking posts.
- **Evidence:** `SUPERLATIVE` in `finalize.py` matches "strongest", "weakest" and
  "worst" alone. `RANKING` already handles rankings of posts.
- **Why it matters:** this is one more false alarm on the same sentence as F-028.
  Without earlier months, any "your strongest post" sets it off.
- **Fix direction:** match strongest, weakest and worst only next to a period word
  ("strongest month", "worst September", "the strongest yet"), and leave rankings of
  posts to `RANKING`.

### F-031: The model ignores "one sentence per item" in some runs (low, draft-report, September run 4)

- **Observed:** items against real sentences (headline, happened, worked, didn't land,
  top post):
  - October: 1/1, 3/3, 2/2, 1/1, 2/2. The rule is followed.
  - September: 1/1, 3/3, 1/2, 1/2, 1/2. Three sections each came back as one item
    holding two sentences.

  Each merged item cites the posts of both sentences: what worked P2, P4 and P1;
  didn't land P5 and P4; top post P1 and P4.
- **Evidence:** `report.json` `split`. `SENTENCE` in `draft.py` still has no schema
  `description`. The rule is one clause in `INSTRUCTIONS`, and the effort is low.
- **Why it matters:** the split keeps the counts and lengths right (F-020). It cannot
  restore which data each sentence rests on, and that is the cause of most of F-029.
- **Fix direction:** add `"description": "exactly one sentence"` to `SENTENCE.text`
  and "refs: only the data this one sentence rests on" to `refs`. Keep the split as the
  safety net, together with the F-029 change to how a split item's references are
  checked.

### F-032: September's headline no longer says the month fell (low, draft-report, September run 4)

- **Observed:** run 2's headline was "September reach was 34,900 people, down 3,300 from
  August." Run 4's is "September reached 34.9K people and brought 18 enquiries." Reach
  (-8.64%) and enquiries (-14.29%) both fell. The report card now reads as neutral or
  good, and the fall appears only in what happened. That paragraph states it plainly,
  so the report as a whole is honest.
- **Evidence:** the headline in the instructions is "the month's main takeaway with
  people reached and enquiries". The honesty rule names only what_happened.
- **Why it matters:** the headline is the line the client is most likely to read. A
  month with lower reach and fewer enquiries that does not say so in the headline
  comes close to the "flattering comparison" the honesty rule forbids.
- **Fix direction:** in the headline instruction, give the direction of change against
  last month for reach and enquiries ("34.9K reached and 18 enquiries, both down on
  August"), still within 20 words.

### F-033: The ranking order check misses the run-4 error on its real wording and refs (high, latent, draft-report)

- **Observed:** `order_checks` was replayed (free, in a scratch script) on the run-4
  sentence that F-028 is about, with the refs it really had (P2, P4, P1) and the
  September LEADERS: no check. Its test
  (`test_a_ranking_given_to_the_wrong_post_is_flagged`) passes only because the sentence
  there names one measure and cites only the wrong post. Three gaps:
  - `measures_in` returns only the engagement rate when a line has engagement wording
    ("liked, commented"), so the reach claim in the same sentence ("reached more people
    than any other post") is never checked. Run 6's what worked s1 (engagement and "the
    most viewers watched it to the end") is checked on engagement only; it is right, so
    nothing was missed this time.
  - A line passes when any cited Full post is the leader (`posts & set(lead[...])`). Run
    4 cited P1, the real leader, next to P2, which it ranked first. Replay: "It reached
    more people than any other post with complete data." flags P2 alone, but not P2 with
    P1.
  - `MOST` and `FEWEST` do not know "widest audience", "topped", "came first", "led the
    month" or "no post was seen by more people"; none of these is checked.
- **Evidence:** `processors/draft-report/finalize.py` `measures_in` (returns early on
  `ENGAGEMENT`) and `order_checks`; `history/20261105-115326/report.json` what worked
  s1, evidence P2, P4, P1.
- **Why it matters:** a ranking given to the wrong post is the one error type that has
  no number for the number checks to catch, and it reached a draft in run 4. The fix
  status said the run-4 claim "is flagged in a replay", but on the real data it is not.
  Runs 5 and 6 had no wrong ranking, so they pass because of LEADERS, not because of
  the check.
- **Fix direction:**
  - `measures_in` returns every measure a line names (engagement, retention and counts
    together), without counting "liked, commented on, shared or saved" in the
    engagement wording as the likes, comments, shares and saves counts.
  - When a ranking line cites the leader and other Full posts, flag it ("cites P1 and
    P2; check which post it puts first"), or have the model return each ranking in a
    structured field (post, measure, most or fewest) and check that against LEADERS.
  - Add led, topped, came first, widest and "no other post … more" to the ranking words.
  - Add a test with the run-4 sentence and refs P2, P4, P1.

- **Re-test of the fix (replay, 2026-11-06):** the current `order_checks`,
  `ranking_checks` and `partial_checks` were replayed (free; scratch script) on runs 3
  to 6.
  - Run 4: the F-028 sentence now gets "What worked, sentence 1 ranks posts and cites
    P1, P2; among posts with complete data the first is P2 on engagement rate; P1 on
    people reached: make sure that is the post it puts first." This is a prompt to check,
    not a verdict, but it names P1 as the reach leader, so a strategist reading it finds
    the error. `measures_in` now gives engagement rate and reach for that line.
  - Run 3: the engagement highlight ("Highest result for people liking, commenting on,
    sharing or saving") now gets "puts P2 first on comments, but P1 is first", which is
    real (F-025).
  - Runs 5 and 6: September's checks are the same 4 real ones plus a shared-leader check
    on what worked s1; October gets 3 new checks, all false alarms (F-035).
  - Status: partly fixed. The error is caught now, but at the cost of the false alarms
    in F-035.
  - **Second replay (after the F-035 fix):** per run, the order and ranking checks:
    - Run 4: order "make sure" on what worked s1 (names P1 for reach): real, the F-028
      error. No ranking check: "with complete data" in the reach clause now exempts the
      whole line, so its unqualified "more than any other post" on likes, comments,
      shares or saves (P4 has no shares or saves) goes unflagged (latent). A Partial
      check on the top post s1 is an artefact of the replay: run 4's file predates the
      `item` field, so its split sentences could not be grouped.
    - Run 6: order "make sure" on what worked s1: false (the line puts P2 first,
      correctly; P1 is cited for "Instagram videos stood out"). Ranking on s1 and s2,
      and Partial on s1 and s2: real, as in the run-6 review.
    - Run 5: order "make sure" on what worked s3: false (it puts P6 first, correctly).
      The two engagement-rate checks are gone.
    - Run 3: order "make sure" on what worked s1 (P1 first on comments) and "the highest
      engagement highlight puts P2 first on comments, but P1 is first": both real (the
      F-025 wording "strongest result for people liking, commenting on…").
    - Status: fixed. The 2 prompts on correct lines are the remaining noise (F-035).

### F-034: October's "What didn't land" comes back as one sentence (low, draft-report, October runs 3 and 5)

- **Observed:** all three October runs give what didn't land as one item; run 1 packed
  two sentences into it, runs 3 and 5 give one sentence, and the length check fires
  rightly each time. Run 5: "Your intake-dates carousel reached the fewest people, with
  1,900, and had the fewest likes, comments, shares and saves." It is correct (P8 is last
  on reach and every count), but LEADERS also gives a second quiet spot that goes unused:
  P3, the reposted Instagram promo, is last on all three retention measures (48%,
  30.1%, 18% to the end). September, where things fell, gets 2 sentences.
- **Evidence:** `draft.py` `INSTRUCTIONS` gives "2 to 4 sentences each" once for all
  three paragraphs, then gives what_did_not_land a single job: "the weakest result or
  quietest spot". In a month where every total and platform rose, the model writes the
  one weakest post and stops.
- **Why it matters:** the strategist has to write the paragraph's second sentence every
  October-like month; screen 7 shows two.
- **Fix direction:** in the instruction for what_did_not_land, ask for 2 to 4 sentences:
  the weakest result, then a second quiet spot from LEADERS (another measure or post);
  when nothing fell against last month, one of them may say so. Keep the length check.

### F-035: The F-033 fix reads "share of viewers … to the end" as engagement and flags correct retention lines (medium, draft-report, October run 5 by replay)

- **Observed:** with the current `finalize.py`, October run 5 (which had one correct
  check) would get 3 more, and none of them is real:
  - "What worked, sentence 3 puts P1, P6 first on engagement rate, but P2 is first among
    posts with complete data; check it." The line ("…the video on YouTube had the
    highest share of viewers watch to the end") ranks on watching to the end, where P6
    does lead (41%).
  - "The best retention highlight puts P6 first on engagement rate, but P2 is first…".
    This flags as wrong the highlight line "Your student-visa video on YouTube had the
    highest share of viewers watch to the end: 41%", which is right and worded as the
    instructions ask.
  - "What worked, sentence 3 ranks posts and cites P1, P6; … the first is P6 on watched
    to the end: make sure that is the post it puts first." The line does put P6 first.
    September run 6 gets the same shared-leader check on what worked s1, which puts P2
    first, as it should; P1 is cited only for the opening "Your English-language
    Instagram videos stood out".
- **Evidence:** `ENGAGEMENT` now matches `share of (the )?(people|viewers)`, so
  `measures_in` adds `true_engagement_rate` to any retention line written as a share of
  viewers, and P2, not P6, leads the engagement rate. In September the same mistake hides
  by luck: P2 leads both the engagement rate and watching to the end. The shared-leader
  check fires on every correct line that also cites a supporting post.
- **Why it matters:** the first two say a correct line is wrong ("check it"), in a draft
  whose wording follows the instructions. They are the same kind of false alarm F-029
  removed, and they would sit next to the one real check.
- **Fix direction:**
  - Match `share of viewers` as engagement only when "who liked, commented …" follows,
    or look for the retention wording first and leave such a line out of engagement.
  - Add tests: October's best-retention highlight and what worked s3 raise no order
    check.
  - For the shared-leader check, either accept it as a prompt (state in the skill that
    it asks for a check, not a fix), or ask the model to cite only the ranked post on a
    line that ranks, and put the context post in a separate sentence.
- **Second replay (after the fix):** the engagement-rate false alarms are gone in runs 3
  to 6; October's best-retention highlight and what worked s3 are read as watching to
  the end only. What remains is the shared-leader "make sure" prompt on 2 correct lines
  (October what worked s3, September what worked s1). Status: partly fixed; the fix
  direction for the prompt stands.

### F-036: Visual-tag comparisons use only the first 8 tags, cut alphabetically, so the talking-head video_003 counts as "without speaking-to-camera" (high, draft-insights, October)

- **Observed:** G1, G9 and G15 compare "videos showing person, speaking-to-camera and
  text-on-screen" (P2, P6, P7, P11: video_014 and video_007) with "videos without it"
  (P1, P8: video_003). G1 gives engagement 8.17% vs 3.47%, 2.4×. But video_003 is a
  talking-head video. Run 1 and F-001 found `V:speaking-to-camera` in its `tags.json`,
  spanning the whole video (`[[0, 48.167]]`, 13 of 15 tags whole-video). T1's second
  hypothesis ("A person speaking to camera with text on screen may have helped the
  video connect…", G1, P7) and T1's brief ("…with a person speaking to camera and text
  on screen…") rest on this contrast. All three videos in the window are talking-head
  videos, so the request asks for nothing new.
- **Evidence:**
  - `tag-visuals/finalize.py:347` sorts tags by frame count, then by label.
  - `prepare.py:92` sets `MAX_VISUAL_TAGS = 8`.
  - `prepare.py:359` keeps the first 8 tags.
  - `prepare.py:383-384` groups posts by those 8 tags only.
  - In a one-shot video most tags tie on frames, so the cut is alphabetical. P1 and P8
    show exactly "blinds, certificate, chair, desk, glasses, keyboard, microphone,
    office", which all sort before "person" and "speaking-to-camera".
  - The other two lists are alphabetical too, so G7 and G23 (display, standing, suit) and
    G18, G22 and G24 (sitting) may be the same artefact: 8 of the 24 comparisons.
  - Nothing in finalize can see this. The numbers are right, and the group is wrong.
- **Why it matters:** a hypothesis, a request brief and part of the card's "this format"
  rest on a difference that probably does not exist. It reads as solid evidence (2.4×,
  the largest gap in the list).
- **Fix direction (proposal):**
  - Group posts on every tag the video has, or on every tag seen in at least half the
    frames. Keep the 8-tag cap only for the list shown to the model.
  - Break ties by `seconds`, not by label.
  - Add a prepare test in which a tag that sorts 9th alphabetically among tied tags
    still puts its video in the group.

### F-037: Every request asks for 1 item; T3 answers 8 open slots with 1 photo (medium, draft-insights, October)

- **Observed:** all three requests have `quantity` 1: "1 more educational video", "1
  educational video with a question opening" and "1 educational Instagram post"
  (`photo`). The allowed values are 1, 2 and 3. T3's trigger is "8 of the 16 posts …
  were published; 8 behind", and its request fills 1 of those 8. The Pulse card asks for
  "two more this month" ("Send us 2 more stories").
- **Evidence:**
  - The instruction in `draft.py` asks for "quantity (the smallest the schema allows that
    would test the hypothesis)". The schema allows 1, so at low effort the model reads it
    as "1". The examples in the same instruction ("2 more success-story videos", "Send us
    two more this month", "Send us 2 more stories") and the design's example result
    (`"quantity": 2`, "Send us 2 more videos") point the other way.
  - A single new post cannot test a hypothesis that rests on group averages (6 vs 7
    posts).
  - Latent: design decision 7 says the quantities are "capped by the open quota slots".
    `prepare.py:750` caps them by `monthly_posts` (16) instead, so with 0 or 1 open slots
    the model is still offered 3.
  - T3's `photo` is not backed by any comparison. `GROUPS` has pillar, platform,
    language, hook and visual, but no format. Most of G2's educational average comes from
    videos: P2, P6, P7 and P11 have 7.55% to 10.23%, against 3.97% and 4.87% for the
    photo posts P3 and P9. G4's Instagram reach is mostly videos too.
- **Why it matters:** the strategist has to raise every quantity by hand. For the pace
  trigger, the insight does not do what the instruction asks ("so the agency can fill
  the open slots").
- **Fix direction (proposal):**
  - Replace "the smallest the schema allows" with what the test needs: at least 2, so a
    result rests on more than one post. For the pace trigger, ask for as many as the
    open slots allow, up to the cap.
  - Cap the quantities by `monthly_posts - published` when the pace trigger fires, as
    the design says.
  - Add a format comparison (video vs photo post), so the category can cite evidence.

### F-038: T1 and T2 ask for the same video, and each request mixes its hypotheses, so neither result can confirm or refute one (medium, draft-insights, October)

- **Observed:** the two briefs are one ask, an educational video about student visa
  applications that opens with a question:
  - T1: "Send a short educational video with a person speaking to camera and text on
    screen, using a clear opening question about student visa applications."
  - T2: "Send a short educational video that opens with a clear question for students or
    parents about student visa applications."

  Each request also bundles both of its hypotheses: T2's question opening (H1, G17) and
  educational pillar (H2, G13), and T1's pillar (H1) and presentation (H2). If the new
  video holds viewers, nothing says which hypothesis it supports.
  - T1's own post P7 opened with a curiosity hook ("Visitor visa refusals can hinge on a
    factor applicants may overlook"), not a question. "To try this format again" (T1
    card) therefore asks for something the flagged post did not do. No comparison in T1's
    evidence (G1, G2, P2, P6, P7) is about hooks.
  - T2's flagged post is a Promo success-story video (P8, statement hook), but the
    request switches to an educational video. The question opening is never tried on the
    kind of video that lost viewers.
- **Evidence:** the instruction asks for one action per trigger "and the references it
  rests on". Nothing asks which hypothesis the request tests, or asks the requests to
  differ, and finalize compares no requests with each other.
- **Why it matters:** the client gets two cards ("Send us a video") for one video. The
  "test" the design promises (decision 6) cannot be read from the result.
- **Fix direction (proposal):**
  - Have each request name the one hypothesis it tests (a `tests` field) and change only
    that: for T2 H1, a promo or success-story video that opens with a question.
  - Ask that requests in one month differ in category or content, or merge them.
  - Have finalize note two requests with the same category whose briefs share most of
    their words.

### F-039: Three of six tests name no measure (low, draft-insights, October)

- **Observed:** these say "perform(s) more strongly" / "no better", with no measure,
  post count or period:
  - T1 H1: "A new educational post performs more strongly than comparable posts in other
    pillars." Its refute_if says "New educational posts…", which switches to the plural.
  - T1 H2: "New videos using this presentation style perform more strongly than videos
    without it."
  - T3 H1: "New educational posts perform more strongly than posts in other pillars."

  T2's two tests and T3 H2 name their measure ("still watching after 3 seconds", "reach
  more people").
- **Evidence:** the instruction asks only for "one sentence on what result would support
  it". `insight_checks` checks only that confirm_if and refute_if are not empty.
- **Why it matters:** it is not clear whether "more strongly" means engagement or
  reach, so whoever reads the result next month can call it either way.
- **Fix direction (proposal):** ask confirm_if and refute_if to name the measure of the
  comparison the hypothesis cites, and how many new posts make the test. finalize could
  flag a test without a measure word (engag…/liked…, reach/people reached, watching).

### F-040: Comparisons count posts, not videos, and include the flagged post and its twin (medium, draft-insights, October)

- **Observed:** four hypotheses give post counts that count one video twice:
  - T1 H1 and T3 H1 cite G2's "6 educational posts". These are 4 pieces of content: P2
    and P7 are video_014, and P6 and P11 are video_007. The 7 others include P1 and P8
    (video_003).
  - T2 H2 cites G13's "4 posts in each group". These are 2 videos against 3.
  - T3 H2 cites G4's "7 Instagram posts", which include P1 and P8.

  G2 is used to explain T1, but its group holds T1's own post P7 (10.23%) and its twin
  P2 (7.55%). A third of the "educational" evidence is the flagged video itself.
  Without them the gap remains (P3, P6, P9 and P11 average about 5.9%, against 3.43%),
  but the stated 6.92% is partly the outlier explaining itself. Review note 2 flags the
  repeat generically ("repeated videos are counted as posts…"), and no hypothesis says
  it.
- **Evidence:** `prepare.py:433-434` counts videos only for the `hook` and `visual`
  kinds, so labels for pillar, platform and language say "(6 posts)" with no video
  count. The instruction asks to "say how many posts are behind it", not how many
  videos. A comparison "bears on" a trigger exactly when the trigger's post is a member
  (`prepare.py:419-423`), so every comparison cited for T1 contains P7.
- **Why it matters:** two hypotheses look as if they rest on twice as many pieces of
  content as they do. This is the same mistake as F-024, at the level of the evidence.
- **Fix direction (proposal):**
  - Give every comparison its video count (distinct `source_file`; a post without one
    counts as one), and add "includes the flagged post" / "and the same video on another
    platform" to its label when that is so.
  - Ask the model to state videos where the label gives them.

### F-041: The T1 client card claims in count words a lead that the counts contradict (medium, draft-insights, October)

- **Observed:** the T1 card finding reads "Your Nepali TikTok video was liked, commented
  on, shared or saved more often than your other recent posts." P7 had 700 likes, 88
  comments, 120 shares and 95 saves. P6, the Instagram financial-documents video, had
  more of every count: 820, 96, 214 and 310. P7 leads only as a share of the people
  reached (10.23% against 9.35%). The trigger also compares P7 with the 90-day average
  (2.2× of 4.7%), not with every other post.
- **Evidence:** the instruction offers "liked, commented on, shared or saved" as the
  people-terms wording for engagement rate, and nothing turns that into a share. The
  sentence has no number, so `number_checks` and `ratio_checks` have nothing to test,
  and checks is empty.
- **Why it matters:** this is the one sentence the client may read. A client who looks
  at the post counts will find it wrong. It is the F-025 mistake (counts and a share
  read as one) on the client card.
- **Fix direction (proposal):**
  - Give the share wording in the instruction ("a bigger share of the people who saw it
    liked, commented on, shared or saved it"), plus the trigger's own ratio, in the
    Pulse style ("2.2× your usual").
  - Have finalize flag a client line that cites an engagement-rate trigger and uses
    "more often", "more than" or "most" without "share", "of the people" or a ratio.

### F-042: T3's hypotheses do not say why the month fell behind, and their tests measure something else (medium, draft-insights, October)

- **Observed:** T3 is "8 of the 16 posts … were published; 8 behind". Both hypotheses
  suggest what to post, not why posts are missing: "Educational posts may be a useful
  way to fill open slots…" (G2), and "Instagram may be a useful channel for some open
  slots…" (G4). Their tests measure engagement and reach, not pace. The model's own
  review note 1 says "this evidence does not explain why fewer posts were published".
- **Evidence:** the instruction defines hypotheses as "1 or 2 possible reasons", and for
  the pace trigger it adds "ask for what the comparisons show works best". The material
  has nothing that bears on a shortfall (assets received, approvals, schedule). For the
  pace trigger, prepare counts a comparison as bearing on it when "a group doing better"
  (`prepare.py:423`).
- **Why it matters:** the strategist gets two "hypotheses" for a trigger that are
  content advice labelled as reasons. The design's "why it may have happened" is not
  answered, and the "not enough evidence" path (decision 10) went unused, although the
  model knew the evidence was missing.
- **Fix direction (proposal):** for `pace_behind_quota`, either ask for
  `enough_evidence: false` on the "why" with a reason, and keep the request as "what to
  fill the slots with", or rename the field for that rule ("what may work best for the
  open slots"), with tests on the measure cited. Say which in the skill and the design.

### F-043: The client cards are vaguer than the Pulse card and partly off-voice (low, draft-insights, October)

- **Observed:**
  - No card carries a number or a ratio. The Pulse card leads with "Success-story videos
    got 3.2× your average reach".
  - The findings describe one post, and the actions ask for a type without linking the
    two. T1 asks for "one more educational video to try this format again", and the
    card never says what the format is.
  - T2's "On your Instagram video, 48% of viewers were still watching after 3 seconds."
    does not say which video (the window has four Instagram videos) or how 48%
    compares.
  - T3's "You published 8 of your 16 planned October posts." puts the publishing on the
    client. The instruction says "we" for the agency, which does the publishing.
  - T3's action uses the scheduling term "open slots".
  - The buttons are generic: "Send us a video" twice and "Send us a post". The client
    sends a photo, not a post. The Pulse card has "Send us 2 more stories".
- **Evidence:** compare `Assets and Results.dc.html:243-246`. Nothing checks
  `CLIENT_TERMS` for "slot" or the agency's "we".
- **Why it matters:** the strategist rewrites each card before it can be shown. Two
  identical buttons on two cards do not say what each one adds.
- **Fix direction (proposal):** ask that the finding name the kind of post (as the
  request does) and carry the cited ratio or number when one is in the trigger or
  comparison. Ask that the button name the quantity and the kind ("Send us 2 more
  videos"), and use "we" for publishing. Add "slots" to `CLIENT_TERMS`.

### F-044: `insights.md` names only the October report as input; the token estimate ran 7% under (low, draft-insights, October)

- **Observed:** the header reads "Input: insights/2026-10.json (the anomaly rules'
  triggers) and reports/2026-10.json (the month's numbers)". The comparisons also used
  `reports/2026-09.json` (P1 to P5), which `metadata.json` `inputs.window_reports`
  records. The estimate was 4,956 input tokens and the request used 5,331, so it was
  7.6% under. draft-report's estimates run 2% to 4% over.
- **Evidence:** `finalize.py` `to_markdown` writes only `plan['inputs']['report']`.
- **Why it matters:** a reader of `insights.md` does not know that a second month's
  numbers feed the comparisons. The cost line slightly understates.
- **Fix direction (proposal):** list `window_reports` in the header. Recalibrate the
  token estimate. It already counts the instructions, the schema and the context
  (`prepare.py:790`), so the chars-per-token ratio for this mixed text is what is off.

### F-045: Both tests set their bar at the weaker side's average, below the 90-day average, so almost any new video confirms them (medium, draft-insights, October run 2)

- **Observed:**
  - T1: "This may be supported if 2 new educational videos have a higher engagement rate
    than 3.43%." 3.43% is G2's average for the other pillars, below the 90-day 4.7%.
    6 of the 8 videos in the window already beat it, including the promos P1 (3.91%)
    and P12 (5.72%). Only P5 (2.58%) and P8 (3.03%) fall under it. A promo video would
    pass too, so the test does not test the pillar.
  - T2: "…if 2 new promo videos with question openings have at least 54.67% still
    watching after 3 seconds." 54.67% is G15's average for other hook styles, below the
    58% average, and 2 of its 3 posts are the flagged video_003 itself (P8 48%, P1 52%).
    A video at 55% would "support" the question opening while still under the client's
    usual.
  - Neither test says whether "2 new videos" means each video or their average.
- **Evidence:**
  - The instruction asks for "the number to beat" without saying which number.
  - finalize lets a test use any of its G's, its trigger's or BL's numbers, and checks
    only that the number is known and that a measure word is present.
- **Why it matters:** a test that cannot fail does not tell the strategist next month
  whether the hypothesis held. Both would read as confirmed on an ordinary month.
- **Fix direction (proposal):**
  - Have prepare give each comparison the bar to beat: the higher of the 90-day average
    for that measure and the stronger side's average. Have the test cite it, and say "on
    average across the N new posts".
  - Have finalize flag a confirm_if whose number is below BL's average on the same
    measure (engagement 4.7%, still watching after 3 s 58%).

### F-046: T1's and T3's requests ask for the same educational videos; the same-request check misses it (medium, draft-insights, October run 2)

- **Observed:**
  - T1: "Send us two educational videos explaining practical visa-application guidance,
    in the same straightforward, adviser-led style as the flagged video."
  - T3: "Send us three educational videos with practical visa-application guidance so we
    can catch up with the kind of content that compared well…"
  - Both cite G2, and both are `video`. The client gets two cards for one ask, "Send 2
    more videos" and "Send 3 videos", 5 educational videos in all. The instruction says
    "Each request this month asks for something different from the others".
- **Evidence:** `same_request_checks` compares the briefs' words of 4 or more letters
  over their union. T1 and T3 share 7 of 26 (0.27), under `SAME_BRIEF` (0.5), because
  T3's brief adds a long reason. Against the shorter brief (T1, 14 words) the overlap
  is 0.5. The October replay that flagged run 1's T1 and T2 had two short briefs.
- **Why it matters:** this is the F-038 problem again, between a post trigger and the
  quota trigger. T3's 3 videos repeat T1's test, so the strategist has to merge them by
  hand.
- **Fix direction (proposal):**
  - Measure the overlap against the shorter brief, or compare what is asked for
    (category, plus the pillar or kind named: educational, promo, success-story) and the
    comparisons cited (the same G).
  - For the quota trigger, ask for something no other request asks for, or add to the
    other request's quantity and say so.

### F-047: September's quota request asks for 2 photos, which the format comparisons it was given count against (medium, draft-insights, September run 3)

- **Observed:**
  - T3 asks for `photo`, 2, "2 more educational posts", with the brief "…using a post
    type that reached more people and had a bigger share of people who engaged". It cites
    G3 and G5 (Educational, 2 posts: P2, a video, and P3, a photo).
  - G4 (video posts reached 7,300 vs 3,950, 1.8×) and G6 (engagement 4.68% vs 3.25%,
    1.4×) are both marked "bears on T3", and both favour video.
  - The educational lead comes from the video P2 (8,700 reached, 7.55%). The one
    educational photo, P3, reached 6,000 people at 3.97%, below the 4.2% average. So the
    brief's claim does not hold for photos.
  - The button "Send us 2 posts" does not name the photos.
  - October's T3 asked for video, which fits G1 and G7 (it did not cite them).
- **Evidence:**
  - The instruction says only "its category (photo, video or story)". Nothing ties the
    category to a format comparison.
  - finalize checks only that the category is one of `CATEGORIES`.
  - The F-037 fix added the comparison ("gives the category evidence"), but nothing
    makes the model use it.
- **Why it matters:** the client is asked for the kind of post the numbers rate lower,
  for the reason that it did better.
- **Fix direction (proposal):**
  - Say in the instruction that the category follows a format comparison that bears on
    the trigger.
  - Have finalize flag a request whose category is on the weaker side of a format
    comparison that bears on its trigger or that it cites.
  - For the quota trigger, the category could be set in code from that comparison.

### F-048: Client cards say "engagement rate" whenever they give an engagement number (medium, draft-insights, runs 2 and 3)

- **Observed:**
  - October T1: "Your educational TikTok video had a 10.23% engagement rate, 2.2× your
    usual 4.7%."
  - September T3: "Your educational posts reached 1.5× as many people and had a 1.9×
    engagement rate as posts in other pillars."
  - Both checks are right: the instruction lists engagement rate as a term the client
    never reads. Every card finding about engagement in runs 1 to 3 either names the
    term (runs 2, 3) or uses count words (run 1, F-041). The share wording the
    instruction gives ("a bigger share of the people who saw it…") never appeared.
  - September's card also:
    - uses "pillars", an agency term that is not in `CLIENT_TERMS`
    - is ungrammatical ("a 1.9× engagement rate as posts")
    - is not about its own trigger: it cites G3 and G5, not T3, while October's quota
      card gave "We posted 8 of the 16"
- **Evidence:** the instruction asks the finding to "give the trigger's or comparison's
  own number or ratio", and a percentage needs a name. The allowed name is long, so the
  model takes the short one. This is the C17b lesson: a rule the model ignores even when
  told is built in code.
- **Why it matters:** the client card is the one sentence that may leave the agency.
  The strategist rewrites it every month, and the check stays as a standing alert.
- **Fix direction (proposal):**
  - Build the card finding in finalize from the trigger, with fixed wording per rule:
    - engagement: "A bigger share of the people who saw your {kind} liked, commented
      on, shared or saved it: 2.2× your usual."
    - drop-off: "{48}% of people were still watching your {kind} after 3 seconds;
      usually {58}%."
    - quota: "We posted {8} of the {16} posts planned for {October}."
  - Take {kind} from the post's pillar, platform and format.
  - Have the model write only the card's action. The action and button could also come
    from the request (quantity and category).
  - Add "pillars?" to `CLIENT_TERMS`.

### F-049: The quota request's size is left to the model, and the card promises to "catch up" (low, draft-insights, runs 2 and 3)

- **Observed:** October asks for 3 videos for 8 behind; September asks for 2 photos for
  10 behind. Both are within "up to 3", so the bigger gap got the smaller request. Both
  cards say "so we can catch up", which 2 or 3 posts cannot do. The requests are for
  next month, which has its own quota of 16. The September session itself noted that 2
  falls well short.
- **Evidence:** `draft.py` says "quantity (2, so the result rests on more than one post;
  up to 3 for the quota trigger…)". The design caps quantities by next month's quota,
  not by this month's gap.
- **Why it matters:** the size the strategist sees depends on the run, and the card
  promises something the request cannot deliver.
- **Fix direction (proposal):**
  - Set the quota request's quantity in code: `MAX_QUANTITY`, or the smaller of the gap
    and `MAX_QUANTITY`.
  - Word the card as "to help us keep to the plan", not "catch up".
  - Decide in the design whether a quota request adds to next month's plan or fills
    part of it.

### F-050: video_003's pictures are still shown as its first 8 tags alphabetically, without "person" and "speaking-to-camera" (low, latent, draft-insights, runs 2 and 3)

- **Observed:**
  - P1 and P8 (video_003) are still described as "blinds, certificate, chair, desk,
    glasses, keyboard, microphone, office", in both regenerated plans.
  - P2 and P7 (video_014) and P6 and P11 (video_007) show "person, speaking-to-camera".
  - video_003's `tags.json` has 13 tags at 48.2 s (all 10 frames), including person and
    speaking to camera.
  - Nothing in runs 2 and 3 rests on it:
    - neither plan has a visual comparison
    - the briefs say "adviser-led" and "success-story style"
    - September's T1 reason says only that the pictures exist
- **Evidence:** `prepare.py:366` sorts the shown tags by seconds only. Python's stable
  sort keeps the alphabetical order of the ties, and `prepare.py:369` cuts at
  `MAX_VISUAL_TAGS`. The F-036 fix status said "ties no longer cut alphabetically";
  that holds for grouping, not for what the model reads.
- **Why it matters:** the model reads the talking-head video as one without a person
  speaking. A hypothesis or brief could repeat F-036's false contrast from the text
  alone.
- **Fix direction (proposal):** show every tag tied with the 8th (13 here), or rank tags
  that tie by a fixed order that puts people and actions first. Add a prepare test on
  video_003's tags.

### F-051: T2's hypothesis rests mostly on the flagged video and does not say so; T1's says so and is then a recommendation, not a reason (medium, draft-insights, October run 2)

- **Observed:**
  - T2 H1 cites G15, whose other side (54.67%) is P1, P7 and P8. P1 and P8 are the
    flagged video_003, and the label says "the other side holds T2's own post P8 and the
    same video posted again (P1)".
  - The hypothesis says "an early pattern based on 2 pieces of content in each group",
    not that one of them is the flagged video. Without video_003, that side has 1 piece
    of content and the comparison would not meet `MIN_GROUP`. The case for a question
    opening is mostly the flagged video's own result, and the test's bar comes from it
    (F-045).
  - T1 H1 says "includes the flagged post itself", but it then offers "may be worth
    testing again", which is a recommendation, not a reason. The model's own note says
    not to present G2 as an explanation.
- **Evidence:**
  - The instruction says "When a comparison holds the flagged post itself, say so: a
    post cannot explain its own result", and nothing checks it.
  - A comparison bears on a post trigger only when the trigger's post is in it
    (`prepare.py` `bears`), so every comparison cited for T1 or T2 holds its own post.
- **Why it matters:** the strategist reads T2's hypothesis as resting on 2 pieces of
  content per side, when it is largely the flagged video compared with the rest.
- **Fix direction (proposal):**
  - For a comparison that bears on a post trigger, have prepare also give the averages
    without the flagged video and its twins, and whether each side still has
    `MIN_GROUP`. A hypothesis can then rest on the other posts, and a trigger with no
    such comparison goes to "not enough evidence".
  - Have finalize flag a hypothesis that cites a G whose label holds the trigger's own
    post when the text does not say so ("flagged", "itself", "own").

### F-052: September T1's hypothesis rests only on the flagged post itself; run 3's "not enough evidence" was right (medium, draft-insights, September run 5)

- **Observed:**
  - T1 (ci-2609-01, P1, 48% gone in 3 s) has: "The opening statement may not have given
    viewers enough reason to keep watching; this is a possibility based on one piece of
    video content, so the pattern is not established." Its only ref is P1, T1's own post.
  - Its request ("2 more visa-success-story videos with a new opening") cites P1 and T1,
    and no comparison.
  - The model's own note 2 says the suggestion "is based on one piece of content and
    does not establish a pattern".
  - In the same answer, T2 (P5) lacks the same thing and got "not enough evidence".
- **Evidence:**
  - In the regenerated plan, G1 to G7 all "bear on T3"; none bears on T1 or T2. With
    P1 left out (F-051), the only other videos are P2 and P5, so no drop-off comparison
    can have 2 pieces of content on each side.
  - Apart from the own post now being left out, T1's plan is the one run 3 answered
    "not enough evidence" to. Only the model's answer changed, at low effort.
  - The instruction says "When nothing in the comparisons or posts bears on a trigger,
    set enough_evidence to false". "or posts" lets the trigger's own post count as
    bearing on it. That contradicts "a post cannot explain its own result" a few lines
    later.
  - `clean_insight` keeps any hypothesis with a known ref. `insight_checks` does not ask
    for a comparison.
- **Why it matters:** this is the self-explanation F-051 removed from the comparisons,
  now made directly from the post's hook label. The strategist gets a "hypothesis" and a
  two-video test resting on one post, which the design says to answer with "not enough
  evidence" (decision 10, "never stretch thin evidence into a claim").
- **Fix direction (proposal):**
  - In prepare, record for each trigger the comparisons that bear on it (in
    `plan["triggers"][T]`, or `bears_on` in each G's ref). When there are none, say so
    under the trigger in the context: "no comparison bears on this trigger: answer not
    enough evidence".
  - In finalize, require a post trigger's hypothesis to cite at least one G that bears on
    its trigger. Otherwise drop it into `dropped` with that reason. When no hypothesis is
    left, move the insight to `not_enough_evidence` with a code-written reason. A check
    alone would leave a two-video request resting on one post on the page.
  - Replay effect: only September run 5's T1 changes. Every hypothesis in runs 1, 2 and 4
    cites a bearing G (G2, G1, G17, G13, G15, G3, G7).
  - Drop "or posts" from the instruction's not-enough-evidence sentence.

### F-053: The drop-off requests change the opening, which no comparison they cite is about; the instruction's example prescribes it (medium, draft-insights, October run 4 and September run 5)

- **Observed:**
  - October T2's hypothesis is "The promo style may be worth testing with a different
    opening, since promo posts had lower average still-watching after 3 seconds than
    posts in other pillars…". It cites G7, Promo (P5, P12) vs other pillars, 49.65% vs
    67.53%.
  - The request asks for "two English promo videos … but open with a different first
    line". It changes the opening while keeping the promo kind the hypothesis blames.
  - If both new promos beat 58%, the result shows that promos can hold viewers, which
    counts against G7. It says nothing about whether the opening lost them. The model's
    note 2 says "the material cannot establish that the opening explains" it.
  - September T1 asks for the same "new opening" promo with no comparison at all
    (F-052).
  - The hypothesis is a suggestion ("may be worth testing"), not a reason. This is
    F-051's second half, still there.
- **Evidence:**
  - T2's comparisons (G5 to G9) cover pillar, platform and language. The only hook
    comparison (G16) bears on T3, and without P1 and P8 a hook comparison for T2 has 1
    piece of content on one side.
  - The instruction gives the answer as an example: "when a promo lost viewers in its
    first seconds, ask for a promo with another opening, not a different kind of video".
    Both drop-off requests in runs 4 and 5 follow it word for word, whatever the
    evidence.
  - "Keep the flagged kind" and "change only what the hypothesis is about" conflict when
    the hypothesis is about the kind (here, the pillar).
  - Nothing checks that what a request changes is what its tested hypothesis's
    comparison is about.
- **Why it matters:** the test the strategist reads next month cannot confirm or refute
  the hypothesis it names. This is the F-038 problem in a new form. The request itself
  (try a new opening on a promo) is reasonable, but it is an untested idea and is
  presented as a test.
- **Fix direction (proposal):**
  - Replace the example with the rule it stands for: a request changes what the cited
    comparison is about. When the only comparison is about the flagged post's own kind,
    the request either tries that kind's alternative, or keeps the kind and says the
    change is untried (`tests` 0, and a review note that no comparison is about
    openings).
  - Ask that a hypothesis say why the result may have happened ("promo videos may lose
    more viewers in their first seconds"), not what to try.
  - Have finalize flag a request whose title or brief changes the opening ("opening",
    "first line", "hook", "question") when no G its tested hypothesis cites is a hook
    comparison.

### F-054: Client card actions repeat the code's finding; the "16" check is a false alarm caused by the card rule (medium, draft-insights, September run 5)

- **Observed:**
  - September T3's card renders as "We posted 6 of the 16 posts planned for September.
    We posted 6 of the 16 posts planned for September; send us three educational videos
    for October, and we'll post them." The same sentence appears twice.
  - September T1's card renders as "48% of the people who started watching your English
    Instagram video stopped in the first 3 seconds. Your English Instagram video had 52%
    of viewers still watching after 3 seconds, below the 90-day average of 57%; send us
    two more…". That is the same drop-off twice, and it brings "90-day average" onto the
    card, where the code's wording is "your usual".
  - The only check is "16" in T3's card action ("in the data, but not in what it cites
    (G2 … G6)"). The number is right: it is T3's quota, from the finding. The real
    defect, the repeat, is not flagged. "6" passes only because G3's 5.76% rounds to 6.
  - October's three actions start from the ask and repeat nothing.
- **Evidence:**
  - `insight_texts` checks the card action and button against `action["evidence"]`
    plus the quantity, not the trigger. A replay that also allows the trigger's numbers
    clears the "16" check and changes nothing else in either month.
  - The context gives the finding "(do not write your own)", and the instruction asks
    for "one sentence that follows from that finding". Neither says the action is shown
    right after the finding and must not repeat it.
  - `CLIENT_TERMS` has "baselines?" but not "90-day" or "average".
- **Why it matters:** the card is the one text that may reach the client, and a
  repeated sentence shows it was not read before it went out. The false alarm points the
  strategist at the right number and away from the actual defect.
- **Fix direction (proposal):**
  - Let the card action and button use their trigger's numbers too, as tests already
    may.
  - Say in the instruction that the action is shown right after the finding: start from
    the ask ("Send us…"), and never restate the finding or its numbers.
  - Have finalize flag a card action that repeats the finding: two or more of the
    finding's numbers, or most of its words.
  - Add "90-day" to `CLIENT_TERMS`. The card's own wording is "your usual".

### F-055: The look-alike check at 0.25 flags a promo and an educational request on boilerplate words; duplicates and different requests now overlap in score (medium, draft-insights, October run 4)

- **Observed:**
  - Run 4 flags T2/T3. T2 asks for "two English promo videos like your
    visa-success-story video, but open with a different first line". T3 asks for "three
    educational videos explaining practical steps for students preparing a visa
    application". These are different requests.
  - Their score is 0.27 (7/26). The shared words are please, send, video, videos, visa,
    explaining and different.
  - The real duplicates score 0.28 (run 2 T1/T3), 0.35 (run 4 T1/T3) and 0.50 (run 1
    T1/T2). Different same-category requests score 0.07 to 0.27, with run 4's T1/T2 at
    0.23. See the table in "Re-test (runs 4 and 5)".
  - The real T1/T3 duplicate also persists: the quota request is told to ask for "what
    the comparisons show works best", which in October is the educational video T1 asks
    for. That instruction overrides "never the same kind of video for two triggers".
- **Evidence:**
  - `FILLER` removes generic words but not request boilerplate ("please", "send", the
    category's own noun in both numbers, the client's subject "visa").
  - The F-046 fix's G-overlap idea no longer applies: since F-051, a post trigger's
    comparisons are never the quota trigger's (run 4's T1/T3 share no G).
- **Why it matters:** one of run 4's two alerts is false, and the margin between the
  real and false scores is 0.01. A false alarm next to a real one teaches the strategist
  to skip both. This is the F-029 pattern.
- **Fix direction (proposal):**
  - Compare what is asked for: the category plus the kind named in title and brief
    (educational, promo, success story, case study). On all 10 pairs in runs 1 to 5 this
    flags exactly the 3 duplicates.
  - Or add request boilerplate to `FILLER` (please, send, video(s), photo(s), post(s),
    story/stories, visa, explaining, like, different, same, English, Nepali, platform
    names). That gives duplicates 0.20 to 0.40 and different same-category pairs at most
    0.07, so a threshold of 0.15 separates them in runs 1 to 5.
  - For the duplicate itself, decide in the design whether the quota request may add to
    a post trigger's request (and then say so on one card) or must ask for the
    best-performing kind no other request asks for. Then word the instruction to match.

### F-056: video_003's outdated topic tags send the misheard organisation name to the model (low, latent, draft-insights, runs 1 to 5)

- **Observed:** in both plans, P1 and P8 (video_003) carry "entity
  cleary-consulting-group", the speech-to-text mishearing of Tilicho Consulting Group
  (F-011). The same posts' captions say "Contact Tilicho Consulting Group", so the model
  gets two names for the organisation. No text in runs 1 to 5 used the wrong one.
- **Evidence:**
  - `output/tag-topics/video_003-*/metadata.json` was made 2026-11-05T08:42 and records
    no `organisation.json` among its inputs. F-011's fix makes such a result `outdated`
    until it is re-made.
  - draft-insights' prepare reads topic tags without checking whether they are outdated
    and gives no warning. Its summary says "topic tags for 6".
  - The ORGANISATION section tells the model to spell the name as given, which is why
    nothing leaked.
- **Why it matters:** a request brief or review note could name "Cleary Consulting
  Group". The prompt is the only guard, which is what F-011 replaced with code for
  generate-copy.
- **Fix direction (proposal):**
  - Have prepare warn when a post's topic tags, copy or visual tags are outdated (and
    name them).
  - Or leave out `entity` tags that match `heard_as` or are not the organisation's name.
  - Re-run `/tag-topics` on video_003.

### F-057: October's three requests all ask for educational videos because their evidence does; the look-alike check is right by its rule, but its advice and the "never the same kind" rule do not fit (medium, draft-insights, October run 6)

- **Observed:**
  - T1 asks for "two educational TikTok videos in the same Nepali style as your
    successful video" (tests 1, G4).
  - T2 asks for "two English educational Instagram videos", keeping P8's format,
    platform, language and opening style (tests 1, G7).
  - T3 asks for "three educational videos that open with a question" (G16, G11).
  - finalize flags T1/T2, T1/T3 and T2/T3: "both ask for educational videos; merge them
    or make each test its own hypothesis".
  - The client gets three cards in a row asking for educational videos: 7 in all.
  - The model's note 4 asks the strategist to confirm that the three are "distinct from
    the other requests".
- **Evidence:**
  - Each request follows its own evidence:
    - T1's comparisons (G1 to G4) are all about P7's own features (video,
      educational), so keeping the rest like P7 means an educational video.
    - G7's other side (P2, P6, P7, P11) is all educational, so changing only the pillar
      means educational.
    - The quota request asks for "what the comparisons show works best", which is G11
      (educational, 2×).
  - The instruction's "never the same kind of post for two triggers" cannot be met
    together with those three rules when one pillar leads every comparison. October
    has had a shared-kind pair in every run: run 1 T1/T2, run 2 T1/T3, run 4 T1/T3, and
    run 6 all three.
  - T1 and T2 already test their own hypotheses, on different measures, bars,
    platforms, languages and openings (engagement at 4.7% on a Nepali TikTok; still
    watching after 3 s at 58% on an English Instagram video with a statement opening).
    Merging them would test neither, so the check's advice is wrong for that pair.
  - T2's controls are only in its brief. Its card says "two English educational
    videos", while T3's card asks in the same month for educational videos that open
    with a question. A client who sends question-opening videos for both breaks T2's
    test.
- **Why it matters:** three "merge them" alerts on an overlap the evidence produces
  teach the strategist to skip the check (the F-029 pattern), and following the advice
  for T1/T2 would wreck two tests. The client sees the same ask three times.
- **Fix direction (proposal; recommended: leave the decision to the strategist with a
  correct check, rather than a code merge or the quota request taking over):**
  - Do not merge in code: merged requests test neither hypothesis. Do not let the quota
    request absorb the others: two tests would become one untested ask (`tests` 0).
  - In the design and the instruction, replace "never the same kind of post for two
    triggers" with: requests may share a kind when their evidence points there, and
    each brief says what sets it apart (platform, language, opening). A test's card
    also names its controls ("two English Instagram videos that start with a
    statement").
  - Narrow `same_request_checks` to pairs that nothing sets apart (same category, kind,
    platform and language, as the fields and title name them). Word it "ask for the same
    thing; merge them or say what sets them apart". Replay it on runs 1 to 6: it should
    still catch run 4's T1/T3 (both "educational videos", language any, no platform).
  - Replace the alerts on pairs with the quota request by one code-written line in
    `insights.md`: "November asks for 7 videos, all educational (T1 2, T2 2, T3 3);
    decide whether the client sees them as one ask."

### F-058: T1's test bar is below what its own comparison's videos already average, so an ordinary video would confirm it (low, draft-insights, October run 6)

- **Observed:**
  - T1's hypothesis is "Video format may be one factor worth testing" (G4: video posts
    5.02% vs 3.53%, 1.4×, without P7).
  - Its test: "If 2 new video posts have an average engagement rate above 4.7%, that
    would support this possibility".
  - The flagged result is 10.23%, 2.2× the average.
  - The model's note 2: "check whether the proposed repeat is a useful test before
    sharing".
- **Evidence:**
  - 4.7% is the trigger's bar (the 90-day average), so the F-045 check passes.
  - But G4's videos already average 5.02% without P7. The test therefore predicts an
    ordinary video, not the flagged result, and a 1.4× comparison cannot account for a
    2.2× one.
  - Run 4's T1 cited G3 (educational, 1.7×) and set the bar at its 5.94%. Both answers
    pass the code, so the bar depends on the model's choice.
- **Why it matters:** a confirmed T1 next month would say little about why P7 did well.
  The strategist could read a routine result as support for the hypothesis.
- **Fix direction (proposal):**
  - For the engagement trigger (a post that did better), make the number to beat the
    higher of the trigger's bar and the average of the side the request asks for in the
    cited comparison. prepare can state it per comparison under the trigger.
  - Have finalize flag a confirm_if below that average.
  - Keep the 90-day average for a drop-off trigger. There the test asks whether the
    change brings the post back to normal, so T2's 58% is right.

### F-059: T1's request asks for Nepali TikTok videos, but its language is "any" (low, draft-insights, October run 6)

- **Observed:** T1's title is "2 more Nepali TikTok videos", and its brief is "…in the
  same Nepali style as your successful video". The request's `language` is `any`, and
  `insights.md` shows "any" in the Language column.
- **Evidence:**
  - The instruction allows "ne only when a comparison about Nepali posts supports it".
    No such comparison bears on T1: with P7 left out (F-051), only one other Nepali post
    remains, and G14 and G17 bear on T3.
  - The same instruction says to keep the rest like the flagged post, which is in
    Nepali. The model followed both rules, one in the field and one in the text.
  - finalize does not compare the language field with the title or brief.
- **Why it matters:** the asset request Pulse would create carries language "any" for an
  ask that only makes sense in Nepali. The client or the editor could film it in
  English.
- **Fix direction (proposal):**
  - For a post trigger's request, set the language to the flagged post's language
    unless the tested comparison is about language. prepare knows each post's language.
  - Have finalize flag a title or brief that names Nepali or English when the field
    says otherwise.

### F-060: T1's brief calls the flagged TikTok video "question-led", but it used a curiosity hook, and the brief adds a change no T1 comparison is about (low, draft-insights, October run 8)

- **Observed:**
  - T1's brief: "Send us two educational videos for TikTok, each covering a different
    practical visa question, with the same Nepali language and question-led approach as
    your flagged video."
  - P7 (the flagged TikTok post, ci-2610-02) used hook 3 of video_014's copy, and its
    style is curiosity: "Visitor visa refusals can hinge on a factor applicants may
    overlook." The question hook ("Are you planning a visitor visa application for your
    parents?") is P2's, the same video posted on Instagram.
  - The hypothesis T1's request tests cites G3 (educational vs other pillars,
    engagement), and P7 is already educational. A new video that opens with a question
    also changes the hook style, which G3 is not about. The only hook comparison (G16,
    question hook 1.3×) bears on T3.
  - No check fired, and no review note mentions the hook.
- **Evidence:**
  - The plan lists P7 as "opening hook used (curiosity)" and P2 as "(question)", and it
    marks P7 "same video as P2, posted again on tiktok". The model probably took the
    video's Instagram hook to be the TikTok post's.
  - F-053's third proposal was not built: flag a request that changes the opening when
    no comparison its tested hypothesis cites is about hooks. The F-053 fix covered only
    the example and the advice wording.
- **Why it matters:**
  - The brief tells the client something untrue about their own best video.
  - If the client follows it, the test mixes two changes. A result above 5.94% could
    come from the question opening as much as from the pillar.
  - It is low because one strategist edit fixes it (take out "and question-led
    approach"), and the test still names its measure and bar.
- **Fix direction (proposal):**
  - In prepare, give the flagged post's hook style in its trigger line ("P7 opened with
    a curiosity hook"), next to the rule that the request keeps the rest like the
    flagged post.
  - Have finalize flag a post trigger's brief that names a hook style (question,
    curiosity, statement, "-led", "opening") other than the flagged post's, when no
    comparison its tested hypothesis cites is a hook comparison.
