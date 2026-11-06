from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import load_script

draft = load_script("draft-report", "draft")
finalize = load_script("draft-report", "finalize")

PLAN = {"options": {"model": "test-model", "reasoning_effort": "low"}, "context": "REPORT\nMonth: ..."}


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
        for item in objects(draft.SCHEMA):
            self.assertFalse(item["additionalProperties"])
            self.assertEqual(item["required"], list(item["properties"]))

    def test_slots_and_tiles_are_finalize_s(self):
        properties = draft.SCHEMA["properties"]
        slot = properties["highlights"]["items"]["properties"]["slot"]["enum"]
        tile = properties["tiles"]["items"]["properties"]["metric"]["enum"]
        self.assertEqual(slot, list(finalize.SLOTS))
        self.assertEqual(tile, list(finalize.TILES))

    def test_each_sentence_item_asks_for_one_sentence(self):
        self.assertEqual(draft.SENTENCE["properties"]["text"]["description"], "Exactly one sentence.")

    def test_the_three_paragraphs_are_finalize_s(self):
        for key in finalize.PARAGRAPHS:
            self.assertIn(key, draft.SCHEMA["properties"])
            self.assertIn(key, draft.INSTRUCTIONS)

    def test_the_instructions_hold_the_rules(self):
        for rule in ("never write 0", "not a cause", "Partial or Stale", "Never write a person's name",
                     "do not plan next month", "EARLIER MONTHS", "no ratios", "one sentence per item",
                     "never call the people in its posts clients", "same video as"):  # fmt: skip
            self.assertIn(rule, draft.INSTRUCTIONS.replace("\n", " "), rule)


class PayloadTest(unittest.TestCase):
    def test_strict_json_and_the_material_only(self):
        payload = draft.build_payload(PLAN)
        self.assertEqual(payload["text"]["format"]["type"], "json_schema")
        self.assertTrue(payload["text"]["format"]["strict"])
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
        reply = {"status": "completed", "output_text": json.dumps({"headline": {}}), "usage": {"input_tokens": 9}}
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(draft, "request", return_value=reply):
            self.assertIsNone(draft.ask(Path(folder), PLAN))
            saved = json.loads((Path(folder) / "results" / "answer.json").read_text())
        self.assertEqual(saved, {"answer": {"headline": {}}, "usage": {"input_tokens": 9}})

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
