from __future__ import annotations

import unittest
from unittest import mock

from helpers import load_script

from lib import openai_api

prepare = load_script("generate-copy", "prepare")

TRANSCRIPT = {
    "complete": True, "created_at": "t-transcript",
    "source": {"name": "story.mov", "duration_seconds": 48.0},
    "parts": [
        {"index": 0, "start_seconds": 0.0, "end_seconds": 30.0, "text": "SPEAKER 0: मेरो भिसा आयो। Thank you!", "missing": False},
        {"index": 1, "start_seconds": 30.0, "end_seconds": 48.0, "text": "SPEAKER 0: Contact us.", "missing": False},
    ],
}  # fmt: skip
TAGS = {
    "complete": True, "created_at": "t-tags",
    "source": {"name": "story.mov", "kind": "video", "duration_seconds": 48.0},
    "tags": [
        {"label": "office", "category": "scene", "seconds": 12.0, "ranges": [[0.0, 12.0]]},
        {"label": "speaking to camera", "category": "activity", "seconds": 30.0, "ranges": [[10.0, 40.0]]},
    ],
    "on_screen_text": [
        {"text": "Subclass 500", "legibility": "clear", "ranges": [[12.0, 20.0]]},
        {"text": "TILICHO", "legibility": "partial", "ranges": [[30.0, 32.0]]},
        {"text": "Guessed line", "legibility": "partial", "confirmed": False, "ranges": [[40.0, 45.0]]},
    ],
}  # fmt: skip
TOPICS = {
    "complete": True, "created_at": "t-topics",
    "summary": "A student shares a visa success.",
    "type": ["student-testimonial"], "topic": ["australia-student-visa"], "entity": ["subclass-500"],
}  # fmt: skip
ORGANISATION = {"name": "Tilicho Consulting Group", "other_names": ["Tilicho"],
                "website": "", "hashtags": [], "note": ""}  # fmt: skip


def options(**changes):
    values = {"platforms": None, "language": None, "translate": None, "tone": None, "brief": None}
    return prepare.request_options(**{**values, **changes})


class RequestOptionsTest(unittest.TestCase):
    def test_defaults(self):
        self.assertEqual(
            options(),
            {"platforms": ["instagram-reels", "tiktok", "linkedin"], "language": "English",
             "translate": None, "tone": None, "brief": None},
        )  # fmt: skip

    def test_language_codes_become_names_and_platforms_are_cleaned(self):
        chosen = options(platforms="LinkedIn, tiktok,linkedin", language="en", translate="ne")
        self.assertEqual(chosen["platforms"], ["linkedin", "tiktok"])
        self.assertEqual(chosen["translate"], "Nepali")

    def test_unknown_platform_fails(self):
        with self.assertRaises(SystemExit):
            options(platforms="myspace")

    def test_translation_into_the_copy_language_fails(self):
        with self.assertRaises(SystemExit):
            options(language="Nepali", translate="ne")

    def test_overlong_brief_fails(self):
        with self.assertRaises(SystemExit):
            options(brief="x" * (prepare.MAX_BRIEF_CHARS + 1))


class BuildMaterialTest(unittest.TestCase):
    def test_speech_visuals_screen_text_topics_and_organisation(self):
        context, refs, warnings = prepare.build_material(TRANSCRIPT, TAGS, TOPICS, ORGANISATION)
        self.assertEqual(refs["S1"]["text"], "मेरो भिसा आयो।")
        self.assertEqual(refs["S1"]["speaker"], "SPEAKER 0")
        self.assertEqual(refs["V:speaking-to-camera"]["ranges"], [[10.0, 40.0]])
        self.assertEqual(refs["T1"]["text"], "Subclass 500")
        self.assertIn('PARTLY READ ON-SCREEN TEXT', context)
        self.assertIn('- "TILICHO"', context)
        self.assertNotIn("Guessed line", context)  # unconfirmed text may be invented
        self.assertIn("TOPIC TAGS", context)
        self.assertIn("topic: australia-student-visa", context)
        self.assertIn("Name: Tilicho Consulting Group", context)
        self.assertNotIn("story.mov", context)  # file names can hold people's names
        self.assertEqual(warnings, [])

    def test_without_topics_or_organisation_neither_section_is_sent(self):
        context, _, _ = prepare.build_material(TRANSCRIPT, TAGS, None, None)
        self.assertNotIn("TOPIC TAGS", context)
        self.assertNotIn("ORGANISATION", context)


class StatusTest(unittest.TestCase):
    def setUp(self):
        self.inputs = prepare.input_records(TRANSCRIPT, TAGS, TOPICS, ORGANISATION)
        self.done = {"inputs": self.inputs, "options": {**options(tone="warm", brief="Promote us"), "model": "m"}}

    def test_same_inputs_and_request_is_done(self):
        request = options(tone="warm", brief="Promote us")
        self.assertEqual(prepare.previous_status(self.done, self.inputs, request), "already_done")

    def test_new_inputs_or_organisation_are_outdated(self):
        redone = {**self.inputs, "topics": None}
        self.assertEqual(prepare.previous_status(self.done, redone, options()), "outdated")
        renamed = {**self.inputs, "organisation": {**ORGANISATION, "name": "Other"}}
        self.assertEqual(prepare.previous_status(self.done, renamed, options()), "outdated")

    def test_other_request_names_what_changed_including_a_dropped_brief(self):
        request = options(tone="playful")
        self.assertEqual(prepare.previous_status(self.done, self.inputs, request), "different_options")
        self.assertEqual(
            prepare.changed_options(self.done, request),
            {"tone": {"saved": "warm", "requested": "playful"},
             "brief": {"saved": "Promote us", "requested": None}},
        )  # fmt: skip


class ReadySummaryTest(unittest.TestCase):
    def test_every_line_every_time(self):
        inputs = prepare.input_records(TRANSCRIPT, TAGS, None, None)
        chosen = {**options(platforms="linkedin,tiktok", tone="warm"), "model": "m", "reasoning_effort": "low"}
        lines = prepare.ready_summary(inputs, chosen, 2961, None, [])
        self.assertEqual(len(lines), 7)
        self.assertEqual(lines[0], "Inputs read: transcript yes, visual tags yes, topic tags no")
        self.assertEqual(lines[1], "Organisation: none (no organisation.json)")
        self.assertIn("LinkedIn, TikTok; written in English; translation: none", lines[2])
        self.assertEqual(lines[3], "Tone: warm; brief: none")
        self.assertIn("about 2,961 input tokens", lines[4])
        self.assertEqual(lines[5:], ["Replaces: nothing", "Warnings: none"])


class WarningsTest(unittest.TestCase):
    def test_missing_topics_organisation_and_incomplete_inputs(self):
        warnings = prepare.input_warnings({**TRANSCRIPT, "complete": False}, TAGS, None, None)
        self.assertEqual(len(warnings), 3)
        joined = " ".join(warnings)
        self.assertIn("incomplete", joined)
        self.assertIn("/tag-topics", joined)
        self.assertIn("organisation.json", joined)

    def test_one_part_transcript_says_soundbite_times_cover_it_all(self):
        one = {**TRANSCRIPT, "parts": TRANSCRIPT["parts"][:1]}
        warnings = prepare.input_warnings(one, TAGS, TOPICS, ORGANISATION)
        self.assertEqual(len(warnings), 1)
        self.assertIn("00:00:00-00:00:30", warnings[0])

    def test_silent_video_has_no_soundbites(self):
        silent = {**TRANSCRIPT, "parts": [{"start_seconds": 0.0, "end_seconds": 48.0, "text": ""}]}
        warnings = prepare.input_warnings(silent, TAGS, TOPICS, ORGANISATION)
        self.assertEqual(len(warnings), 1)
        self.assertIn("no speech", warnings[0])

    def test_complete_inputs_have_no_warnings(self):
        self.assertEqual(prepare.input_warnings(TRANSCRIPT, TAGS, TOPICS, ORGANISATION), [])


class CopyModelTest(unittest.TestCase):
    def test_copy_model_falls_back_to_vision_model(self):
        values = {"OPENAI_VISION_MODEL": "vision-x"}
        with mock.patch.object(openai_api, "setting", lambda name, default=None: values.get(name, default)):
            self.assertEqual(openai_api.copy_model(), "vision-x")
            values["OPENAI_COPY_MODEL"] = "copy-y"
            self.assertEqual(openai_api.copy_model(), "copy-y")


if __name__ == "__main__":
    unittest.main()
