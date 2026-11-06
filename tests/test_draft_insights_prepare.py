from __future__ import annotations

import contextlib
import copy
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import ROOT, load_script

prepare = load_script("draft-insights", "prepare")

TRIGGERS = json.loads((ROOT / "fixtures" / "insights-input.example.json").read_text(encoding="utf-8"))
REPORT = json.loads((ROOT / "fixtures" / "report-input.example.json").read_text(encoding="utf-8"))


def read(**changes):
    """The example triggers with top-level changes, read as prepare reads a file."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "2026-10.json"
        path.write_text(json.dumps({**copy.deepcopy(TRIGGERS), **changes}), encoding="utf-8")
        return prepare.read_triggers(path)


def window(triggers=None, reports=None):
    """load_window over a folder of report inputs ({"2026-10": data, ...})."""
    reports = reports or {"2026-10": REPORT}
    with tempfile.TemporaryDirectory() as folder:
        for name, data in reports.items():
            (Path(folder) / f"{name}.json").write_text(json.dumps(data), encoding="utf-8")
        return prepare.load_window(triggers or read(), Path(folder))


def post(item, platform="instagram", pillar="Educational", language="en", source=None, **snapshot):
    values = {"true_engagement_rate": None, "reach_count": None, "retention_3s_pct": None,
              "retention_10s_pct": None, "retention_complete_pct": None,
              "data_quality_flag": "Full", **snapshot}  # fmt: skip
    return {"content_item_id": item, "platform": platform, "content_pillar": pillar,
            "language": language, "source_file": source, "published_at": "2026-10-01",
            "snapshot": values}  # fmt: skip


class ReadTriggersTest(unittest.TestCase):
    def test_the_example_reads(self):
        triggers = read()
        self.assertEqual(triggers["month_period"], "2026-10")
        self.assertEqual(triggers["baseline"]["window_days"], 90)
        self.assertEqual(triggers["quota"], {"monthly_posts": 16, "published": 2})
        self.assertEqual([t["rule"] for t in triggers["triggers"]],
                         ["engagement_gt_200pct_mean", "hook_dropoff_gt_45pct", "pace_behind_quota"])  # fmt: skip

    def test_bad_shapes_stop_with_an_error(self):
        baseline = TRIGGERS["baseline"]
        cases = {
            "month": {"month_period": "2026-13"},
            "unknown rule": {"triggers": [{"trigger_rule_id": "views_up", "content_item_id": "ci-0001"}]},
            "post rule without a post": {"triggers": [{"trigger_rule_id": "hook_dropoff_gt_45pct", "content_item_id": None}]},
            "pace with a post": {"triggers": [{"trigger_rule_id": "pace_behind_quota", "content_item_id": "ci-0001"}]},
            "repeated": {"triggers": [TRIGGERS["triggers"][0], TRIGGERS["triggers"][0]]},
            "window length": {"baseline": {**baseline, "window_days": 30}},
            "window outside the month": {"baseline": {**baseline, "window_start": "2026-07-03", "window_end": "2026-09-30"}},
            "no average": {"baseline": {**baseline, "engagement_rate_mean": 0}},
            "negative quota": {"quota": {"monthly_posts": 16, "published": -1}},
            "no quota": {"quota": None},
        }  # fmt: skip
        for name, changes in cases.items():
            with self.subTest(name), self.assertRaises(SystemExit):
                read(**changes)


class LoadWindowTest(unittest.TestCase):
    def test_posts_come_from_every_month_in_the_window(self):
        september = copy.deepcopy(REPORT)
        september.update(month_period="2026-09", previous_month="2026-08", highlights={})
        september.pop("next_month_plan")
        september.pop("earlier_months")
        for n, item in enumerate(september["posts"]):
            item.update(content_item_id=f"ci-09{n}", published_at=f"2026-09-0{n + 1}")
        july = {**copy.deepcopy(september), "month_period": "2026-07", "previous_month": "2026-06"}
        for item in july["posts"]:
            item["content_item_id"] += "-jul"
        month, posts, files = window(reports={"2026-10": REPORT, "2026-09": september, "2026-07": july})
        self.assertEqual(month["month_period"], "2026-10")
        self.assertEqual([p["content_item_id"] for p in posts], ["ci-090", "ci-091", "ci-0001", "ci-0002"])
        self.assertEqual(sorted(files), ["2026-09.json", "2026-10.json"])

    def test_the_month_s_report_input_is_needed(self):
        with self.assertRaises(SystemExit):
            window(reports={"2026-09": REPORT})


class CheckTriggersTest(unittest.TestCase):
    def test_the_example_sends_two_and_holds_back_the_partial_post(self):
        triggers = read()
        month, _, _ = window(triggers)
        sent, held = prepare.check_triggers(triggers, month)
        first = {key: sent[0][key] for key in ("rule", "content_item_id", "value", "times", "threshold", "bar")}
        self.assertEqual(first, {"rule": "engagement_gt_200pct_mean", "content_item_id": "ci-0001",
                                 "value": 5.0, "times": 2.1, "threshold": 4.8, "bar": 2.4})  # fmt: skip
        self.assertEqual(sent[0]["card"], "A bigger share of the people who saw your English Instagram video "
                                          "liked, commented on, shared or saved it: 2.1× your usual.")  # fmt: skip
        self.assertEqual((sent[1]["behind"], sent[1]["quantity"]), (14, 3))
        self.assertEqual(sent[1]["card"], "We posted 2 of the 16 posts planned for October.")
        self.assertEqual(len(held), 1)
        self.assertEqual(held[0]["content_item_id"], "ci-0002")
        self.assertIn("Partial", held[0]["reason"])

    def test_a_trigger_the_numbers_do_not_bear_out_stops(self):
        baseline = {**TRIGGERS["baseline"], "engagement_rate_mean": 3.0}  # 2 x 3.0 is above 5.0
        cases = {
            "engagement": {"baseline": baseline},
            "pace": {"quota": {"monthly_posts": 3, "published": 2}},
            "unknown post": {"triggers": [{"trigger_rule_id": "hook_dropoff_gt_45pct", "content_item_id": "ci-9"}]},
        }
        for name, changes in cases.items():
            triggers = read(**changes)
            month, _, _ = window(triggers)
            with self.subTest(name), self.assertRaises(SystemExit):
                prepare.check_triggers(triggers, month)

    def test_a_drop_off_is_100_minus_the_share_still_watching(self):
        report = copy.deepcopy(REPORT)
        report["posts"][0]["snapshot"]["retention_3s_pct"] = 48.0
        triggers = read(triggers=[{"trigger_rule_id": "hook_dropoff_gt_45pct", "content_item_id": "ci-0001"}])
        month, _, _ = window(triggers, {"2026-10": report})
        sent, _ = prepare.check_triggers(triggers, month)
        self.assertEqual(sent[0]["dropoff"], 52.0)

    def test_more_than_three_are_held_back(self):
        month = copy.deepcopy(REPORT)
        extra = []
        for n in range(3):
            item = copy.deepcopy(REPORT["posts"][0])
            item["content_item_id"] = f"ci-10{n}"
            item["snapshot"]["retention_3s_pct"] = 40.0
            month["posts"].append(item)
            extra.append({"trigger_rule_id": "hook_dropoff_gt_45pct", "content_item_id": f"ci-10{n}"})
        triggers = read(triggers=[TRIGGERS["triggers"][0], *extra])
        read_month, _, _ = window(triggers, {"2026-10": month})
        sent, held = prepare.check_triggers(triggers, read_month)
        self.assertEqual(len(sent), 3)
        self.assertEqual([h["content_item_id"] for h in held], ["ci-102"])
        self.assertIn("limit of 3", held[0]["reason"])


class RuleWarningsTest(unittest.TestCase):
    def test_a_post_the_rules_should_have_flagged_is_warned(self):
        triggers = read(triggers=[])
        month, posts, _ = window(triggers)
        warnings = " | ".join(prepare.rule_warnings(triggers, month, posts))
        self.assertIn("ci-0001 has an engagement rate above 2 × the average, but no trigger", warnings)
        self.assertIn("behind the quota, but has no pace trigger", warnings)
        self.assertIn("The baseline counts 12 posts in the window; input/reports/ holds 2", warnings)


class ComparisonsTest(unittest.TestCase):
    PACE = [{"rule": "pace_behind_quota", "content_item_id": None, "behind": 4}]

    def test_each_side_needs_two_posts(self):
        posts = [post("a", true_engagement_rate=6.0), post("b", true_engagement_rate=5.0),
                 post("c", pillar="Promo", true_engagement_rate=2.0)]  # fmt: skip
        self.assertEqual(prepare.comparisons(posts, {}, self.PACE), [])

    def test_a_group_is_compared_with_the_rest(self):
        posts = [post("a", true_engagement_rate=6.0), post("b", true_engagement_rate=4.0),
                 post("c", pillar="Promo", true_engagement_rate=2.0),
                 post("d", pillar="Promo", true_engagement_rate=3.0)]  # fmt: skip
        found = prepare.comparisons(posts, {}, self.PACE)
        self.assertEqual(len(found), 1)  # Promo vs Educational only swaps the sides
        item = found[0]
        self.assertEqual((item["group"], item["rest"]), ("Educational posts", "posts in other pillars"))
        self.assertEqual((item["mean"], item["other_mean"], item["times"], item["difference_pct"]), (5.0, 2.5, 2.0, 100))
        self.assertIn("Educational posts (2 posts) vs posts in other pillars (2 posts), engagement rate: "
                      "average 5% vs 2.5%; 2× (100% higher)", prepare.comparison_text(item))  # fmt: skip

    def test_groups_with_the_same_posts_are_named_together(self):
        posts = [post("a", platform="tiktok", language="ne", true_engagement_rate=6.0),
                 post("b", platform="tiktok", language="ne", true_engagement_rate=4.0),
                 post("c", true_engagement_rate=2.0), post("d", true_engagement_rate=3.0)]  # fmt: skip
        found = prepare.comparisons(posts, {}, self.PACE)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["group"], "tiktok posts (the same posts as posts in Nepali)")
        self.assertEqual(found[0]["rest"], "the other posts")

    def test_a_trigger_s_comparisons_are_its_post_s_groups_without_it(self):
        posts = [post("a", true_engagement_rate=9.0), post("b", true_engagement_rate=4.0),
                 post("e", true_engagement_rate=5.0), post("c", pillar="Promo", true_engagement_rate=2.0),
                 post("d", pillar="Promo", true_engagement_rate=3.0)]  # fmt: skip
        outlier = [{"rule": "engagement_gt_200pct_mean", "content_item_id": "a"}]
        found = prepare.comparisons(posts, {}, outlier)
        self.assertEqual([(c["group"], c["posts"], c["without"]) for c in found],
                         [("Educational posts", ["b", "e"], ["a"])])  # never the Promo group  # fmt: skip
        drop = [{"rule": "hook_dropoff_gt_45pct", "content_item_id": "a"}]
        self.assertEqual(prepare.comparisons(posts, {}, drop), [])  # no retention numbers


class BuildContextTest(unittest.TestCase):
    def setUp(self):
        self.triggers = read()
        self.month, window_posts, _ = window(self.triggers)
        self.sent, _ = prepare.check_triggers(self.triggers, self.month)
        self.posts = [p for p in window_posts if prepare.full(p)]
        self.context, self.refs, self.allowed, self.general = prepare.build_context(
            self.triggers, self.month, self.posts, self.sent, [], {}, None, [1, 2, 3]
        )

    def test_triggers_baseline_and_complete_posts_are_referenced(self):
        self.assertEqual(sorted(self.refs), ["BL", "P1", "T1", "T2"])
        self.assertEqual(self.refs["T1"]["post"], "P1")
        self.assertIn("[T1] engagement rate above 2 × the 90-day average: P1: engagement rate 5%, 2.1× the "
                      "90-day average of 2.4%", self.context)  # fmt: skip
        self.assertIn("[T2] 2 or more posts behind the monthly quota: 2 of the 16 posts", self.context)
        self.assertIn("A request may ask for 1, 2 or 3 items", self.context)

    def test_the_partial_post_is_left_out(self):
        self.assertNotIn("ci-0002", json.dumps(self.refs))
        self.assertNotIn("tiktok", self.context.split("POSTS IN THE BASELINE WINDOW")[1].split("BRAND")[0])

    def test_each_reference_keeps_its_numbers(self):
        self.assertEqual(self.refs["T1"]["numbers"], [2.0, 2.1, 2.4, 4.8, 5.0])
        self.assertEqual(self.refs["T2"]["numbers"], [2.0, 3.0, 14.0, 16.0])
        self.assertIn(8000.0, self.refs["P1"]["numbers"])
        self.assertEqual(self.general, [3.0, 10.0, 90.0, 2026.0])

    def test_no_comparison_is_said_plainly(self):
        self.assertIn("- none: no group has enough posts", self.context)
        self.assertEqual(self.context.count("no comparison bears on this trigger"), 1)  # T1, not the pace T2


class VideoEvidenceTest(unittest.TestCase):
    def test_every_visual_tag_groups_a_video_and_the_longest_seen_are_shown(self):
        tied = [{"label": name, "category": "object", "seconds": 48.0} for name in "abcdefghi"]
        tags = {"tags": [*tied, {"label": "speaking-to-camera", "category": "activity", "seconds": 48.0},
                         {"label": "zoom", "category": "object", "seconds": 60.0}]}  # fmt: skip
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "talk.mov").write_bytes(b"video")
            result = Path(folder) / "result"
            result.mkdir()
            (result / "tags.json").write_text(json.dumps(tags), encoding="utf-8")
            item = {**post("a", source="talk.mov"), "hook_used": None}
            with mock.patch.object(prepare, "output_dir_for", lambda *a: result):
                materials, _, _ = prepare.gather_materials([item], {"a": "P1"}, Path(folder))
        material = materials["a"]
        self.assertIn("speaking-to-camera", material["visual"])  # sorts 10th of 11
        self.assertEqual(material["visual_shown"][:2], ["zoom", "speaking-to-camera"])  # activity before objects
        self.assertEqual(len(material["visual_shown"]), min(prepare.MAX_VISUAL_TAGS, 11))
        self.assertIn("speaking-to-camera", prepare.attributes(item, material)["visual"])

    def test_a_video_posted_twice_is_one_piece_of_content(self):
        posts = [post("a", source="v1.mov", true_engagement_rate=6.0),
                 post("b", platform="tiktok", source="v1.mov", true_engagement_rate=5.0),
                 post("c", pillar="Promo", true_engagement_rate=2.0),
                 post("d", pillar="Promo", true_engagement_rate=3.0)]  # fmt: skip
        pace = [{"rule": "pace_behind_quota", "content_item_id": None, "behind": 4}]
        pillar = [c for c in prepare.comparisons(posts, {}, pace) if c["kind"] == "pillar"]
        self.assertEqual(pillar, [])  # the Educational side is one video
        posts.append(post("e", true_engagement_rate=4.0))
        found = [c for c in prepare.comparisons(posts, {}, pace) if c["kind"] == "pillar"]
        self.assertEqual((found[0]["pieces"], len(found[0]["posts"])), (2, 3))
        self.assertIn("Educational posts (3 posts of 2 pieces of content)", prepare.comparison_text(found[0]))

    def test_the_flagged_post_and_its_twin_are_left_out(self):
        posts = [post("a", source="v1.mov", true_engagement_rate=9.0),
                 post("b", platform="tiktok", source="v1.mov", true_engagement_rate=8.0),
                 post("c", true_engagement_rate=5.0), post("f", true_engagement_rate=4.0),
                 post("d", pillar="Promo", true_engagement_rate=2.0),
                 post("g", pillar="Promo", true_engagement_rate=3.0)]  # fmt: skip
        sent = [{"rule": "engagement_gt_200pct_mean", "content_item_id": "b"}]
        found = [c for c in prepare.comparisons(posts, {}, sent) if c["kind"] == "pillar"]
        self.assertEqual((found[0]["posts"], found[0]["without"]), (["c", "f"], ["a", "b"]))
        ids = {i: f"P{n}" for n, i in enumerate("abcfdg", 1)}
        self.assertEqual(prepare.without_text(found[0], ids), "; worked out without the flagged post (P1, P2)")


class OutdatedTopicsTest(unittest.TestCase):
    def warnings_for(self, made_from):
        """gather_materials' warnings when topics.json was made from visual tags of
        `made_from` and the saved tags.json is from "new"."""
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "talk.mov").write_bytes(b"video")
            result = Path(folder) / "result"
            result.mkdir()
            (result / "tags.json").write_text(json.dumps({"created_at": "new", "tags": []}), encoding="utf-8")
            inputs = {"transcript": None, "tags": {"created_at": made_from, "complete": False}, "organisation": None}
            (result / "topics.json").write_text(json.dumps({"inputs": inputs}), encoding="utf-8")
            item = {**post("a", source="talk.mov"), "hook_used": None}
            with mock.patch.object(prepare, "output_dir_for", lambda *a: result):
                return " | ".join(prepare.gather_materials([item], {"a": "P1"}, Path(folder))[2])

    def test_topic_tags_made_from_older_results_are_warned(self):
        self.assertIn("The topic tags of talk.mov are outdated", self.warnings_for("old"))
        self.assertNotIn("outdated", self.warnings_for("new"))


class MainTest(unittest.TestCase):
    def test_nothing_left_to_send_costs_nothing(self):
        triggers = read(triggers=[TRIGGERS["triggers"][1]])  # the Partial post only
        month, posts, files = window(triggers)
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "2026-10.json"
            source.write_text(json.dumps(TRIGGERS), encoding="utf-8")
            with mock.patch.object(prepare, "read_triggers", return_value=triggers), \
                 mock.patch.object(prepare, "load_window", return_value=(month, posts, files)), \
                 mock.patch.object(prepare, "new_job_dir") as job, \
                 mock.patch.object(sys, "argv", ["prepare.py", str(source)]), contextlib.redirect_stdout(out):  # fmt: skip
                prepare.main()
        result = json.loads(out.getvalue())
        self.assertEqual(result["status"], "nothing_to_send")
        self.assertEqual(len(result["held_back"]), 1)
        job.assert_not_called()


if __name__ == "__main__":
    unittest.main()
