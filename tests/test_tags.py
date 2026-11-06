from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import helpers  # noqa: F401  (repo root on sys.path)

from lib.tags import clean_label, tag_library


class CleanLabelTest(unittest.TestCase):
    def test_spaces_and_case_become_hyphens(self):
        self.assertEqual(clean_label("  Speaking  to Camera "), "speaking-to-camera")

    def test_underscores_and_repeated_hyphens(self):
        self.assertEqual(clean_label("subclass__500 -- visa"), "subclass-500-visa")

    def test_existing_hyphens_kept(self):
        self.assertEqual(clean_label("close-up"), "close-up")

    def test_only_separators_is_empty(self):
        self.assertEqual(clean_label(" - _ "), "")


class TagLibraryTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)

    def write(self, name: str, tags: list[dict], file: str = "tags.json") -> Path:
        result = self.folder / name
        result.mkdir()
        (result / file).write_text(json.dumps({"tags": tags}), encoding="utf-8")
        return result

    def test_old_spaced_and_new_hyphenated_tags_merge(self):
        self.write("a-11111111", [{"label": "speaking to camera", "category": "activity", "frames": [0, 1]}])
        self.write("b-22222222", [{"label": "speaking-to-camera", "category": "activity", "frames": [3]}])
        self.assertEqual(
            tag_library(self.folder, "tags.json", None, 10),
            [{"label": "speaking-to-camera", "category": "activity", "uses": 3}],
        )

    def test_excluded_folder_and_broken_files_skipped(self):
        own = self.write("a-11111111", [{"label": "office", "category": "scene", "frames": [0]}])
        broken = self.folder / "b-22222222"
        broken.mkdir()
        (broken / "tags.json").write_text("{not json", encoding="utf-8")
        self.assertEqual(tag_library(self.folder, "tags.json", own, 10), [])

    def test_result_without_frames_counts_once(self):
        self.write("a-11111111", [{"label": "Australia", "category": "entity"}], "topics.json")
        self.write("b-22222222", [{"label": "australia", "category": "entity"}], "topics.json")
        self.assertEqual(
            tag_library(self.folder, "topics.json", None, 10),
            [{"label": "australia", "category": "entity", "uses": 2}],
        )

    def test_limit_keeps_most_used(self):
        self.write("a-11111111", [
            {"label": "office", "category": "scene", "frames": [0, 1, 2]},
            {"label": "laptop", "category": "object", "frames": [0]},
        ])  # fmt: skip
        self.assertEqual(
            [t["label"] for t in tag_library(self.folder, "tags.json", None, 1)],
            ["office"],
        )


if __name__ == "__main__":
    unittest.main()
