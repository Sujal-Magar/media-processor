from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import load_script

tag = load_script("tag-topics", "tag")

PLAN = {
    "options": {"model": "test-model", "reasoning_effort": "low"},
    "existing_tags": [{"label": "visa-success-story", "category": "topic", "uses": 2}],
    "context": "Media: video\n\nSPEECH\n\n[S1 00:00:00-00:02:00]\nhello",
}


class PayloadTest(unittest.TestCase):
    def test_text_only_with_context_vocabulary_and_reasoning(self):
        payload = tag.build_payload(PLAN)
        content = payload["input"][0]["content"]
        self.assertEqual({part["type"] for part in content}, {"input_text"})
        texts = " ".join(part["text"] for part in content)
        self.assertIn("[S1 00:00:00-00:02:00]", texts)
        self.assertIn("topic: visa-success-story", texts)
        self.assertEqual(payload["model"], "test-model")
        self.assertEqual(payload["reasoning"], {"effort": "low"})
        self.assertTrue(payload["text"]["format"]["strict"])

    def test_unset_effort_sends_no_reasoning(self):
        plan = {**PLAN, "options": {"model": "m", "reasoning_effort": "unset"}}
        self.assertNotIn("reasoning", tag.build_payload(plan))

    def test_instructions_ask_for_hyphens_and_no_names(self):
        self.assertIn("joined by hyphens", tag.INSTRUCTIONS)
        self.assertIn("Never include a person's name", tag.INSTRUCTIONS)

    def test_instructions_do_not_steer_evidence_to_the_first_sentence(self):
        self.assertNotIn("(S1,", tag.INSTRUCTIONS)
        self.assertIn("do not default to the first sentence", tag.INSTRUCTIONS)
        self.assertIn("ORGANISATION section", tag.INSTRUCTIONS)

    def test_instructions_ask_to_cite_supporting_pictures_and_text(self):
        self.assertIn("cite those too", tag.INSTRUCTIONS)


class AskTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.job_dir = Path(temporary.name)
        self.answer_file = self.job_dir / "results" / "answer.json"

    def test_answer_saved(self):
        reply = {"output_text": json.dumps({"summary": "s", "tags": []}),
                 "usage": {"input_tokens": 5, "output_tokens": 2}}  # fmt: skip
        with mock.patch.object(tag, "request", return_value=reply) as sent:
            self.assertIsNone(tag.ask(self.job_dir, PLAN))
        sent.assert_called_once()
        saved = json.loads(self.answer_file.read_text(encoding="utf-8"))
        self.assertEqual(saved, {"answer": {"summary": "s", "tags": []},
                                 "usage": {"input_tokens": 5, "output_tokens": 2}})

    def test_saved_answer_is_not_sent_again(self):
        self.answer_file.parent.mkdir()
        self.answer_file.write_text('{"answer": {"summary": "", "tags": []}}', encoding="utf-8")
        with mock.patch.object(tag, "request", side_effect=AssertionError("paid twice")):
            self.assertIsNone(tag.ask(self.job_dir, PLAN))

    def test_api_error_returned_and_nothing_saved(self):
        error = tag.OpenAIError(429, "rate_limit_exceeded", "slow down")
        with mock.patch.object(tag, "request", side_effect=error):
            self.assertIs(tag.ask(self.job_dir, PLAN), error)
        self.assertFalse(self.answer_file.exists())

    def test_answer_cut_off_at_the_token_limit_is_reported_as_such(self):
        reply = {"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"},
                 "output_text": '{"summary": "A stud'}  # fmt: skip
        with mock.patch.object(tag, "request", return_value=reply):
            failure = tag.ask(self.job_dir, PLAN)
        self.assertEqual(failure.code, "max_output_tokens")
        self.assertFalse(self.answer_file.exists())

    def test_instructions_limit_references_per_tag(self):
        self.assertIn("at most 5 references", tag.INSTRUCTIONS)

    def test_unreadable_answer_is_bad_output(self):
        with mock.patch.object(tag, "request", return_value={"output_text": "not json"}):
            failure = tag.ask(self.job_dir, PLAN)
        self.assertEqual(failure.code, "bad_output")
        self.assertFalse(self.answer_file.exists())


if __name__ == "__main__":
    unittest.main()
