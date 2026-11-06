from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import load_script

draft = load_script("draft-insights", "draft")
finalize = load_script("draft-insights", "finalize")

PLAN = {
    "options": {"model": "test-model", "reasoning_effort": "low"},
    "context": "INSIGHTS\nMonth: ...",
    "quantities": [1, 2],
}


def objects(schema):
    """Every object in a JSON schema."""
    if schema.get("type") == "object":
        yield schema
        for value in schema["properties"].values():
            yield from objects(value)
    elif schema.get("type") == "array":
        yield from objects(schema["items"])


class SchemaTest(unittest.TestCase):
    def test_every_object_is_strict(self):
        for item in objects(draft.schema([1, 2, 3])):
            self.assertFalse(item["additionalProperties"])
            self.assertEqual(item["required"], list(item["properties"]))

    def test_the_request_may_ask_only_for_the_allowed_quantities(self):
        insight = draft.schema([1, 2])["properties"]["insights"]["items"]["properties"]
        action = insight["action"]["properties"]
        self.assertEqual(action["quantity"], {"type": "integer", "enum": [1, 2]})
        self.assertEqual(action["category"]["enum"], list(finalize.CATEGORIES))
        self.assertEqual(action["language"]["enum"], list(finalize.LANGUAGES))

    def test_the_instructions_hold_the_rules(self):
        for rule in ("worded as a possibility", "never as fact", "enough_evidence to false",
                     "confirm_if", "refute_if", "compute nothing yourself", "held back",
                     "Never write a person's name", "not the strategist's either",
                     "never write a reference in the text", "at most 5 words", "engagement rate"):  # fmt: skip
            self.assertIn(rule, " ".join(draft.INSTRUCTIONS.split()), rule)


class PayloadTest(unittest.TestCase):
    def test_strict_json_with_the_plan_s_quantities(self):
        payload = draft.build_payload(PLAN)
        format_ = payload["text"]["format"]
        self.assertTrue(format_["strict"])
        self.assertEqual(format_["schema"], draft.schema([1, 2]))
        self.assertEqual(payload["input"][0]["content"], [{"type": "input_text", "text": PLAN["context"]}])
        self.assertEqual(payload["reasoning"], {"effort": "low"})

    def test_unset_effort_sends_no_reasoning(self):
        plan = {**PLAN, "options": {"model": "m", "reasoning_effort": "unset"}}
        self.assertNotIn("reasoning", draft.build_payload(plan))


class AskTest(unittest.TestCase):
    def test_a_saved_answer_is_never_paid_for_again(self):
        with tempfile.TemporaryDirectory() as folder:
            job = Path(folder)
            (job / "results").mkdir()
            (job / "results" / "answer.json").write_text("{}")
            with mock.patch.object(draft, "request") as sent:
                self.assertIsNone(draft.ask(job, PLAN))
            sent.assert_not_called()

    def test_the_answer_is_saved_with_its_usage(self):
        reply = {"status": "completed", "output_text": json.dumps({"insights": []}), "usage": {"input_tokens": 9}}
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(draft, "request", return_value=reply):
            self.assertIsNone(draft.ask(Path(folder), PLAN))
            saved = json.loads((Path(folder) / "results" / "answer.json").read_text())
        self.assertEqual(saved, {"answer": {"insights": []}, "usage": {"input_tokens": 9}})

    def test_a_cut_off_answer_says_so(self):
        reply = {"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"}}
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(draft, "request", return_value=reply):
            failure = draft.ask(Path(folder), PLAN)
            self.assertFalse((Path(folder) / "results").exists())
        self.assertEqual(failure.code, "max_output_tokens")

    def test_an_unreadable_answer_is_bad_output(self):
        reply = {"status": "completed", "output_text": "not json"}
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(draft, "request", return_value=reply):
            self.assertEqual(draft.ask(Path(folder), PLAN).code, "bad_output")


if __name__ == "__main__":
    unittest.main()
