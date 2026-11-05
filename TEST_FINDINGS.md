# Test findings: /generate-copy

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

## Fix status (2026-11-05, uncommitted, awaiting re-test)

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
