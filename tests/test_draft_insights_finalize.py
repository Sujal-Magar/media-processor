from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT, load_script

prepare = load_script("draft-insights", "prepare")
finalize = load_script("draft-insights", "finalize")

TRIGGERS = json.loads((ROOT / "fixtures" / "insights-input.example.json").read_text(encoding="utf-8"))
REPORT = json.loads((ROOT / "fixtures" / "report-input.example.json").read_text(encoding="utf-8"))
# One comparison for the example (G1), so ratios and comparison numbers can be tested.
COMPARISON = {
    "kind": "pillar", "value": "Educational", "measure": "true_engagement_rate",
    "group": "Educational posts", "rest": "posts in other pillars",
    "posts": ["ci-0001"], "others": ["ci-0001"], "pieces": 1, "other_pieces": 1,
    "mean": 5.0, "other_mean": 2.0, "times": 2.5, "difference_pct": 150, "triggers": [0],
    "without": [],
}  # fmt: skip


def plan_for(output_dir: Path, **changes) -> dict:
    """A plan as prepare writes it for the example triggers and report input."""
    with tempfile.TemporaryDirectory() as folder:
        source, reports = Path(folder) / "2026-10.json", Path(folder) / "reports"
        reports.mkdir()
        source.write_text(json.dumps(TRIGGERS), encoding="utf-8")
        (reports / "2026-10.json").write_text(json.dumps(REPORT), encoding="utf-8")
        triggers = prepare.read_triggers(source)
        month, window, files = prepare.load_window(triggers, reports)
    sent, held = prepare.check_triggers(triggers, month)
    posts = [post for post in window if prepare.full(post)]
    context, refs, allowed, general = prepare.build_context(
        triggers, month, posts, sent, [COMPARISON], {}, None, [1, 2, 3]
    )
    return {
        "processor": "draft-insights",
        "source": {"name": "2026-10.json", "path": "input/insights/2026-10.json", "sha256": "0" * 64},
        "month": {"period": "2026-10", "next": "2026-11", "name": "October 2026", "next_name": "November 2026"},
        "inputs": {"report": {"name": "2026-10.json", "sha256": "1" * 64}, "window_reports": files,
                   "posts": {}, "organisation": None},  # fmt: skip
        "organisation": None,
        "options": {"model": "test-model", "reasoning_effort": "low"},
        "triggers": {f"T{n}": {"rule": t["rule"], "content_item_id": t["content_item_id"], "card": t["card"],
                               "bar": t.get("bar"), "quantity": t.get("quantity")}
                     for n, t in enumerate(sent, 1)},  # fmt: skip
        "format_lean": prepare.format_lean(posts),
        "pillars": ["case study", "educational", "promo"],
        "held_back": held,
        "quantities": [1, 2, 3],
        "refs": refs,
        "allowed_numbers": allowed,
        "general_numbers": general,
        "context": context,
        "estimated_input_tokens": 100,
        "warnings": [],
        "output_dir": str(output_dir),
        "replaces": None,
        "created_at": "2026-11-06T00:00:00+00:00",
        **changes,
    }


def line(text, *refs):
    return {"text": text, "refs": list(refs)}


def insight(**changes):
    """An insight for T1 that keeps to every rule."""
    good = {
        "trigger": "T1",
        "enough_evidence": True,
        "reason": "",
        "observation": line("Your Instagram video had an engagement rate of 5%, 2.1× the 90-day average of 2.4%.", "T1"),
        "hypotheses": [{
            **line("Educational videos may hold attention better: Educational posts averaged 5% against 2%.", "G1"),
            "confirm_if": "Two more educational videos are each liked, commented on, shared or saved by over 5% of the people reached.",
            "refute_if": "Neither is liked or shared by more of the people reached than the other posts.",
        }],
        "action": {"title": "2 more educational videos", "tests": 1, "category": "video", "quantity": 2, "language": "any",
                   "brief": "Film two short videos that each explain one step of a student visa.", "refs": ["G1", "P1"]},
        "client_card": {
            "action": "Send us 2 more educational videos this month.",
            "button": "Send us 2 more videos",
        },
    }  # fmt: skip
    return {**good, **changes}


NOT_ENOUGH = {
    "trigger": "T2", "enough_evidence": False, "reason": "No comparison shows what would fill the open slots.",
    "observation": line("", ), "hypotheses": [], "client_card": {"action": "", "button": ""},
    "action": {"title": "", "category": "video", "quantity": 1, "language": "any", "brief": "", "refs": []},
}  # fmt: skip


def run(insights=None, notes=None, **plan_changes):
    """finalize on an answer; returns (summary, document, markdown)."""
    with tempfile.TemporaryDirectory() as folder:
        job, output = Path(folder) / "job", Path(folder) / "out"
        (job / "results").mkdir(parents=True)
        (job / "plan.json").write_text(json.dumps(plan_for(output, **plan_changes)), encoding="utf-8")
        answer = {"insights": insights if insights is not None else [insight(), NOT_ENOUGH],
                  "review_notes": notes or []}  # fmt: skip
        (job / "results" / "answer.json").write_text(json.dumps({"answer": answer, "usage": {}}), encoding="utf-8")
        summary = finalize.finalize(job)
        document = json.loads((output / "insights.json").read_text(encoding="utf-8"))
        markdown = (output / "insights.md").read_text(encoding="utf-8")
        assert not job.exists()
    return summary, document, markdown


def checks_of(**changes):
    summary, _, _ = run([insight(**changes), NOT_ENOUGH])
    return " | ".join(summary["checks"])


class GoodAnswerTest(unittest.TestCase):
    def test_a_good_answer_is_complete_and_raises_nothing(self):
        summary, document, markdown = run()
        self.assertEqual(summary["status"], "complete", summary)
        self.assertEqual((summary["checks"], summary["missing"], summary["dropped"]), ([], [], 0))
        self.assertEqual(summary["not_enough_evidence"], ["T2"])
        self.assertEqual(summary["held_back"], 1)
        self.assertEqual(document["review_status"], "draft")
        saved = document["insights"][0]
        self.assertEqual(saved["status"], "Proposed")
        self.assertEqual(saved["trigger_rule_id"], "engagement_gt_200pct_mean")
        self.assertEqual(saved["action"]["due_month"], "2026-11")
        self.assertEqual([e["ref"] for e in saved["action"]["evidence"]], ["G1", "P1"])
        self.assertIn("Hypotheses (to test, not facts)", markdown)
        self.assertIn("## Held back (not sent)", markdown)
        self.assertIn("## Not enough evidence", markdown)


class NumberChecksTest(unittest.TestCase):
    def test_a_number_the_data_does_not_hold_makes_it_incomplete(self):
        summary, _, _ = run([insight(observation=line("Your video reached 7% more people.", "T1")), NOT_ENOUGH])
        self.assertEqual(summary["status"], "incomplete")
        self.assertIn('"7" in T1\'s observation matches no number in the data', " | ".join(summary["checks"]))

    def test_a_number_from_data_the_sentence_does_not_cite(self):
        found = checks_of(observation=line("Your video reached 8,000 people.", "T1"))
        self.assertIn('"8,000" in T1\'s observation is in the data, but not in what it cites (T1)', found)

    def test_the_request_s_quantity_may_be_written(self):
        self.assertEqual(checks_of(), "")

    def test_a_hypothesis_s_test_may_use_its_trigger_and_the_baseline(self):
        hypothesis = {**insight()["hypotheses"][0], "confirm_if": "Both new videos are liked or shared by over 5% of the people reached.",
                      "refute_if": "Neither is liked or shared by more than 2.4% or 4.8% of the people reached."}  # fmt: skip
        self.assertEqual(checks_of(hypotheses=[hypothesis]), "")
        hypothesis["confirm_if"] = "Both new videos reach 8,000 people."  # P1's, not the trigger's
        self.assertIn('"8,000" in T1\'s hypothesis 1, what would confirm it', checks_of(hypotheses=[hypothesis]))

    def test_ratios_must_be_one_the_cited_data_gives(self):
        twice = "Your video was saved twice as often as usual, so send us 2 more."
        self.assertIn('has a ratio ("twice")', checks_of(client_card={**insight()["client_card"], "action": twice}))
        other = line("Your video did 2.5× better than usual.", "T1")
        found = checks_of(observation=other)
        self.assertIn('has a ratio ("2.5×")', found)
        self.assertNotIn("ratio", checks_of(observation=line("Your video did 2.5× better than usual.", "G1")))


class WordingChecksTest(unittest.TestCase):
    def test_a_cause_outside_a_hypothesis_is_flagged(self):
        found = checks_of(observation=line("Your video did well because it was educational.", "T1"))
        self.assertIn('T1\'s observation states a cause ("because")', found)

    def test_a_hypothesis_must_be_a_possibility(self):
        stated = {**insight()["hypotheses"][0], "text": "Educational videos hold attention better."}
        self.assertIn("is not worded as a possibility", checks_of(hypotheses=[stated]))
        hedged = {**stated, "text": "Educational videos may hold attention because they answer a question."}
        self.assertEqual(checks_of(hypotheses=[hedged]), "")

    def test_internal_terms_and_jargon_stay_off_the_client_card(self):
        card = insight()["client_card"]
        for words, term in (("Your engagement rate beat the baseline.", "engagement rate"),
                            ("Your post had 8,000 impressions.", "impressions"),
                            ("Send us 2 more so we can catch up.", "catch up")):  # fmt: skip
            found = checks_of(client_card={**card, "action": words})
            self.assertIn(f'"{term}"', found)

    def test_references_in_the_text_are_flagged(self):
        found = checks_of(action={**insight()["action"], "brief": "Film two videos like P1."})
        self.assertIn('shows the reference "P1"', found)

    def test_a_long_button_is_flagged(self):
        card = {**insight()["client_card"], "button": "Yes please send us two more videos now"}
        self.assertIn("button has 8 words", checks_of(client_card=card))


def pace(**changes):
    """An answer for T2, the pace trigger: no hypotheses, a request toward the gap."""
    good = {
        "trigger": "T2", "enough_evidence": True,
        "reason": "What the client sent and the schedule are not in the data.",
        "observation": line("2 of the 16 posts were published, 14 behind.", "T2"), "hypotheses": [],
        "action": {"title": "3 videos for Instagram", "tests": 0, "category": "video", "quantity": 3,
                   "language": "any", "brief": "Film three vertical clips about life on campus.", "refs": ["G1"]},
        "client_card": {"action": "Send us three short videos for next month.", "button": "Send us 3 videos"},
    }  # fmt: skip
    return {**good, **changes}


class ReviewFixesTest(unittest.TestCase):
    """The checks added after the first paid October run (F-037 to F-044)."""

    def test_the_pace_trigger_gets_no_hypotheses(self):
        stray = [{**insight()["hypotheses"][0]}]
        summary, document, markdown = run([insight(), pace(hypotheses=stray)])
        self.assertEqual(summary["status"], "complete", summary)
        saved = document["insights"][1]
        self.assertEqual((saved["hypotheses"], saved["action"]["tests"]), ([], 0))
        self.assertEqual(saved["why_unknown"], "What the client sent and the schedule are not in the data.")
        self.assertEqual(document["dropped"][0]["reason"], "the data cannot say why posting fell behind")
        self.assertIn("**Why posting fell behind:** the numbers cannot say.", markdown)
        self.assertIn("reports/2026-10.json (the posts in the baseline window)", markdown)

    def test_a_request_names_the_hypothesis_it_tests(self):
        found = checks_of(action={**insight()["action"], "tests": 2})
        self.assertIn("T1's request does not say which hypothesis it tests", found)

    def test_a_test_must_name_its_measure(self):
        vague = {**insight()["hypotheses"][0], "confirm_if": "A new educational post performs more strongly."}
        self.assertIn("what would confirm it names no measure", checks_of(hypotheses=[vague]))

    def test_an_engagement_rate_is_a_share_not_a_count(self):
        card = insight()["client_card"]
        counted = "Educational videos were liked more often than your other posts, so send us 2 more."
        self.assertIn('gives an engagement rate as a count ("more often")', checks_of(client_card={**card, "action": counted}))
        self.assertNotIn("as a count", checks_of(client_card={**card, "action": "Send us 2 more like it."}))

    def test_two_requests_for_the_same_thing_are_flagged(self):
        same = pace(action={**pace()["action"], "title": "3 educational videos"})
        summary, _, _ = run([insight(), same])  # the quota request may match another
        self.assertNotIn("both ask for", " | ".join(summary["checks"]))
        summary, _, _ = run([insight(), pace()])
        self.assertEqual(summary["checks"], [])

    def test_a_button_says_how_many_and_no_slots(self):
        card = {**insight()["client_card"], "button": "Send us a video", "action": "Fill your open slots."}
        found = checks_of(client_card=card)
        self.assertIn("does not say how many", found)
        self.assertIn('uses the internal term "slots"', found)


class SecondReviewFixesTest(unittest.TestCase):
    """The rules added after runs 2 and 3 (F-045 to F-051)."""

    def test_the_card_finding_is_written_from_the_numbers(self):
        model_card = {**insight()["client_card"], "finding": line("Your engagement rate was great.", "T1")}
        _, document, markdown = run([insight(client_card=model_card), pace()])
        finding = document["insights"][0]["client_card"]["finding"]
        self.assertEqual(finding["text"], "A bigger share of the people who saw your English Instagram video "
                                          "liked, commented on, shared or saved it: 2.1× your usual.")  # fmt: skip
        self.assertEqual([e["ref"] for e in finding["evidence"]], ["T1"])
        self.assertEqual(document["insights"][1]["client_card"]["finding"]["text"],
                         "We posted 2 of the 16 posts planned for October.")  # fmt: skip
        self.assertIn("the first sentence is written from the numbers", markdown)

    def test_the_quota_request_is_sized_from_the_gap(self):
        small = pace(action={**pace()["action"], "quantity": 1})
        _, document, _ = run([insight(), small])
        self.assertEqual(document["insights"][1]["action"]["quantity"], 3)

    def test_a_test_below_the_average_is_flagged(self):
        low = {**insight()["hypotheses"][0], "confirm_if": "Both new videos are liked or shared by over 2% of the people reached."}
        self.assertIn("would be confirmed below its bar, the 90-day or group average (2% against 5%)", checks_of(hypotheses=[low]))

    def test_a_category_against_the_format_evidence_is_flagged(self):
        lean = {"category": "video", "text": "video vs picture posts: people reached 8,000 vs 4,000"}
        photo = insight(action={**insight()["action"], "category": "photo"})
        summary, _, _ = run([photo, pace()], format_lean=lean)
        self.assertIn("asks for a photo, but the numbers favour the other format", " | ".join(summary["checks"]))
        summary, _, _ = run([insight(), pace()], format_lean=lean)
        self.assertEqual(summary["checks"], [])


class ThirdReviewFixesTest(unittest.TestCase):
    """The rules added after runs 4 and 5 (F-052 to F-055)."""

    def test_a_hypothesis_must_cite_a_comparison_for_its_trigger(self):
        own = {**insight()["hypotheses"][0], "refs": ["P1"]}
        summary, document, _ = run([insight(hypotheses=[own]), pace()])
        self.assertEqual(document["dropped"][0]["reason"], "it cites no comparison for this trigger")
        self.assertIn("T1: no hypothesis with data behind it", summary["missing"])

    def test_a_trigger_no_comparison_bears_on_is_not_enough_evidence(self):
        refs = plan_for(Path("unused"))["refs"]
        refs["G1"]["triggers"] = ["T2"]
        own = {**insight()["hypotheses"][0], "refs": ["P1"]}
        summary, document, _ = run([insight(hypotheses=[own]), pace()], refs=refs)
        self.assertEqual(summary["not_enough_evidence"], ["T1"])
        self.assertIn("decided by the scripts", document["not_enough_evidence"][0]["reason"])

    def test_the_card_action_may_use_its_trigger_s_numbers(self):
        card = {**pace()["client_card"], "action": "Send us three short videos toward the 16 for next month."}
        summary, _, _ = run([insight(), pace(client_card=card)])
        found = " | ".join(summary["checks"])
        self.assertNotIn("not in what it cites", found)  # the false alarm of run 5
        self.assertIn("T2's client card action repeats its finding (16)", found)  # what it really is

    def test_a_card_action_that_repeats_the_finding_is_flagged(self):
        card = {**pace()["client_card"], "action": "We posted 2 of the 16 posts planned for October."}
        summary, _, _ = run([insight(), pace(client_card=card)])
        self.assertIn("T2's client card action repeats its finding", " | ".join(summary["checks"]))


def tested(trigger, title, kinds, language="any"):
    """A cleaned insight on a post trigger whose request tests a hypothesis citing
    comparisons of these kinds."""
    hypothesis = {"text": "", "evidence": [{"ref": f"G{n}", "kind": kind} for n, kind in enumerate(kinds, 1)]}
    return {"trigger": trigger, "trigger_rule_id": "engagement_gt_200pct_mean", "hypotheses": [hypothesis],
            "action": {"title": title, "brief": "", "category": "video", "tests": 1, "language": language,
                       "quantity": 2}}  # fmt: skip


class FourthReviewFixesTest(unittest.TestCase):
    """The rules added after runs 6 and 7 (F-053, F-057 to F-059)."""

    PILLARS = ["educational", "promo"]

    def test_requests_for_the_same_kind_are_flagged_only_when_nothing_sets_them_apart(self):
        same = [tested("T1", "2 educational videos", ["pillar"]), tested("T2", "2 more educational videos", ["pillar"])]
        self.assertIn("nothing sets them apart", " ".join(finalize.same_request_checks(same, self.PILLARS)))
        for other in (tested("T2", "2 educational videos", ["format"]),  # tests something else
                      tested("T2", "2 educational videos", ["pillar"], language="ne"),
                      tested("T2", "2 educational videos for TikTok", ["pillar"])):  # fmt: skip
            self.assertEqual(finalize.same_request_checks([same[0], other], self.PILLARS), [])

    def test_the_language_named_in_the_request_wins(self):
        self.assertEqual(finalize.language_of({"title": "2 Nepali TikTok videos", "language": "any"}), "ne")
        self.assertEqual(finalize.language_of({"title": "Nepali and English versions", "language": "any"}), "any")

    def test_a_hypothesis_that_gives_advice_is_flagged(self):
        advice = {**insight()["hypotheses"][0], "text": "Educational videos may be worth testing again."}
        self.assertIn('gives advice ("worth testing")', checks_of(hypotheses=[advice]))

    def test_investigate_is_advice_and_90_day_is_an_internal_term(self):
        advice = {**insight()["hypotheses"][0], "text": "Promos may lose viewers early, which is worth a closer look to investigate."}
        self.assertIn('gives advice ("investigate")', checks_of(hypotheses=[advice]))
        card = {**insight()["client_card"], "action": "Send us 2 more to beat your 90-day average."}
        self.assertIn('uses the internal term "90-day"', checks_of(client_card=card))

    def test_the_month_s_total_ask_is_given(self):
        summary, _, markdown = run([insight(), pace()])
        self.assertEqual(summary["total_ask"], "Requests for November 2026: 5 videos (T1 2, T2 3).")
        self.assertIn("(Requests for November 2026: 5 videos (T1 2, T2 3).)", markdown)


class StructureTest(unittest.TestCase):
    def test_unknown_and_second_answers_are_dropped(self):
        summary, document, _ = run([insight(), insight(trigger="T9"), insight(), NOT_ENOUGH])
        self.assertEqual(summary["dropped"], 2)
        self.assertEqual(len(document["insights"]), 1)

    def test_an_unanswered_trigger_is_missing(self):
        summary, _, _ = run([insight()])
        self.assertEqual(summary["status"], "incomplete")
        self.assertEqual(summary["missing"], ["T2: no answer"])

    def test_a_quantity_not_allowed_makes_it_incomplete(self):
        summary, _, _ = run([insight(action={**insight()["action"], "quantity": 5}), NOT_ENOUGH])
        self.assertEqual(summary["status"], "incomplete")
        self.assertIn("T1: the request asks for 5; it may ask for 1, 2, 3", summary["missing"])

    def test_a_sentence_citing_nothing_sent_is_dropped(self):
        hypothesis = {**insight()["hypotheses"][0], "refs": ["G7"]}
        summary, document, _ = run([insight(hypotheses=[hypothesis]), NOT_ENOUGH])
        self.assertEqual(summary["dropped"], 1)
        self.assertIn("T1: no hypothesis with data behind it", summary["missing"])
        self.assertEqual(document["dropped"][0]["where"], "T1 hypothesis 1")

    def test_a_hypothesis_without_its_test_is_flagged(self):
        hypothesis = {**insight()["hypotheses"][0], "refute_if": ""}
        self.assertIn("does not say what would refute it", checks_of(hypotheses=[hypothesis]))

    def test_the_plan_is_not_changed(self):
        before = copy.deepcopy(TRIGGERS)
        run()
        self.assertEqual(TRIGGERS, before)


if __name__ == "__main__":
    unittest.main()
