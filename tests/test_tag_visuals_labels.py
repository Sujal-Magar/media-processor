from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from helpers import load_script

finalize = load_script("tag-visuals", "finalize")
tag = load_script("tag-visuals", "tag")
prepare = load_script("tag-visuals", "prepare")


class TagVisualsLabelsTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.dir = Path(temporary.name)

    def test_aggregate_hyphenates_and_matches_old_library_tags(self):
        plan = {
            "frames": [
                {"index": 0, "time_seconds": 0.0, "file": "a.jpg"},
                {"index": 1, "time_seconds": 5.0, "file": "b.jpg"},
            ],
            "source": {"duration_seconds": 10.0},
            "existing_tags": [{"label": "speaking to camera", "category": "activity"}],
        }
        tagged = {
            0: {"tags": [{"label": "Speaking to camera", "category": "activity", "confidence": "high"}]},
            1: {"tags": [{"label": "speaking-to-camera", "category": "activity", "confidence": "medium"}]},
        }
        [entry] = finalize.aggregate(plan, tagged)
        self.assertEqual(entry["label"], "speaking-to-camera")
        self.assertFalse(entry["new"])
        self.assertEqual(entry["frames"], [0, 1])

    def test_earlier_batches_offer_hyphenated_tags(self):
        (self.dir / "batch_000.json").write_text(json.dumps({"frames": [
            {"index": 0, "tags": [{"label": "White Shirt", "category": "object", "confidence": "high"}],
             "on_screen_text": []},
        ]}), encoding="utf-8")  # fmt: skip
        text = tag.earlier_batches_text(self.dir, [{"index": 1}])
        self.assertIn("object: white-shirt", text)

    def test_instructions_ask_for_hyphens(self):
        self.assertIn("speaking-to-camera", tag.INSTRUCTIONS)
        self.assertNotIn("speaking to camera", tag.INSTRUCTIONS)
        self.assertIn("joined by hyphens", tag.INSTRUCTIONS)

    def test_previous_tags_hyphenated_and_known_dropped(self):
        (self.dir / "tags.json").write_text(json.dumps({"tags": [
            {"label": "White Shirt", "category": "object", "frames": [0]},
            {"label": "white shirt", "category": "object", "frames": [2]},
            {"label": "office", "category": "scene", "frames": [0, 1]},
        ]}), encoding="utf-8")  # fmt: skip
        existing = [{"label": "office", "category": "scene", "uses": 2}]
        self.assertEqual(
            prepare.previous_tags(self.dir, existing),
            [{"label": "white-shirt", "category": "object", "uses": 2}],
        )


if __name__ == "__main__":
    unittest.main()
