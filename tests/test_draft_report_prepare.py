from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import ROOT, load_script

prepare = load_script("draft-report", "prepare")

EXAMPLE = json.loads((ROOT / "fixtures" / "report-input.example.json").read_text(encoding="utf-8"))


def month(**changes):
    """The example input with top-level changes, read as prepare reads a file."""
    data = {**copy.deepcopy(EXAMPLE), **changes}
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "2026-10.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return prepare.read_month(path)


def with_post(index, **changes):
    posts = copy.deepcopy(EXAMPLE["posts"])
    posts[index].update(changes)
    return posts


class ReadMonthTest(unittest.TestCase):
    def test_the_example_reads(self):
        read = month()
        self.assertEqual(read["month_period"], "2026-10")
        self.assertEqual(read["previous_month"], "2026-09")
        self.assertIsNone(read["totals"]["link_clicks"])
        self.assertIsNone(read["totals"]["enquiries"]["delta_pct"])
        self.assertEqual(read["posts"][1]["snapshot"]["data_quality_flag"], "Partial")
        self.assertIsNone(read["posts"][1]["snapshot"]["shares_count"])

    def test_bad_shapes_stop_with_an_error(self):
        snapshot = copy.deepcopy(EXAMPLE["posts"][0]["snapshot"])
        cases = {
            "month": {"month_period": "2026-13"},
            "previous month": {"previous_month": "2026-08"},
            "unknown metric": {"totals": {"impressions": None}},
            "platform": {"posts": with_post(0, platform="facebook")},
            "highlight": {"highlights": {"highest_reach": "ci-9999"}},
            "hook without file": {"posts": with_post(1, hook_used=1)},
            "file in a folder": {"posts": with_post(0, source_file="../secret.mov")},
            "negative count": {"posts": with_post(0, snapshot={**snapshot, "likes_count": -1})},
            "no quality flag": {"posts": with_post(0, snapshot={**snapshot, "data_quality_flag": None})},
            "repeated id": {"posts": [EXAMPLE["posts"][0], EXAMPLE["posts"][0]]},
            "later earlier month": {"earlier_months": [{"month_period": "2026-11"}]},
        }
        for name, changes in cases.items():
            with self.subTest(name), self.assertRaises(SystemExit):
                month(**changes)


class DataWarningsTest(unittest.TestCase):
    def test_partial_data_and_parts_left_out_are_warned(self):
        warnings = " | ".join(prepare.data_warnings(month(next_month_plan=[], earlier_months=[])))
        self.assertIn("P2 (tiktok, 2026-10-10) has Partial data", warnings)
        self.assertIn("Not tracked, so not written about: link clicks", warnings)
        self.assertIn("No next-month plan", warnings)
        self.assertIn("No earlier months", warnings)

    def test_numbers_that_do_not_add_up_are_warned(self):
        snapshot = {**EXAMPLE["posts"][0]["snapshot"], "true_engagement_rate": 7.0}
        totals = {**EXAMPLE["totals"], "reach": {"current": 12000, "previous": 10000, "delta_pct": 25.0}}
        warnings = " | ".join(prepare.data_warnings(month(posts=with_post(0, snapshot=snapshot), totals=totals)))
        self.assertIn("P1's true_engagement_rate is 7.0, but its counts give 5.00", warnings)
        self.assertIn("totals.reach.delta_pct is 25.0, but its numbers give 20.00", warnings)

    def test_the_example_adds_up(self):
        warnings = prepare.data_warnings(month())
        self.assertFalse([w for w in warnings if "but its" in w], warnings)


class BuildContextTest(unittest.TestCase):
    def setUp(self):
        materials = {"ci-0001": {
            "topics": {"type": ["educational-advice"], "topic": ["student-visa"], "entity": ["subclass-500"],
                       "summary": "Advice on a student visa."},
            "hook": {"text": "Is this your first visa?", "style": "question"},
        }}  # fmt: skip
        organisation = {"name": "Example Consulting", "other_names": [], "website": "",
                        "hashtags": [], "note": ""}  # fmt: skip
        self.context, self.refs, self.allowed, self.general = prepare.build_context(month(), materials, organisation)

    def test_only_tracked_metrics_get_a_reference(self):
        self.assertIn("M:reach", self.refs)
        self.assertNotIn("M:link_clicks", self.refs)
        self.assertIn("- link clicks: not tracked", self.context)

    def test_a_held_back_change_is_said_and_gives_no_difference(self):
        line = next(l for l in self.context.splitlines() if l.startswith("[M:enquiries]"))
        self.assertIn("enquiries: 6; September 2026: 4; change not shown", line)
        self.assertNotIn("difference", line)

    def test_posts_carry_their_quality_topics_and_hook(self):
        self.assertEqual(self.refs["P2"]["data_quality_flag"], "Partial")
        self.assertIn("call them incomplete", self.context)
        self.assertIn("shares not recorded", self.context)
        self.assertIn("topic tags (made by a model from the video; themes, not facts): type "
                      "educational-advice; topic student-visa; entity subclass-500", self.context)  # fmt: skip
        self.assertIn('opening hook used (question): "Is this your first visa?"', self.context)
        self.assertIn("title (may name a person: never repeat a name)", self.context)

    def test_the_plan_is_numbered_for_rewording(self):
        self.assertEqual(self.refs["N2"], {"source": "plan", "text": "One post a week on TikTok.",
                                           "label": "One post a week on TikTok.", "numbers": []})  # fmt: skip
        self.assertIn("STRATEGIST'S PLAN FOR NOVEMBER 2026", self.context)

    def test_allowed_numbers_hold_the_data_differences_counts_and_years(self):
        for value in (12000, 10000, 20.0, 2000, 6, 4, 8000, 5.0, 300, 2, 1, 2026, 500):
            self.assertIn(float(value), self.allowed, value)
        self.assertNotIn(-1.0, self.allowed)

    def test_each_reference_carries_its_own_numbers(self):
        self.assertEqual(self.refs["M:reach"]["numbers"], [20.0, 2000.0, 9000.0, 10000.0, 12000.0])
        self.assertIn(8000.0, self.refs["P1"]["numbers"])
        self.assertNotIn(8000.0, self.refs["M:reach"]["numbers"])
        self.assertIn(500.0, self.refs["P1"]["numbers"])  # from its topic tags
        self.assertEqual(self.refs["N1"]["numbers"], [2.0])  # "Two more ..."
        for value in (2026, 2, 1):  # the year and post counts belong to no reference
            self.assertIn(float(value), self.general)

    def test_highlights_say_they_were_chosen_with_incomplete_numbers(self):
        self.assertIn("chosen while the numbers of P2 are incomplete", self.context)

    def test_leaders_rank_only_posts_with_complete_data(self):
        third = {**copy.deepcopy(EXAMPLE["posts"][0]), "content_item_id": "ci-0003", "source_file": None, "hook_used": None}
        third["snapshot"].update(reach_count=9000, retention_complete_pct=25.0)
        found = prepare.leaders(month(posts=[*EXAMPLE["posts"], third]))
        self.assertEqual(found["reach_count"]["most"], ["P3"])  # P2 is Partial
        self.assertEqual(found["reach_count"]["fewest"], ["P1"])
        self.assertEqual(found["retention_complete_pct"]["most"], ["P1", "P3"])  # a tie keeps both
        self.assertEqual(prepare.leaders(month()), {})  # one complete post: nothing to rank
        context = prepare.build_context(month(), {}, None)[0]
        self.assertIn("left out because their data is incomplete: P2", context)
        self.assertIn("fewer than two posts have complete data: rank no posts", context)

    def test_a_video_posted_twice_is_one_video(self):
        second = {**copy.deepcopy(EXAMPLE["posts"][0]), "content_item_id": "ci-0003", "platform": "tiktok"}
        second["snapshot"]["platform"] = "tiktok"
        context, _, _, _ = prepare.build_context(month(posts=[*EXAMPLE["posts"], second]), {}, None)
        self.assertIn("[P3] tiktok video", context)
        self.assertIn("same video as P1, posted again on tiktok: one video, not two", context)

    def test_without_a_plan_or_earlier_months_the_material_says_so(self):
        context, refs, _, _ = prepare.build_context(month(next_month_plan=None, earlier_months=None), {}, None)
        self.assertIn("not written yet. Leave next_month empty", context)
        self.assertIn("EARLIER MONTHS: none given", context)
        self.assertFalse([ref for ref in refs if ref.startswith("N")])
        self.assertNotIn("ORGANISATION", context)

    def test_an_image_post_counts_times_shown_not_plays(self):
        posts = with_post(1, snapshot={**EXAMPLE["posts"][1]["snapshot"], "retention_3s_pct": None,
                                       "retention_10s_pct": None, "retention_complete_pct": None})  # fmt: skip
        context, _, _, _ = prepare.build_context(month(posts=posts), {}, None)
        self.assertIn("[P2] tiktok post", context)
        self.assertIn("times shown 3,000", context)


class GatherMaterialsTest(unittest.TestCase):
    def test_topics_and_the_hook_used_come_from_earlier_results(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "interview.mov").write_bytes(b"video")
            results = root / "results"

            def result_dir(processor, source, digest):
                return results / processor

            (results / "tag-topics").mkdir(parents=True)
            (results / "tag-topics" / "topics.json").write_text(json.dumps({"created_at": "t1", "complete": True, "type": ["x"]}))
            (results / "generate-copy").mkdir()
            (results / "generate-copy" / "copy.json").write_text(json.dumps(
                {"created_at": "t2", "complete": True, "hooks": [{"text": "First hook", "style": "story"}]}))  # fmt: skip
            with mock.patch.object(prepare, "output_dir_for", result_dir):
                materials, records, warnings = prepare.gather_materials(month(), root)
        self.assertEqual(materials["ci-0001"]["hook"], {"text": "First hook", "style": "story"})
        self.assertEqual(records["ci-0001"]["topics"], {"created_at": "t1", "complete": True})
        self.assertEqual(warnings, [])

    def test_a_missing_file_or_hook_is_warned_and_left_out(self):
        with tempfile.TemporaryDirectory() as folder:
            materials, _, warnings = prepare.gather_materials(month(), Path(folder))
            self.assertEqual(materials, {})
            self.assertIn("interview.mov is not in input/", warnings[0])
            (Path(folder) / "interview.mov").write_bytes(b"video")
            with mock.patch.object(prepare, "output_dir_for", lambda *a: Path(folder) / "none"):
                materials, _, warnings = prepare.gather_materials(month(), Path(folder))
        self.assertIsNone(materials["ci-0001"]["hook"])
        self.assertIn("used hook 1 of interview.mov, but its copy has 0 hooks (no /generate-copy result)", warnings[0])
        self.assertIn("No topic tags for interview.mov (P1)", warnings[1])


class ReadySummaryTest(unittest.TestCase):
    def test_every_line_is_there(self):
        read = month()
        options = {"model": "test-model", "reasoning_effort": "low"}
        lines = prepare.ready_summary(read, {}, None, options, 1234, None, ["a warning"])
        self.assertEqual(lines[0], "Month: October 2026, compared with September 2026")
        self.assertIn("Incomplete data: P2 (tiktok, Partial)", lines)
        self.assertIn("Next-month plan: 2 items from the strategist", lines)
        self.assertIn("about 1,234 input tokens", lines[7])
        self.assertEqual(lines[-1], "Warnings: a warning")


if __name__ == "__main__":
    unittest.main()
