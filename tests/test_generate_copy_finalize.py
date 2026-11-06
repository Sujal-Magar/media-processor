from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from helpers import load_script

finalize = load_script("generate-copy", "finalize")

REFS = {
    "S1": {"source": "speech", "start_seconds": 0.0, "end_seconds": 15.0, "sentence": 1, "text": "मेरो भिसा आयो।"},
    "S2": {"source": "speech", "start_seconds": 0.0, "end_seconds": 15.0, "sentence": 2, "text": "Contact us at", "cut": "end"},
    "S3": {"source": "speech", "start_seconds": 15.0, "end_seconds": 30.0, "sentence": 1, "text": "the office", "cut": "start"},
    "T1": {"source": "on_screen_text", "ranges": [[12.0, 20.0]], "text": "Subclass 500"},
    "T2": {"source": "on_screen_text", "ranges": [[22.0, 25.0]], "text": "Jane Smith"},
    "V:office": {"source": "visual", "label": "office", "ranges": [[0.0, 12.0]]},
}  # fmt: skip
OPTIONS = {
    "model": "test-model", "reasoning_effort": "low",
    "platforms": ["instagram-reels", "linkedin"], "language": "English",
    "translate": "Nepali", "tone": None, "brief": None,
}  # fmt: skip
ORGANISATION = {"name": "Tilicho Consulting Group", "other_names": ["Tilicho"],
                "website": "", "hashtags": [], "note": ""}  # fmt: skip


def hook(text, refs, style="question", translation="अनुवाद"):
    return {"text": text, "style": style, "refs": refs, "translation": translation}


def caption(platform, body, refs=("S1",), translation="अनुवाद"):
    return {"platform": platform, "text": body, "call_to_action": "Apply", "refs": list(refs),
            "translation": translation}  # fmt: skip


def segment(soundbites, broll=(), purpose="story", overlay=""):
    return {"purpose": purpose, "soundbites": list(soundbites), "broll": list(broll),
            "subtitle": "", "overlay_text": overlay, "note": ""}  # fmt: skip


class HooksTest(unittest.TestCase):
    def test_hooks_without_evidence_or_repeated_are_dropped_with_their_translation(self):
        hooks = finalize.clean_hooks(
            [hook("Got your visa?", ["S1", "S9"], translation="भिसा?"),
             hook("Made up.", ["S9"], translation="बनावटी"),
             hook(" got your  visa? ", ["S2"]), hook("Thanks!", ["S2"], "story", "धन्यवाद")],
            REFS, translate=True,
        )  # fmt: skip
        self.assertEqual([(h["text"], h["translation"]) for h in hooks],
                         [("Got your visa?", "भिसा?"), ("Thanks!", "धन्यवाद")])  # fmt: skip
        self.assertEqual([e["ref"] for e in hooks[0]["evidence"]], ["S1"])

    def test_no_translation_kept_when_none_was_asked(self):
        hooks = finalize.clean_hooks([hook("Got your visa?", ["S1"])], REFS, translate=False)
        self.assertNotIn("translation", hooks[0])

    def test_at_most_five_hooks(self):
        hooks = finalize.clean_hooks([hook(f"Hook {n}", ["S1"]) for n in range(7)], REFS, True)
        self.assertEqual(len(hooks), finalize.MAX_HOOKS)


class ScriptTest(unittest.TestCase):
    def test_refs_go_where_they_belong_and_empty_segments_are_dropped(self):
        script = finalize.clean_script(
            {"title": " Visa  day ", "segments": [
                segment(["S1", "V:office"], ["V:office", "T1", "S2", "V:nope"], "hook"),
                segment(["S9"], overlay="x"),
            ]},
            REFS,
        )  # fmt: skip
        self.assertEqual(script["title"], "Visa day")
        self.assertEqual(len(script["segments"]), 1)
        first = script["segments"][0]
        self.assertEqual([s["ref"] for s in first["soundbites"]], ["S1"])
        self.assertEqual(first["soundbites"][0]["text"], "मेरो भिसा आयो।")
        self.assertEqual([b["ref"] for b in first["broll"]], ["V:office", "T1"])
        self.assertEqual(script["segments_dropped"], [{"segment": 2, "soundbites": ["S9"], "broll": []}])

    def test_ranges_and_loose_writing_name_each_sentence(self):
        self.assertEqual(
            finalize.parse_refs(["S1-S3", "[T1]", "S2–3", "V:office and S2", "S9-S1"]),
            ["S1", "S2", "S3", "T1", "S2", "S3", "V:office", "S2"],
        )
        script = finalize.clean_script({"title": "", "segments": [segment(["S1-S3"])]}, REFS)
        self.assertEqual([b["ref"] for b in script["segments"][0]["soundbites"]], ["S1", "S2", "S3"])


class CaptionsTest(unittest.TestCase):
    def test_only_requested_platforms_first_one_kept(self):
        captions = finalize.clean_captions(
            [caption("linkedin", "Proud day."), caption("linkedin", "Second."),
             caption("tiktok", "Not asked.")],
            REFS, OPTIONS["platforms"], translate=True,
        )  # fmt: skip
        self.assertEqual([c["platform"] for c in captions], ["linkedin"])
        self.assertEqual(captions[0]["text"], "Proud day.")
        self.assertEqual(captions[0]["translation"], "अनुवाद")

    def test_too_long_caption_is_a_check(self):
        long = {"platform": "linkedin", "text": "x" * 3001, "call_to_action": "", "evidence": []}
        checks = finalize.caption_checks([long])
        self.assertEqual(len(checks), 1)
        self.assertIn("3,000", checks[0])


class HashtagsTest(unittest.TestCase):
    def test_cleaned_deduplicated_and_capped(self):
        hashtags = finalize.clean_hashtags({
            "niche": ["#Study Visa", "subclass-500", "मेरोभिसा", "studyvisa"],
            "broad": ["#StudyAbroad", "#studyvisa", ""],
            "brand": [f"brand{n}" for n in range(9)],
        })  # fmt: skip
        self.assertEqual(hashtags["niche"], ["studyvisa", "subclass500", "मेरोभिसा"])
        self.assertEqual(hashtags["broad"], ["studyabroad"])
        self.assertEqual(len(hashtags["brand"]), finalize.MAX_HASHTAGS["brand"])


class MissingTest(unittest.TestCase):
    def test_each_gap_is_named(self):
        missing = finalize.missing_parts(
            hooks=[{"text": "a", "translation": ""}], script={"segments": []},
            captions=[{"platform": "linkedin", "translation": ""}], options=OPTIONS,
        )  # fmt: skip
        self.assertEqual(len(missing), 5)
        joined = " ".join(missing)
        for words in ("1 usable hooks", "script", "no caption for Instagram Reels",
                      "1 hooks have no Nepali", "Nepali translation of the LinkedIn"):  # fmt: skip
            self.assertIn(words, joined)


class SpeechUsedTest(unittest.TestCase):
    def test_a_script_without_soundbites_is_incomplete_when_there_is_speech(self):
        script = {"segments": [{"soundbites": [], "broll": [{"ref": "T1"}]}]}
        hooks = [{"text": str(n), "translation": "x"} for n in range(3)]
        captions = [{"platform": p, "translation": "x"} for p in OPTIONS["platforms"]]
        missing = finalize.missing_parts(hooks, script, captions, OPTIONS, has_speech=True)
        self.assertEqual(missing, ["the script uses none of the speech (no soundbites)"])
        self.assertEqual(finalize.missing_parts(hooks, script, captions, OPTIONS), [])


class ChecksTest(unittest.TestCase):
    def test_brand_hashtag_needs_the_organisation_or_the_screen(self):
        brand = ["tilottamaconsultinggroup", "tilichoconsulting", "consultinggroup"]
        checks = finalize.brand_checks(brand, ORGANISATION, ["CONSULTING GROUP"])
        self.assertEqual(len(checks), 1)
        self.assertIn("#tilottamaconsultinggroup", checks[0])
        # Without organisation.json, only the screen can confirm a brand hashtag.
        self.assertEqual(len(finalize.brand_checks(brand, None, ["…at Tilicho Consulting"])), 2)

    def test_opening_or_closing_on_a_cut_sentence(self):
        script = finalize.clean_script(
            {"title": "", "segments": [segment(["S3"]), segment(["S1", "S2"], purpose="call-to-action")]},
            REFS,
        )  # fmt: skip
        checks = finalize.cut_checks(script["segments"])
        self.assertEqual(len(checks), 2)
        self.assertIn("opens on S3", checks[0])
        self.assertIn("ends on S2", checks[1])

    def test_on_screen_text_repeated_word_for_word(self):
        document = {
            "hooks": [{"text": "Meet Jane Smith", "translation": ""}],
            "script": {"segments": [{"subtitle": "", "overlay_text": "Tilicho Consulting Group"}]},
            "captions": [{"text": "Subclass 500 explained", "call_to_action": "", "translation": ""}],
        }  # fmt: skip
        refs = {**REFS, "T3": {"source": "on_screen_text", "text": "Consulting Group"}}
        checks = finalize.screen_copy_checks(document, refs, ORGANISATION)
        self.assertEqual([c.split()[5] for c in checks], ["T1", "T2"])  # T3 is the name


class FinalizeTest(unittest.TestCase):
    def test_writes_outputs_without_the_material(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        job_dir, output_dir = root / "job", root / "out"
        (job_dir / "results").mkdir(parents=True)
        plan = {
            "version": 1, "processor": "generate-copy", "status": "ready",
            "source": {"name": "story.mov", "path": "/x/story.mov", "sha256": "0" * 64,
                       "kind": "video", "duration_seconds": 48.0},
            "inputs": {"transcript": {"created_at": "t1", "complete": True},
                       "tags": {"created_at": "t2", "complete": True}, "topics": None,
                       "organisation": ORGANISATION},
            "organisation": ORGANISATION, "options": OPTIONS, "refs": REFS,
            "screen_texts": ["SECRET SCREEN"], "context": "SECRET TRANSCRIPT",
            "estimated_input_tokens": 100, "warnings": [], "output_dir": str(output_dir),
            "replaces": None, "created_at": "t3",
        }  # fmt: skip
        (job_dir / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
        answer = {
            "hooks": [hook("Got your visa?", ["S1"]), hook("Big news.", ["S1"], "statement"),
                      hook("Guess what came?", ["S1"], "curiosity"), hook("Unfounded.", ["S9"])],
            "script": {"title": "Visa day", "segments": [
                {**segment(["S1"], ["V:office"], "hook"), "subtitle": "My visa came."}]},
            "captions": [caption("instagram-reels", "It came!", translation=""),
                         caption("linkedin", "A proud day.")],
            "hashtags": {"niche": ["studyvisa"], "broad": ["studyabroad"], "brand": ["tilicho"]},
            "review_notes": ["The brief mentions students; the video shows visitors."],
        }  # fmt: skip
        (job_dir / "results" / "answer.json").write_text(
            json.dumps({"answer": answer, "usage": {"input_tokens": 90, "output_tokens": 40}}),
            encoding="utf-8",
        )

        summary = finalize.finalize(job_dir, keep_work=True)

        document = json.loads((output_dir / "copy.json").read_text(encoding="utf-8"))
        self.assertEqual(document["review_status"], "draft")
        self.assertFalse(document["complete"])  # the Instagram Reels caption is untranslated
        self.assertEqual(summary["status"], "incomplete")
        self.assertEqual(summary["hooks"], 3)
        self.assertEqual(document["dropped"], {"hooks": 1, "segments": 0,
                                               "for_their_references": [{"hook": 4, "refs": ["S9"]}]})  # fmt: skip
        self.assertEqual(summary["dropped"], {"hooks": 1, "segments": 0})
        self.assertEqual(document["checks"], [])  # the brand hashtag is the organisation's
        self.assertEqual(summary["review_notes"], answer["review_notes"])
        self.assertEqual(summary["captions"], ["instagram-reels", "linkedin"])
        self.assertEqual(document["organisation"]["name"], "Tilicho Consulting Group")
        metadata = (output_dir / "metadata.json").read_text(encoding="utf-8")
        self.assertNotIn("SECRET TRANSCRIPT", metadata)
        self.assertNotIn("SECRET SCREEN", metadata)
        markdown = (output_dir / "copy.md").read_text(encoding="utf-8")
        self.assertIn("speech 00:00:00-00:00:15, sentence 1", markdown)
        self.assertIn("#tilicho", markdown)
        self.assertIn("office (00:00:00-00:00:12)", markdown)
        self.assertIn("   - Nepali: अनुवाद", markdown)
        self.assertIn("## Notes from the model", markdown)


if __name__ == "__main__":
    unittest.main()
