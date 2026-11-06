from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT, load_script

prepare = load_script("draft-report", "prepare")
finalize = load_script("draft-report", "finalize")

EXAMPLE = json.loads((ROOT / "fixtures" / "report-input.example.json").read_text(encoding="utf-8"))


def plan_for(output_dir: Path, **changes) -> dict:
    """A plan as prepare writes it for the example input (with top-level changes)."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "2026-10.json"
        path.write_text(json.dumps({**copy.deepcopy(EXAMPLE), **changes}), encoding="utf-8")
        month = prepare.read_month(path)
    context, refs, allowed, general = prepare.build_context(month, {}, None)
    return {
        "processor": "draft-report",
        "source": {"name": "2026-10.json", "path": "input/reports/2026-10.json", "sha256": "0" * 64},
        "month": {"period": "2026-10", "previous": "2026-09", "next": "2026-11",
                  "name": "October 2026", "previous_name": "September 2026",
                  "next_name": "November 2026"},  # fmt: skip
        "inputs": {"posts": {}, "organisation": None},
        "organisation": None,
        "options": {"model": "test-model", "reasoning_effort": "low"},
        "highlights": {slot: prepare.post_refs(month).get(chosen) for slot, chosen in month["highlights"].items()},
        "tiles": {key: month["totals"][key] for key in finalize.TILES if month["totals"].get(key)},
        "has_earlier_months": bool(month["earlier_months"]),
        "leaders": {key: {k: v for k, v in lead.items() if k != "values"}
                    for key, lead in prepare.leaders(month).items()},  # fmt: skip
        "refs": refs,
        "allowed_numbers": allowed,
        "general_numbers": general,
        "context": context,
        "estimated_input_tokens": 100,
        "warnings": [],
        "output_dir": str(output_dir),
        "replaces": None,
        "created_at": "2026-11-05T00:00:00+00:00",
    }


def three_posts():
    """The example's posts plus P3, a complete post that reached more people than P1 but
    got fewer likes, shares and saves (P2 stays Partial)."""
    third = {**copy.deepcopy(EXAMPLE["posts"][0]), "content_item_id": "ci-0003", "source_file": None, "hook_used": None}
    third["snapshot"].update(reach_count=9000, likes_count=100, comments_count=5, shares_count=5,
                             saves_count=10, true_engagement_rate=1.33)  # fmt: skip
    return [*EXAMPLE["posts"], third]


def line(text, *refs):
    return {"text": text, "refs": list(refs)}


def answer(**changes):
    """An answer that keeps to every rule for the example input."""
    tiles = {"reach": "people saw your posts, up from 10,000", "video_views": "times your videos were played",
             "enquiries": "people got in touch", "new_followers": "new people follow you, down 10"}  # fmt: skip
    good = {
        "headline": line("A good October: 12K people reached and 6 enquiries.", "M:reach", "M:enquiries"),
        "what_happened": [line("12,000 people saw your posts, up 20% on September.", "M:reach"),
                          line("Your videos were played 9,000 times.", "M:video_views")],
        "what_worked": [line("Your Instagram video reached 8,000 people and was shared 40 times.", "P1"),
                        line("Instagram reached 8,000 people, up from 6,000.", "PL:instagram")],
        "what_did_not_land": [line("New followers went down by 10, to 40.", "M:new_followers"),
                              line("That is 20% fewer than in September.", "M:new_followers")],
        "top_post": [line("An educational video that 8K people saw.", "P1")],
        "highlights": [
            {"slot": "highest_reach", "text": "Seen by 8,000 people.", "refs": ["P1"]},
            {"slot": "highest_engagement", "text": "Liked, commented on, shared or saved the most, leaving out "
             "the post with incomplete numbers.", "refs": ["P1"]},
            {"slot": "best_retention", "text": "30% watched to the end, from incomplete numbers.", "refs": ["P2"]},
        ],
        "tiles": [{"metric": key, "text": text, "refs": [f"M:{key}"]} for key, text in tiles.items()],
        "next_month": [{"plan_item": "N1", "text": "Two more short videos that explain things."},
                       {"plan_item": "N2", "text": "A TikTok post every week."}],
        "review_notes": ["Check the TikTok numbers before sending."],
    }  # fmt: skip
    return {**good, **changes}


class FinalizeTest(unittest.TestCase):
    def run_finalize(self, given, **plan_changes):
        folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        job, output = folder / "job", folder / "output"
        (job / "results").mkdir(parents=True)
        plan = plan_for(output, **plan_changes)
        (job / "plan.json").write_text(json.dumps(plan))
        (job / "results" / "answer.json").write_text(json.dumps({"answer": given, "usage": {"input_tokens": 5}}))
        summary = finalize.finalize(job)
        document = json.loads((output / "report.json").read_text())
        markdown = (output / "report.md").read_text()
        self.assertFalse(job.exists())
        return summary, document, markdown

    def test_an_answer_that_keeps_to_the_rules_is_complete(self):
        summary, document, markdown = self.run_finalize(answer())
        self.assertEqual(summary["status"], "complete")
        self.assertEqual(document["review_status"], "draft")
        self.assertEqual(document["missing"], [])
        # The retention highlight rests on Partial P2 but says its numbers are incomplete.
        self.assertEqual(document["checks"], [])
        self.assertEqual([item["plan_item"] for item in document["next_month"]], ["N1", "N2"])
        self.assertIn("# October 2026 at a glance (draft)", markdown)
        self.assertIn("## What we're doing in November", markdown)
        self.assertIn("| people reached | 12.0K | ▲ 20% | people saw your posts, up from 10,000 |", markdown)
        self.assertIn("| enquiries | 6 | not shown |", markdown)

    def test_display_forms_and_differences_pass_the_number_check(self):
        given = answer(what_happened=[line("12K people saw your posts, up 20 per cent: 2,000 more.", "M:reach"),
                                      line("Your videos were played 9K times.", "M:video_views")])
        self.assertEqual(self.run_finalize(given)[0]["status"], "complete")

    def test_an_invented_number_makes_the_draft_incomplete(self):
        summary, document, _ = self.run_finalize(answer(headline=line("13K people reached.", "M:reach")))
        self.assertEqual(summary["status"], "incomplete")
        self.assertFalse(document["complete"])
        self.assertIn('"13K" in the headline matches no number in the month\'s data; check it '
                      "against the dashboard or remove it.", document["checks"])  # fmt: skip

    def test_a_ratio_is_flagged(self):
        given = answer(what_worked=[line("It was shared twice as often as usual.", "P1"), answer()["what_worked"][1]])
        checks = self.run_finalize(given)[1]["checks"]
        self.assertIn('What worked, sentence 1 has a ratio or fraction ("twice") that the data '
                      "does not give; check it or remove it.", checks)  # fmt: skip

    def test_unknown_references_are_dropped_and_recorded(self):
        given = answer(what_worked=[line("A post did well.", "P9", "M:impressions")])
        summary, document, _ = self.run_finalize(given)
        self.assertEqual(document["summary"]["what_worked"], [])
        self.assertIn({"section": "what_worked", "number": 1, "refs": ["P9", "M:impressions"]}, document["dropped"])
        self.assertIn('no "What worked" paragraph with data behind it', summary["missing"])
        self.assertEqual(summary["status"], "incomplete")

    def test_without_a_plan_next_month_stays_empty(self):
        summary, document, markdown = self.run_finalize(answer(), next_month_plan=None)
        self.assertEqual(document["next_month"], [])
        self.assertEqual([d["plan_item"] for d in document["dropped"] if d["section"] == "next_month"], ["N1", "N2"])
        self.assertEqual(summary["status"], "complete")
        self.assertIn("_The strategist writes this list; the input has no plan for November 2026 yet._", markdown)

    def test_an_item_of_the_plan_left_out_is_missing(self):
        given = answer(next_month=[{"plan_item": "N1", "text": "Two more short videos."},
                                   {"plan_item": "N7", "text": "An idea of our own."}])  # fmt: skip
        summary, document, _ = self.run_finalize(given)
        self.assertEqual([item["plan_item"] for item in document["next_month"]], ["N1"])
        self.assertIn("no client wording for the strategist's plan item N2", summary["missing"])

    def test_causes_jargon_and_unsupported_superlatives_are_flagged(self):
        given = answer(what_worked=[line("The video drove enquiries and impressions in your strongest month.", "P1")])
        checks = " | ".join(self.run_finalize(given, earlier_months=None)[1]["checks"])
        self.assertIn('claims a cause ("drove")', checks)
        self.assertIn('uses the jargon word "impressions"', checks)
        self.assertIn('compares beyond last month ("strongest month")', checks)

    def test_earlier_months_allow_a_superlative(self):
        given = answer(what_worked=[line("Your strongest month for reach.", "M:reach"), answer()["what_worked"][1]])
        self.assertNotIn("compares beyond", " ".join(self.run_finalize(given)[1]["checks"]))

    def test_a_highlight_citing_another_post_is_flagged(self):
        given = answer(highlights=[{"slot": "highest_reach", "text": "Seen by 4,000 people.", "refs": ["P2"]},
                                   *answer()["highlights"][1:]])  # fmt: skip
        checks = self.run_finalize(given)[1]["checks"]
        self.assertIn("The highest reach highlight does not cite P1, the post the report engine chose for it.", checks)

    def test_a_tile_without_a_line_is_missing(self):
        summary = self.run_finalize(answer(tiles=answer()["tiles"][:2]))[0]
        self.assertIn("no line under the enquiries tile", summary["missing"])
        self.assertIn("no line under the new followers tile", summary["missing"])


    def test_an_item_of_several_sentences_is_split_and_noted(self):
        given = answer(what_happened=[line("12,000 people saw your posts. That is 20% more than in September.", "M:reach")])
        summary, document, _ = self.run_finalize(given)
        self.assertEqual([s["text"] for s in document["summary"]["what_happened"]],
                         ["12,000 people saw your posts.", "That is 20% more than in September."])  # fmt: skip
        self.assertEqual(document["split"], [{"section": "what_happened", "number": 1, "sentences": 2}])
        self.assertIn("What happened, item 1, held 2 sentences; each keeps all of the item's references, "
                      "so check which data each one rests on.", summary["checks"])  # fmt: skip

    def test_a_short_paragraph_is_flagged(self):
        checks = self.run_finalize(answer(what_worked=answer()["what_worked"][:1]))[1]["checks"]
        self.assertIn("What worked has 1 sentence; the report asks for 2 to 4.", checks)

    def test_a_number_from_data_the_sentence_does_not_cite_is_flagged(self):
        given = answer(what_happened=[line("12,000 people saw your posts, and 300 liked them.", "M:reach"),
                                      answer()["what_happened"][1]])  # fmt: skip
        summary, document, _ = self.run_finalize(given)
        self.assertEqual(summary["status"], "complete")
        self.assertIn('"300" in What happened, sentence 1 is in the month\'s data, but not in what it '
                      "cites (M:reach); check which number it means.", document["checks"])  # fmt: skip

    def test_a_ranking_while_a_post_is_incomplete_is_flagged(self):
        given = answer(highlights=[*answer()["highlights"][:1],
                                   {"slot": "highest_engagement", "text": "The most shares and saves.", "refs": ["P1"]},
                                   *answer()["highlights"][2:]])  # fmt: skip
        checks = self.run_finalize(given)[1]["checks"]
        self.assertIn('The highest engagement highlight ranks posts ("most") while the numbers of P2 are '
                      "incomplete; say the ranking leaves it out.", checks)  # fmt: skip

    def test_internal_terms_are_flagged(self):
        given = answer(top_post=[line("The engine's pick, from complete snapshots, was seen by 8K people.", "P1")])
        checks = " | ".join(self.run_finalize(given)[1]["checks"])
        self.assertIn('uses the internal term "engine"', checks)

    def test_because_explaining_a_data_gap_is_not_a_cause(self):
        given = answer(what_happened=[answer()["what_happened"][0],
                                      line("We can't compare plays with September because its data is incomplete.",
                                           "M:video_views")])  # fmt: skip
        self.assertNotIn("claims a cause", " ".join(self.run_finalize(given)[1]["checks"]))


    def test_split_sentences_are_checked_together_for_partial_data(self):
        given = answer(what_did_not_land=[
            line("Among posts with complete data, the TikTok promo got the fewest likes. "
                 "We left out one TikTok post whose numbers are incomplete.", "P1", "P2"),
            answer()["what_did_not_land"][1]])  # fmt: skip
        checks = " | ".join(self.run_finalize(given)[1]["checks"])
        self.assertNotIn("rests on P2", checks)
        self.assertNotIn("ranks posts", checks)

    def test_a_line_that_leaves_the_partial_post_out_is_not_flagged(self):
        given = answer(highlights=[*answer()["highlights"][:2],
                                   {"slot": "best_retention", "text": "30% watched to the end; its other numbers "
                                    "are incomplete.", "refs": ["P2"]}])  # fmt: skip
        self.assertNotIn("rests on P2", " ".join(self.run_finalize(given)[1]["checks"]))

    def test_the_strongest_post_is_not_a_comparison_with_earlier_months(self):
        given = answer(what_worked=[line("It was among the strongest posts on Instagram.", "PL:instagram"),
                                    answer()["what_worked"][1]])  # fmt: skip
        checks = " ".join(self.run_finalize(given, earlier_months=None)[1]["checks"])
        self.assertNotIn("compares beyond", checks)

    def test_a_ranking_given_to_the_wrong_post_is_flagged(self):
        third = {**copy.deepcopy(EXAMPLE["posts"][0]), "content_item_id": "ci-0003", "source_file": None, "hook_used": None}
        third["snapshot"].update(reach_count=9000, likes_count=100, comments_count=5, shares_count=5,
                                 saves_count=10, true_engagement_rate=1.33)  # fmt: skip
        posts = [*EXAMPLE["posts"], third]
        given = answer(what_worked=[line("Your Instagram video reached more people than any other post.", "P1"),
                                    line("It also got the most likes.", "P1")])  # fmt: skip
        checks = self.run_finalize(given, posts=posts)[1]["checks"]
        self.assertIn("What worked, sentence 1 puts P1 first on people reached, but P3 is first among posts "
                      "with complete data; check it.", checks)  # fmt: skip
        self.assertFalse([c for c in checks if "sentence 2 puts" in c], checks)

    def test_a_reference_in_the_text_is_flagged(self):
        given = answer(top_post=[line("P1 was seen by 8K people.", "P1")])
        self.assertIn('The top post, sentence 1 shows the reference "P1" to the client; name what it is instead.',
                      self.run_finalize(given)[1]["checks"])  # fmt: skip

    def test_a_headline_must_say_that_reach_fell(self):
        totals = {**EXAMPLE["totals"], "reach": {"current": 8000, "previous": 10000, "delta_pct": -20.0}}
        given = answer(headline=line("October: 8K people reached and 6 enquiries.", "M:reach", "M:enquiries"),
                       what_happened=[line("8,000 people saw your posts, 2,000 fewer than in September.", "M:reach"),
                                      answer()["what_happened"][1]],
                       tiles=[{"metric": "reach", "text": "people saw your posts", "refs": ["M:reach"]},
                              *answer()["tiles"][1:]])  # fmt: skip
        checks = self.run_finalize(given, totals=totals)[1]["checks"]
        self.assertIn("The headline does not say that fewer people were reached (-20% on last month).", checks)


    def test_a_ranking_citing_the_leader_with_another_post_names_the_leader(self):
        # Run 4: the claim is about one post, but the line also cites the real leader.
        given = answer(what_worked=[line("Your Instagram checklist video reached more people than any other "
                                         "post with complete data.", "P1", "P2", "P3"),
                                    answer()["what_worked"][1]])  # fmt: skip
        checks = self.run_finalize(given, posts=three_posts())[1]["checks"]
        self.assertIn("What worked, sentence 1 ranks posts and cites P1, P3; among posts with complete data "
                      "the first is P3 on people reached: make sure that is the post it puts first.", checks)  # fmt: skip

    def test_a_reach_claim_beside_the_engagement_wording_is_checked(self):
        given = answer(what_worked=[
            line("It had the highest share of people reached who liked, commented on, shared or saved.", "P1"),
            line("It had the highest share of people reached who liked, commented on, shared or saved, and "
                 "reached the most people.", "P1")])  # fmt: skip
        checks = " | ".join(self.run_finalize(given, posts=three_posts())[1]["checks"])
        self.assertNotIn("What worked, sentence 1 puts", checks)
        self.assertIn("What worked, sentence 2 puts P1 first on people reached, but P3 is first", checks)

    def test_other_ranking_words_are_checked(self):
        given = answer(what_worked=[line("It topped every post for shares.", "P3"), answer()["what_worked"][1]])
        checks = " | ".join(self.run_finalize(given, posts=three_posts())[1]["checks"])
        self.assertIn("What worked, sentence 1 puts P3 first on shares, but P1 is first", checks)

    def test_measures_follow_the_wording(self):
        self.assertEqual(finalize.measures_in("the highest share of people reached who liked, commented on, "
                                              "shared or saved"), ["true_engagement_rate"])  # fmt: skip
        self.assertEqual(finalize.measures_in("the most watched to the end, and it reached 9,000 people"),
                         ["retention_complete_pct", "reach_count"])  # fmt: skip
        # A share that watched to the end is about watching, not engagement or reach.
        for wording in ("the highest share of viewers watched it to the end",
                        "the largest share of people reached watched it to the end"):  # fmt: skip
            self.assertEqual(finalize.measures_in(wording), ["retention_complete_pct"], wording)


if __name__ == "__main__":
    unittest.main()
