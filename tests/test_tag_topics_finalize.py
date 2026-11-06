from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from helpers import load_script

finalize = load_script("tag-topics", "finalize")

REFS = {
    "S1": {"source": "speech", "start_seconds": 0.0, "end_seconds": 120.0},
    "T1": {"source": "on_screen_text", "ranges": [[12.0, 20.0]]},
    "V:office": {"source": "visual", "label": "office"},
}


class CleanAnswerTest(unittest.TestCase):
    def test_labels_cleaned_and_repeats_merged(self):
        answer = {"tags": [
            {"label": "Visa Success Story", "category": "topic", "confidence": "high", "refs": ["S1"]},
            {"label": "visa-success-story", "category": "topic", "confidence": "low", "refs": ["T1", "S1"]},
        ]}  # fmt: skip
        [tag] = finalize.clean_answer(answer, REFS, set())
        self.assertEqual(tag["label"], "visa-success-story")
        self.assertEqual(tag["confidence"], "high")
        self.assertEqual([e["ref"] for e in tag["evidence"]], ["S1", "T1"])
        self.assertEqual(tag["evidence"][0]["end_seconds"], 120.0)

    def test_refs_not_sent_are_dropped(self):
        photo_refs = {"V:office": REFS["V:office"]}
        answer = {"tags": [
            {"label": "student-testimonial", "category": "type", "confidence": "medium", "refs": ["S1"]},
            {"label": "office-life", "category": "topic", "confidence": "low", "refs": ["S1", "V:office"]},
        ]}  # fmt: skip
        [tag] = finalize.clean_answer(answer, photo_refs, set())
        self.assertEqual(tag["label"], "office-life")
        self.assertEqual([e["ref"] for e in tag["evidence"]], ["V:office"])

    def test_unknown_category_and_empty_label_dropped(self):
        answer = {"tags": [
            {"label": "the-student", "category": "person", "confidence": "high", "refs": ["S1"]},
            {"label": " - ", "category": "topic", "confidence": "high", "refs": ["S1"]},
        ]}  # fmt: skip
        self.assertEqual(finalize.clean_answer(answer, REFS, set()), [])

    def test_library_tags_not_new(self):
        answer = {"tags": [
            {"label": "Australia", "category": "entity", "confidence": "high", "refs": ["S1"]},
            {"label": "subclass 500", "category": "entity", "confidence": "high", "refs": ["T1"]},
        ]}  # fmt: skip
        tags = finalize.clean_answer(answer, REFS, {"australia"})
        self.assertEqual([(t["label"], t["new"]) for t in tags],
                         [("australia", False), ("subclass-500", True)])


class FinalizeTest(unittest.TestCase):
    def test_writes_outputs_without_the_context(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        job_dir, output_dir = root / "job", root / "out"
        (job_dir / "results").mkdir(parents=True)
        plan = {
            "version": 1, "processor": "tag-topics", "status": "ready",
            "source": {"name": "story.mov", "path": "/x/story.mov", "sha256": "0" * 64,
                       "kind": "video", "duration_seconds": 130.0},
            "inputs": {"transcript": {"created_at": "t1", "complete": True}, "tags": None},
            "options": {"model": "test-model", "reasoning_effort": "low"},
            "existing_tags": [], "visual": ["office"], "refs": REFS,
            "context": "SECRET TRANSCRIPT", "estimated_input_tokens": 100,
            "warnings": [], "output_dir": str(output_dir), "replaces": None,
            "created_at": "t2",
        }  # fmt: skip
        (job_dir / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
        (job_dir / "results" / "answer.json").write_text(json.dumps({
            "answer": {"summary": "A  student\ntalks about a visa.", "tags": [
                {"label": "Student Testimonial", "category": "type", "confidence": "high", "refs": ["S1"]},
                {"label": "made-up", "category": "topic", "confidence": "low", "refs": ["S9"]},
            ]},
            "usage": {"input_tokens": 90, "output_tokens": 40},
        }), encoding="utf-8")  # fmt: skip

        summary = finalize.finalize(job_dir, keep_work=True)

        document = json.loads((output_dir / "topics.json").read_text(encoding="utf-8"))
        self.assertEqual(document["type"], ["student-testimonial"])
        self.assertEqual(document["topic"], [])
        self.assertEqual(document["visual"], ["office"])
        self.assertEqual(document["summary"], "A student talks about a visa.")
        self.assertEqual(summary["tags"], {"type": 1, "topic": 0, "entity": 0})
        self.assertEqual(summary["tags_dropped"], 1)
        metadata = (output_dir / "metadata.json").read_text(encoding="utf-8")
        self.assertNotIn("SECRET TRANSCRIPT", metadata)
        markdown = (output_dir / "topics.md").read_text(encoding="utf-8")
        self.assertIn("speech 00:00:00-00:02:00", markdown)


class InputsLineTest(unittest.TestCase):
    def test_organisation_details_are_not_an_input_name(self):
        inputs = {"transcript": {"created_at": "t1", "complete": False}, "tags": None,
                  "organisation": {"name": "Tilicho Consulting Group"}}  # fmt: skip
        self.assertEqual(finalize.inputs_line(inputs), "transcript (incomplete)")


class EvidenceTextTest(unittest.TestCase):
    def test_speech_names_its_sentence_within_the_part(self):
        item = {"source": "speech", "start_seconds": 0.0, "end_seconds": 116.0, "sentence": 3}
        self.assertEqual(finalize.evidence_text(item), "speech 00:00:00-00:01:56, sentence 3")

    def test_speech_without_sentence_shows_only_the_part(self):
        item = {"source": "speech", "start_seconds": 0.0, "end_seconds": 120.0}
        self.assertEqual(finalize.evidence_text(item), "speech 00:00:00-00:02:00")


if __name__ == "__main__":
    unittest.main()
