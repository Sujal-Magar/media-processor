# draft-insights implementation plan

Design: `docs/superpowers/specs/2026-11-06-draft-insights-design.md`. Tests run with
`cd tests && python3 -m unittest`; all must pass after every task.

1. **Shared code into `lib/`** (no behaviour change; draft-report's tests stay green).
   - `lib/report_input.py`: reading a month's report input (`read_month`, `read_post`,
     `post_refs`, `post_label`, `snapshot_text`, `fmt`, `month_of`, `month_name`, the
     D2 field names, `METRICS`, `PLATFORMS`, `SLOTS`). draft-report imports them.
   - `lib/wording.py`: `CAUSAL`, `DATA_GAP`, `INTERNAL`, `JARGON`.
2. **Model setting:** `insight_model()` in `lib/openai_api.py` (`OPENAI_INSIGHT_MODEL`,
   `OPENAI_INSIGHT_REASONING_EFFORT`), `.env.example`, `scripts/check_setup.py`,
   `.claude/skills/setup/SKILL.md`.
3. **Inputs:** `fixtures/insights-input.example.json` (pairs with
   `report-input.example.json`), `input/insights/2026-09.json` and `2026-10.json`.
4. **`processors/draft-insights/`:**
   - `finalize.py`: rule names, categories, languages, checks, `insights.md/json`.
   - `draft.py`: instructions, strict schema (quantity as an enum of the allowed values),
     one request, saved answer, never retried.
   - `prepare.py`: read and re-check the triggers, hold back Partial/Stale, read the
     report months in the baseline window, compute sizes and group comparisons, gather
     the video material, write `plan.json`, print the ready summary; stop free when
     nothing is left to send.
5. **Tests:** `tests/test_draft_insights_{prepare,draft,finalize}.py`.
6. **Wiring:** `.claude/skills/draft-insights/SKILL.md`, `.claude/settings.json`
   (`allow` prepare and finalize, `ask` draft), README, CLAUDE.md, OVERVIEW.md.
7. **Free dry run** on both mock months with a hand-written answer through finalize
   (printing only refs and numbers from `input/`, never the video material).
