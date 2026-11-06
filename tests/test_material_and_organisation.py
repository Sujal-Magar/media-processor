from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import helpers  # noqa: F401  (the repo root on sys.path)

from lib import material, organisation

TRANSCRIPT = {
    "parts": [
        {"start_seconds": 0.0, "end_seconds": 15.0, "text": "SPEAKER 0: We help students. Contact us at"},
        {"start_seconds": 15.0, "end_seconds": 30.0, "text": "SPEAKER 0: the office"},
        {"start_seconds": 30.0, "end_seconds": 45.0, "text": "today. SPEAKER 1: Thanks!"},
    ],
}  # fmt: skip


class SpeechTextTest(unittest.TestCase):
    def test_speaker_label_kept_apart_and_part_edges_marked(self):
        _, refs, _ = material.speech_section(TRANSCRIPT, with_text=True)
        self.assertEqual(refs["S1"]["text"], "We help students.")
        self.assertEqual(refs["S1"]["speaker"], "SPEAKER 0")
        self.assertEqual(refs["S2"]["speaker"], "SPEAKER 0")  # same turn, no label
        self.assertNotIn("cut", refs["S1"])
        self.assertEqual(refs["S2"]["cut"], "end")
        self.assertEqual(refs["S3"]["cut"], "both")  # the whole part is one fragment
        self.assertEqual(refs["S4"]["cut"], "start")
        self.assertEqual(refs["S5"]["text"], "Thanks!")
        self.assertEqual(refs["S5"]["speaker"], "SPEAKER 1")
        self.assertNotIn("cut", refs["S5"])

    def test_without_text_the_references_stay_as_tag_topics_uses_them(self):
        lines, refs, _ = material.speech_section(TRANSCRIPT)
        self.assertEqual(set(refs["S2"]), {"source", "start_seconds", "end_seconds", "sentence"})
        self.assertIn("[S1] SPEAKER 0: We help students.", lines[0])


class ScreenTextTest(unittest.TestCase):
    TAGS = {"on_screen_text": [
        {"text": "CONSULTING GROUP", "legibility": "clear"},
        {"text": "TILICHO", "legibility": "partial"},
        {"text": "TILICHO", "legibility": "partial"},
        {"text": "Made up", "legibility": "partial", "confirmed": False},
    ]}  # fmt: skip

    def test_partly_read_text_once_without_unconfirmed(self):
        self.assertEqual(material.partial_texts(self.TAGS), ["TILICHO"])
        self.assertIn('- "TILICHO"', material.partial_section(self.TAGS))
        self.assertEqual(material.partial_section({"on_screen_text": []}), "")

    def test_screen_texts_hold_clear_and_partial(self):
        self.assertEqual(material.screen_texts(self.TAGS), ["CONSULTING GROUP", "TILICHO"])


class OrganisationTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "organisation.json"

    def write(self, data):
        self.path.write_text(json.dumps(data), encoding="utf-8")

    def test_missing_file_is_none(self):
        self.assertIsNone(organisation.load_organisation(self.path))

    def test_loaded_and_cleaned(self):
        self.write({"name": " Tilicho Consulting Group ", "other_names": ["Tilicho"],
                    "website": "https://www.tilicho.com", "hashtags": ["#Tilicho Nepal"]})  # fmt: skip
        found = organisation.load_organisation(self.path)
        self.assertEqual(found["name"], "Tilicho Consulting Group")
        self.assertEqual(found["hashtags"], ["tilichonepal"])
        self.assertEqual(
            organisation.brand_forms(found),
            ["tilichoconsultinggroup", "tilicho", "tilichonepal"],
        )
        section = organisation.organisation_section(found)
        self.assertIn("Name: Tilicho Consulting Group", section)
        self.assertIn("Website: https://www.tilicho.com", section)

    def test_heard_as_only_when_given(self):
        self.write({"name": "Tilicho Consulting Group"})
        self.assertNotIn("heard_as", organisation.load_organisation(self.path))
        self.write({"name": "Tilicho Consulting Group", "heard_as": [" Tilottama ", "तिलोत्तमा"]})
        found = organisation.load_organisation(self.path)
        self.assertEqual(found["heard_as"], ["Tilottama", "तिलोत्तमा"])
        self.assertIn("Speech-to-text may write the name as: Tilottama, तिलोत्तमा",
                      organisation.organisation_section(found))  # fmt: skip

    def test_without_a_name_fails(self):
        self.write({"other_names": ["x"]})
        with self.assertRaises(SystemExit):
            organisation.load_organisation(self.path)

    def test_hashtag_form_keeps_other_scripts(self):
        self.assertEqual(organisation.hashtag_form("#मेरो भिसा"), "मेरोभिसा")
        self.assertEqual(organisation.hashtag_form("Study_Abroad-2025!"), "study_abroad2025")


if __name__ == "__main__":
    unittest.main()
