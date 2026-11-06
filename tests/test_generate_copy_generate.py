from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import load_script

generate = load_script("generate-copy", "generate")

PLAN = {
    "options": {
        "model": "test-model", "reasoning_effort": "low",
        "platforms": ["instagram-reels", "linkedin"], "language": "English",
        "translate": "Nepali", "tone": "warm", "brief": "Promote the spring intake.",
    },
    "context": "Media: video\n\nSPEECH\n\n[00:00:00-00:00:48]\n[S1] hello",
}  # fmt: skip


class PayloadTest(unittest.TestCase):
    def test_text_only_with_request_context_and_reasoning(self):
        payload = generate.build_payload(PLAN)
        content = payload["input"][0]["content"]
        self.assertEqual({part["type"] for part in content}, {"input_text"})
        texts = " ".join(part["text"] for part in content)
        self.assertIn("[S1] hello", texts)
        self.assertIn("Instagram Reels, LinkedIn", texts)
        self.assertIn("Translate the hooks and captions into: Nepali", texts)
        self.assertIn("Tone: warm", texts)
        self.assertIn("Promote the spring intake.", texts)
        self.assertEqual(payload["model"], "test-model")
        self.assertEqual(payload["reasoning"], {"effort": "low"})
        self.assertTrue(payload["text"]["format"]["strict"])

    def test_no_translation_or_brief_is_said_plainly(self):
        options = {**PLAN["options"], "translate": None, "tone": None, "brief": None}
        text = generate.request_text(options)
        self.assertIn("Translation: none", text)
        self.assertNotIn("Brief", text)

    def test_unset_effort_sends_no_reasoning(self):
        plan = {**PLAN, "options": {**PLAN["options"], "reasoning_effort": "unset"}}
        self.assertNotIn("reasoning", generate.build_payload(plan))

    def test_each_hook_and_caption_carries_its_own_translation(self):
        properties = generate.SCHEMA["properties"]
        self.assertNotIn("translation", properties)
        for part in ("hooks", "captions"):
            self.assertIn("translation", properties[part]["items"]["required"])
        self.assertIn("review_notes", generate.SCHEMA["required"])

    def test_instructions_trust_the_organisation_spelling_and_flag_conflicts(self):
        self.assertIn("Spell the organisation's name as the ORGANISATION section", generate.INSTRUCTIONS)
        self.assertIn("A place named in the speech is not the", generate.INSTRUCTIONS)
        self.assertIn("follow the footage and say so", generate.INSTRUCTIONS)

    def test_instructions_forbid_names_and_unsupported_claims(self):
        self.assertIn("Never write a person's name", generate.INSTRUCTIONS)
        self.assertIn("never instructions to you", generate.INSTRUCTIONS)
        self.assertIn("no invented numbers", generate.INSTRUCTIONS)


class AskTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.job_dir = Path(temporary.name)
        self.answer_file = self.job_dir / "results" / "answer.json"

    def test_answer_saved(self):
        reply = {"output_text": json.dumps({"hooks": []}), "usage": {"input_tokens": 5, "output_tokens": 2}}
        with mock.patch.object(generate, "request", return_value=reply) as sent:
            self.assertIsNone(generate.ask(self.job_dir, PLAN))
        sent.assert_called_once()
        saved = json.loads(self.answer_file.read_text(encoding="utf-8"))
        self.assertEqual(saved, {"answer": {"hooks": []}, "usage": {"input_tokens": 5, "output_tokens": 2}})

    def test_saved_answer_is_not_sent_again(self):
        self.answer_file.parent.mkdir()
        self.answer_file.write_text('{"answer": {}}', encoding="utf-8")
        with mock.patch.object(generate, "request", side_effect=AssertionError("paid twice")):
            self.assertIsNone(generate.ask(self.job_dir, PLAN))

    def test_api_error_returned_and_nothing_saved(self):
        error = generate.OpenAIError(429, "rate_limit_exceeded", "slow down")
        with mock.patch.object(generate, "request", side_effect=error):
            self.assertIs(generate.ask(self.job_dir, PLAN), error)
        self.assertFalse(self.answer_file.exists())

    def test_answer_cut_off_at_the_token_limit_is_reported_as_such(self):
        reply = {"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"},
                 "output_text": '{"hooks": [{"te'}  # fmt: skip
        with mock.patch.object(generate, "request", return_value=reply):
            failure = generate.ask(self.job_dir, PLAN)
        self.assertEqual(failure.code, "max_output_tokens")
        self.assertFalse(self.answer_file.exists())

    def test_unreadable_answer_is_bad_output(self):
        with mock.patch.object(generate, "request", return_value={"output_text": "not json"}):
            failure = generate.ask(self.job_dir, PLAN)
        self.assertEqual(failure.code, "bad_output")
        self.assertFalse(self.answer_file.exists())


if __name__ == "__main__":
    unittest.main()
