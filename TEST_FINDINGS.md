# Test findings: /generate-copy, /draft-report

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

## Fix status (2026-11-05, uncommitted; draft-report re-tested in runs 3 to 6)

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
