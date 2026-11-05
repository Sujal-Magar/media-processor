from __future__ import annotations

import unittest
from unittest import mock

from helpers import load_script

from lib import openai_api

prepare = load_script("tag-topics", "prepare")

TRANSCRIPT = {
    "complete": True, "created_at": "t-transcript",
    "source": {"name": "story.mov", "duration_seconds": 240.0},
    "parts": [
        {"index": 0, "start_seconds": 0.0, "end_seconds": 120.0, "text": "I got my visa. It took six weeks!", "missing": False},
        {"index": 1, "start_seconds": 120.0, "end_seconds": 240.0, "text": "Thank you.", "missing": False},
    ],
}  # fmt: skip
TAGS = {
    "complete": True, "created_at": "t-tags",
    "source": {"name": "story.mov", "kind": "video", "duration_seconds": 240.0},
    "tags": [
        {"label": "office", "category": "scene", "seconds": 40.0},
        {"label": "speaking to camera", "category": "activity", "seconds": 30.0},
    ],
    "on_screen_text": [
        {"text": "Subclass 500", "legibility": "clear", "ranges": [[12.0, 20.0]]},
        {"text": "Prof… Sm…", "legibility": "partial", "ranges": [[30.0, 35.0]]},
        {"text": "Guessed line", "legibility": "clear", "confirmed": False, "ranges": [[40.0, 45.0]]},
    ],
}  # fmt: skip


class BuildContextTest(unittest.TestCase):
    def test_speech_visual_and_clear_text_with_refs(self):
        context, refs, warnings = prepare.build_context(TRANSCRIPT, TAGS)
        self.assertEqual(set(refs), {"S1", "S2", "S3", "T1", "V:office", "V:speaking-to-camera"})
        self.assertEqual(refs["S3"], {"source": "speech", "start_seconds": 120.0, "end_seconds": 240.0, "sentence": 1})
        self.assertIn("[00:00:00-00:02:00]\n[S1] I got my visa.\n[S2] It took six weeks!", context)
        self.assertIn('[T1 00:00:12] "Subclass 500"', context)
        self.assertNotIn("Prof", context)
        self.assertNotIn("Guessed line", context)
        self.assertNotIn("story.mov", context)  # file names can hold people's names
        self.assertEqual(warnings, [])

    def test_speech_is_split_into_sentences_within_their_part(self):
        _, refs, _ = prepare.build_context(TRANSCRIPT, None)
        self.assertEqual(refs["S2"], {"source": "speech", "start_seconds": 0.0, "end_seconds": 120.0, "sentence": 2})

    def test_nepali_danda_ends_a_sentence(self):
        nepali = {**TRANSCRIPT, "parts": [{"start_seconds": 0.0, "end_seconds": 9.0, "text": "मेरो भिसा आयो। धन्यवाद।"}]}
        context, refs, _ = prepare.build_context(nepali, None)
        self.assertEqual(set(refs), {"S1", "S2"})
        self.assertIn("[S2] धन्यवाद।", context)

    def test_photo_without_transcript_has_no_speech(self):
        photo = {**TAGS, "source": {"kind": "image", "duration_seconds": None}}
        context, refs, _ = prepare.build_context(None, photo)
        self.assertNotIn("SPEECH", context)
        self.assertFalse(any(ref.startswith("S") for ref in refs))

    def test_text_saved_before_legibility_is_left_out_with_a_warning(self):
        old = {**TAGS, "on_screen_text": [{"text": "Subclass 500", "ranges": [[12.0, 20.0]]}]}
        context, refs, warnings = prepare.build_context(None, old)
        self.assertNotIn("Subclass 500", context)
        self.assertFalse(any(ref.startswith("T") for ref in refs))
        self.assertEqual(len(warnings), 1)
        self.assertIn("force", warnings[0])

    def test_long_transcript_is_cut_with_a_warning(self):
        with mock.patch.object(prepare, "MAX_SPEECH_CHARS", 10):
            context, refs, warnings = prepare.build_context(TRANSCRIPT, None)
        self.assertIn("I got my v", context)
        self.assertNotIn("six weeks", context)
        self.assertEqual(set(refs), {"S1"})
        self.assertEqual(len(warnings), 1)


class InputsTest(unittest.TestCase):
    def test_previous_status_outdated_when_inputs_change(self):
        inputs = {"transcript": prepare.input_record(TRANSCRIPT), "tags": prepare.input_record(TAGS)}
        self.assertEqual(prepare.previous_status({"inputs": inputs}, inputs), "already_done")
        redone = {**inputs, "tags": {"created_at": "t-tags-again", "complete": True}}
        self.assertEqual(prepare.previous_status({"inputs": inputs}, redone), "outdated")
        added = {**inputs, "transcript": None}
        self.assertEqual(prepare.previous_status({"inputs": added}, inputs), "outdated")

    def test_warnings_for_missing_and_incomplete_inputs(self):
        self.assertEqual(len(prepare.input_warnings(None, TAGS)), 1)  # video, no speech
        photo = {**TAGS, "source": {"kind": "image"}}
        self.assertEqual(prepare.input_warnings(None, photo), [])
        partial = {**TRANSCRIPT, "complete": False}
        warnings = prepare.input_warnings(partial, TAGS)
        self.assertEqual(len(warnings), 1)
        self.assertIn("transcript is incomplete", warnings[0])

    def test_visual_labels_cleaned_in_order(self):
        self.assertEqual(
            [label for label, _, _ in prepare.visual_labels(TAGS)],
            ["office", "speaking-to-camera"],
        )


class OpenAISettingsTest(unittest.TestCase):
    def test_topic_model_falls_back_to_vision_model(self):
        values = {"OPENAI_VISION_MODEL": "vision-x"}
        with mock.patch.object(openai_api, "setting", lambda name, default=None: values.get(name, default)):
            self.assertEqual(openai_api.topic_model(), "vision-x")
            values["OPENAI_TOPIC_MODEL"] = "topic-y"
            self.assertEqual(openai_api.topic_model(), "topic-y")

    def test_text_estimate_counts_other_scripts_heavier(self):
        self.assertEqual(openai_api.estimate_text_tokens("abcd" * 10), 10)
        self.assertEqual(openai_api.estimate_text_tokens("नमस्ते"), 3)


if __name__ == "__main__":
    unittest.main()
