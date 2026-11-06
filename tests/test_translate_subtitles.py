from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from helpers import load_script

from lib.subtitles import split_cue, stamp, width

prepare = load_script("translate-subtitles", "prepare")
translate = load_script("translate-subtitles", "translate")
finalize = load_script("translate-subtitles", "finalize")

# Mostly Nepali, with English words inside, as in the videos.
TRANSCRIPT = {
    "complete": True, "created_at": "t-transcript",
    "parts": [
        {"index": 0, "start_seconds": 0.0, "end_seconds": 8.0, "missing": False,
         "text": "SPEAKER 0: मेरो subclass 500 भिसा आयो, म धेरै खुसी छु। Thank you, everyone!"},
        {"index": 1, "start_seconds": 8.0, "end_seconds": 12.0, "missing": False,
         "text": "SPEAKER 0: आजै Tilicho लाई सम्पर्क गर्नुहोस्। (laughter)"},
    ],
}  # fmt: skip
ORGANISATION = {"name": "Tilicho Consulting Group", "other_names": [], "website": "",
                "hashtags": [], "note": ""}  # fmt: skip


def planned(languages=("en", "ne")):
    """Cues, spans and the tracks as prepare plans them."""
    cues = prepare.numbered(TRANSCRIPT)
    assembled, full = prepare.tracks(cues, list(languages))
    spans = prepare.with_spans(cues, assembled) if assembled else []
    return cues, spans, assembled, full


def objects(schema):
    if schema.get("type") == "object":
        yield schema
        for value in schema["properties"].values():
            yield from objects(value)
    elif schema.get("type") == "array":
        yield from objects(schema["items"])


class PrepareTest(unittest.TestCase):
    def test_languages_by_code_or_name_both_by_default(self):
        self.assertEqual(prepare.request_languages(None), ["en", "ne"])
        self.assertEqual(prepare.request_languages("Nepali, en, ne"), ["ne", "en"])
        with self.assertRaises(SystemExit):
            prepare.request_languages("hindi")

    def test_cues_are_the_transcript_s_subtitles_numbered(self):
        cues = prepare.numbered(TRANSCRIPT)
        self.assertEqual([c["id"] for c in cues], ["C1", "C2", "C3"])
        self.assertEqual((cues[0]["start"], cues[-1]["end"]), (0.0, 12.0))
        self.assertEqual(cues[0]["speaker"], "SPEAKER 0")
        self.assertNotIn("SPEAKER", cues[0]["text"])

    def test_the_language_most_of_the_speech_is_in_is_assembled(self):
        cues, spans, assembled, full = planned()
        self.assertEqual((assembled, full), ("ne", ["en"]))
        self.assertEqual(prepare.tracks(prepare.numbered(TRANSCRIPT), ["en"]), (None, ["en"]))
        english = [{"id": "C1", "text": "We help students apply for the visa. धन्यवाद।"}]
        self.assertEqual(prepare.tracks(english, ["en", "ne"]), ("en", ["ne"]))

    def test_spans_are_the_words_in_the_other_script(self):
        cues, spans, _, _ = planned()
        self.assertEqual([(s["id"], s["cue"], s["text"]) for s in spans], [
            ("S1", "C1", "subclass"), ("S2", "C2", "Thank you, everyone"),
            ("S3", "C3", "Tilicho"), ("S4", "C3", "laughter")])  # fmt: skip
        # Numbers and punctuation at a span's edge stay outside it.
        self.assertEqual(cues[0]["parts"], [{"text": "मेरो", "space": False}, {"span": "S1", "space": True},
                                            {"text": "500 भिसा आयो, म धेरै खुसी छु।", "space": True}])  # fmt: skip
        self.assertEqual(cues[2]["parts"][-3:], [{"text": "लाई सम्पर्क गर्नुहोस्। (", "space": True},
                                                 {"span": "S4", "space": False}, {"text": ")", "space": False}])  # fmt: skip

    def test_an_english_word_with_a_nepali_ending_is_a_span_and_keeps_the_ending(self):
        parts = finalize.split_spans("Refusalsहरू पनि छन् marketमा।", "Devanagari")
        self.assertEqual(parts, [
            {"span": "Refusals", "space": False}, {"text": "हरू पनि छन्", "space": False},
            {"span": "market", "space": True}, {"text": "मा।", "space": False}])  # fmt: skip
        rendered = finalize.assemble(parts, {"Refusals": "रिफ्युजल", "market": "मार्केट"}, {})
        self.assertEqual(rendered, "रिफ्युजलहरू पनि छन् मार्केटमा।")

    def test_a_heard_as_form_is_a_name_span_of_its_own(self):
        parts = finalize.split_spans("आजै तिलोत्तमामा आउनुहोस्।", "Devanagari", ["तिलोत्तमा", "Tilottama"])
        self.assertEqual(parts, [
            {"text": "आजै", "space": False}, {"span": "तिलोत्तमा", "space": True, "name": True},
            {"text": "मा आउनुहोस्।", "space": False}])  # fmt: skip
        cues = [{"id": "C1", "text": "आजै तिलोत्तमामा आउनुहोस्।"}]
        spans = prepare.with_spans(cues, "ne", ["तिलोत्तमा"])
        self.assertEqual(spans, [{"id": "S1", "cue": "C1", "text": "तिलोत्तमा", "name": True}])
        context = prepare.build_context(cues, spans, "ne", None)
        self.assertIn("[S1 in C1, the organisation's name as heard] तिलोत्तमा", context)

    def test_putting_the_spans_back_as_said_gives_the_cue(self):
        cues, spans, _, _ = planned()
        said = {s["id"]: s["text"] for s in spans}
        for cue in cues:
            self.assertEqual(finalize.assemble(cue["parts"], {}, said), cue["text"])

    def test_the_material_has_the_cues_the_spans_and_the_organisation(self):
        cues, spans, assembled, _ = planned()
        context = prepare.build_context(cues, spans, assembled, ORGANISATION)
        self.assertIn("[C1] मेरो subclass 500 भिसा आयो, म धेरै खुसी छु।", context)
        self.assertIn("SPANS FOR THE NEPALI TRACK", context)
        self.assertIn("[S2 in C2] Thank you, everyone", context)
        self.assertIn("Name: Tilicho Consulting Group", context)

    def test_warnings(self):
        one_part = {"complete": False, "parts": [TRANSCRIPT["parts"][0]]}
        warnings = " | ".join(prepare.input_warnings(one_part, None))
        self.assertIn("incomplete", warnings)
        self.assertIn("one part", warnings)
        self.assertIn("No organisation.json", warnings)


class TranslateTest(unittest.TestCase):
    def test_the_instructions(self):
        text = " ".join(translate.INSTRUCTIONS.split())
        self.assertIn("The rest of that cue stays exactly as it was said", text)
        self.assertIn("not translated but written in the track's script as it sounds", text)
        self.assertIn("Decide from its cue", text)
        self.assertIn("never from your text for another language", text)
        self.assertIn("at most two lines of 42 characters, 84 in all", text)

    def test_the_schema_asks_for_spans_and_whole_cues_and_is_strict(self):
        schema = translate.schema(["en"], "ne", "ne-spoken")
        self.assertEqual(list(schema["properties"]), ["spans", "cues", "review_notes"])
        self.assertEqual(schema["properties"]["spans"]["items"]["required"], ["span", "ne", "ne_spoken"])
        self.assertEqual(schema["properties"]["cues"]["items"]["required"], ["cue", "en"])
        for item in objects(schema):
            self.assertFalse(item["additionalProperties"])
            self.assertEqual(item["required"], list(item["properties"]))
        self.assertEqual(list(translate.schema(["en"], None)["properties"]), ["cues", "review_notes"])

    def test_the_payload_says_which_track_is_which(self):
        plan = {"options": {"model": "m", "reasoning_effort": "low", "languages": ["en", "ne"],
                            "assembled": "ne", "spoken": "ne-spoken", "full": ["en"]}, "context": "CUES"}  # fmt: skip
        payload = translate.build_payload(plan)
        self.assertEqual(payload["input"][0]["content"][0]["text"],
                         "REQUEST\nPut each span into: Nepali (ne), Nepali as spoken (ne_spoken)\n"
                         "Write each whole cue in: English (en)")  # fmt: skip
        self.assertEqual(payload["input"][0]["content"][1]["text"], "CUES")
        self.assertTrue(payload["text"]["format"]["strict"])


ENGLISH = {
    "C1": "My subclass 500 visa came through, and I am very happy.",
    "C2": "Thank you, everyone!",
    "C3": "Contact Tilicho today. (laughter)",
}
SPANS = {"S1": "सबक्लास", "S2": "सबैलाई धन्यवाद", "S3": "Tilicho", "S4": "हाँसो"}
SPOKEN = {"S1": "सबक्लास", "S2": "थ्यांक यु, एभ्रिवान", "S3": "तिलिचो", "S4": "लाफ्टर"}


class FinalizeTest(unittest.TestCase):
    def run_finalize(self, english=None, spans=None, spoken=None):
        english = ENGLISH if english is None else english
        spans = SPANS if spans is None else spans
        spoken = SPOKEN if spoken is None else spoken
        folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        job, output = folder / "job", folder / "output"
        (job / "results").mkdir(parents=True)
        cues, planned_spans, assembled, full = planned()
        plan = {"processor": "translate-subtitles", "source": {"name": "story.mov"}, "inputs": {},
                "organisation": None, "options": {"model": "test-model", "reasoning_effort": "low",
                "languages": ["en", "ne"], "assembled": assembled, "spoken": "ne-spoken", "full": full},
                "cues": cues,
                "spans": planned_spans, "context": "x", "estimated_input_tokens": 1, "warnings": [],
                "output_dir": str(output), "replaces": None}  # fmt: skip
        answer = {"cues": [{"cue": c, "en": t} for c, t in english.items()],
                  "spans": [{"span": s, "ne": t, "ne_spoken": spoken.get(s, "")} for s, t in spans.items()],
                  "review_notes": []}  # fmt: skip
        (job / "plan.json").write_text(json.dumps(plan))
        (job / "results" / "answer.json").write_text(json.dumps({"answer": answer, "usage": {}}))
        return finalize.finalize(job), output, cues

    def test_the_nepali_track_keeps_what_was_said_and_puts_in_the_spans(self):
        summary, output, cues = self.run_finalize()
        self.assertEqual(summary["status"], "complete")
        self.assertEqual(summary["checks"], [])
        document = json.loads((output / "translation.json").read_text())
        self.assertEqual([c["ne"] for c in document["cues"]], [
            "मेरो सबक्लास 500 भिसा आयो, म धेरै खुसी छु।", "सबैलाई धन्यवाद!",
            "आजै Tilicho लाई सम्पर्क गर्नुहोस्। (हाँसो)"])  # fmt: skip
        self.assertEqual(document["spans"][0], {"id": "S1", "cue": "C1", "text": "subclass", "ne": "सबक्लास",
                                                "ne-spoken": "सबक्लास"})  # fmt: skip
        self.assertEqual(summary["translated"], {"English": 3, "Nepali spans": 4, "Nepali as spoken spans": 4})

    def test_the_spoken_track_writes_the_other_words_by_their_sound(self):
        summary, output, _ = self.run_finalize()
        document = json.loads((output / "translation.json").read_text())
        self.assertEqual([c["ne-spoken"] for c in document["cues"]], [
            "मेरो सबक्लास 500 भिसा आयो, म धेरै खुसी छु।", "थ्यांक यु, एभ्रिवान!",
            "आजै तिलिचो लाई सम्पर्क गर्नुहोस्। (लाफ्टर)"])  # fmt: skip
        vtt = (output / "transcript.ne-spoken.vtt").read_text()
        self.assertIn("NOTE\nNepali subtitles as spoken: every word as said", vtt)
        self.assertEqual(summary["tracks"], ["English", "Nepali", "Nepali as spoken"])

    def test_latin_letters_left_in_the_spoken_track_are_flagged(self):
        checks = self.run_finalize(spoken={**SPOKEN, "S3": "Tilicho"})[0]["checks"]
        self.assertIn("C3 in Nepali as spoken still has Latin letters; check that every word is in Devanagari.",
                      checks)  # fmt: skip

    def test_every_track_keeps_every_cue_s_times(self):
        _, output, cues = self.run_finalize()
        files = sorted(p.name for p in output.iterdir())
        self.assertEqual(files, ["metadata.json", "transcript.en.srt", "transcript.en.vtt",
                                 "transcript.ne-spoken.srt", "transcript.ne-spoken.vtt",
                                 "transcript.ne.srt", "transcript.ne.vtt", "translation.json"])  # fmt: skip
        for name in ("transcript.en.srt", "transcript.ne.srt", "transcript.ne-spoken.srt"):
            srt = (output / name).read_text()
            for cue in cues:
                self.assertIn(f"{stamp(cue['start'], ',')} --> {stamp(cue['end'], ',')}", srt)
        vtt = (output / "transcript.ne.vtt").read_text()
        self.assertIn("NOTE\nNepali translation of the transcript's subtitles, made by a model (test-model)", vtt)
        self.assertIn("<v SPEAKER 0>सबैलाई धन्यवाद!", vtt)

    def test_a_missing_span_or_cue_keeps_what_was_said_and_makes_it_incomplete(self):
        summary, output, cues = self.run_finalize(english={"C1": ENGLISH["C1"], "C9": "Made up."},
                                                  spans={"S1": "सबक्लास", "S3": "Tilicho", "S4": "हाँसो"},
                                                  spoken={"S1": "सबक्लास", "S3": "तिलिचो", "S4": "लाफ्टर"})  # fmt: skip
        self.assertEqual(summary["status"], "incomplete")
        self.assertEqual(summary["dropped"], 1)
        self.assertIn("S2 (in C2) has no Nepali; the words as said are kept.", summary["missing"])
        self.assertIn("S2 (in C2) has no Nepali as spoken; the words as said are kept.", summary["missing"])
        self.assertIn("C2 has no English translation; its original text is kept.", summary["missing"])
        document = json.loads((output / "translation.json").read_text())
        self.assertEqual(document["cues"][1]["ne"], "Thank you, everyone!")
        self.assertEqual(document["review_status"], "draft")

    def test_checks_on_the_whole_cue_track(self):
        english = {"C1": "मेरो visa came.", "C2": "Thanks a lot, all of you!", "C3": ENGLISH["C3"]}
        checks = self.run_finalize(english=english)[0]["checks"]
        self.assertIn("C1 in English still has Devanagari; check that it was translated.", checks)
        self.assertIn("C1 in English lacks the number 500 that the original has.", checks)
        # "Thank you, everyone" was said in English; the track kept only "you" of it.
        self.assertIn("C2 in English keeps 33% of the words said in English; check that it keeps "
                      "what was said and translates only the rest.", checks)  # fmt: skip

    def test_a_long_translation_is_split_within_its_cue_s_time(self):
        long = "My subclass 500 visa came through today. I am very, very happy and so is my whole family."
        summary, output, cues = self.run_finalize(english={**ENGLISH, "C1": long})
        self.assertEqual(summary["split"], 1)
        self.assertIn("C1 in English was too long for two lines, so it shows as 2 cues within its time; "
                      "check where it breaks.", summary["checks"])  # fmt: skip
        srt = (output / "transcript.en.srt").read_text()
        self.assertEqual(srt.count("-->"), 4)
        self.assertIn(f"{stamp(cues[0]['start'], ',')} --> ", srt)
        self.assertIn(f" --> {stamp(cues[0]['end'], ',')}", srt)
        for block in srt.strip().split("\n\n"):
            self.assertLessEqual(len(block.split("\n")) - 2, 2, block)


class SharedTest(unittest.TestCase):
    def test_marks_drawn_over_or_under_a_letter_take_no_width(self):
        self.assertEqual(width("भिसा"), 4)  # भ ि स ा: both vowel signs take room beside a letter
        self.assertEqual(width("संसार"), 4)  # the ं dot above takes no room
        self.assertEqual(width("Visa"), 4)

    def test_split_cue_cuts_at_sentence_ends_and_shares_the_time(self):
        cue = {"id": "C1", "start": 10.0, "end": 16.0, "speaker": None,
               "text": "We help every student choose a course. Then we apply for the visa, and we stay in touch."}  # fmt: skip
        parts = split_cue(cue)
        self.assertEqual([p["text"] for p in parts],
                         ["We help every student choose a course.", "Then we apply for the visa, and we stay in touch."])  # fmt: skip
        self.assertEqual(parts[0]["start"], 10.0)
        self.assertAlmostEqual(parts[0]["end"], parts[1]["start"])
        self.assertAlmostEqual(parts[1]["end"], 16.0)
        short = {**cue, "text": "Thank you."}
        self.assertEqual(split_cue(short), [short])

    def test_numbers_in_either_script_count_the_same(self):
        self.assertEqual(finalize.numbers("subclass ५०० and 2026"), {"500", "2026"})


if __name__ == "__main__":
    unittest.main()
