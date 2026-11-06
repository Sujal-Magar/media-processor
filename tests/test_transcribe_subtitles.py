from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from helpers import load_script

from lib import subtitles as shared

subtitles = load_script("transcribe", "subtitles")

TRANSCRIPT = {
    "complete": False,
    "parts": [
        {"index": 0, "start_seconds": 0.0, "end_seconds": 10.0, "missing": False,
         "text": "SPEAKER 0: Hello there. Welcome to the office.\nSPEAKER 1: Thank you!"},
        {"index": 1, "start_seconds": 10.0, "end_seconds": 20.0, "missing": True, "text": ""},
        {"index": 2, "start_seconds": 20.0, "end_seconds": 26.0, "missing": False,
         "text": "मेरो भिसा आयो। A & B <3"},
    ],
}  # fmt: skip


class PiecesTest(unittest.TestCase):
    def test_a_short_sentence_stays_whole(self):
        self.assertEqual(shared.pieces("Hello there."), ["Hello there."])

    def test_a_long_sentence_is_cut_at_clause_ends_within_two_lines(self):
        sentence = ("We help students choose a course, apply for the visa, and settle in, "
                    "and we stay in touch after they arrive in Australia.")  # fmt: skip
        found = shared.pieces(sentence)
        self.assertTrue(all(len(piece) <= shared.CUE_CHARS for piece in found), found)
        self.assertEqual(" ".join(found), sentence)
        self.assertTrue(found[0].endswith(","), found)

    def test_a_long_clause_is_cut_between_words(self):
        sentence = " ".join(["word"] * 40)
        found = shared.pieces(sentence)
        self.assertGreater(len(found), 1)
        self.assertTrue(all(len(piece) <= shared.CUE_CHARS for piece in found))
        self.assertEqual(" ".join(found), sentence)

    def test_wrap_splits_at_the_space_nearest_the_middle(self):
        self.assertEqual(shared.wrap("short line"), ["short line"])
        lines = shared.wrap("We help students choose a course and apply for the visa.")
        self.assertEqual(len(lines), 2)
        self.assertTrue(all(len(line) <= shared.LINE_CHARS for line in lines))

    def test_every_cue_wraps_within_the_line_limit(self):
        # Words of uneven length, as in the cues that came out 43 to 45 characters wide.
        words = "students apply visa counselling Australia subclass-500 we help you".split()
        for size in range(10, 60):
            sentence = " ".join(words[i % len(words)] for i in range(size)) + "."
            for piece in shared.pieces(sentence):
                self.assertTrue(all(len(line) <= shared.LINE_CHARS for line in shared.wrap(piece)),
                                (size, piece))  # fmt: skip

    def test_wrap_moves_off_the_middle_to_keep_both_lines_short(self):
        # The space nearest the middle would leave a 43-character second line.
        text = "a" * 40 + " b " + "c" * 41
        self.assertEqual(shared.wrap(text), ["a" * 40 + " b", "c" * 41])


class CuesTest(unittest.TestCase):
    def setUp(self):
        self.found = shared.cues(TRANSCRIPT)

    def test_sentences_are_cues_with_their_speaker_and_short_ones_join_a_neighbour(self):
        # "Hello there." is short, so it joins the next sentence of the same speaker;
        # "Thank you!" has no neighbour of its own speaker, so it stays alone.
        self.assertEqual([(c["text"], c["speaker"]) for c in self.found], [
            ("Hello there. Welcome to the office.", "SPEAKER 0"), ("Thank you!", "SPEAKER 1"),
            ("मेरो भिसा आयो। A & B <3", None)])  # fmt: skip

    def test_a_part_s_time_is_shared_by_length_without_gaps(self):
        first = self.found[:2]
        self.assertEqual(first[0]["start"], 0.0)
        self.assertAlmostEqual(first[0]["end"], first[1]["start"])
        self.assertAlmostEqual(first[1]["end"], 10.0)
        # The first cue holds three times the text of "Thank you!", so it lasts longer.
        self.assertGreater(first[0]["end"] - first[0]["start"], first[1]["end"] - first[1]["start"])

    def test_a_missing_part_gives_no_cues(self):
        self.assertFalse([c for c in self.found if 10.0 <= c["start"] < 20.0])
        self.assertEqual(self.found[2]["start"], 20.0)

    def test_a_short_cue_between_long_ones_still_gets_about_a_second(self):
        # Fits a cue exactly, so neither neighbour can take "Yes." as well.
        long = "We help students choose the right course and then apply for the visa step by step."
        transcript = {"parts": [{"start_seconds": 0.0, "end_seconds": 9.0, "missing": False,
                                 "text": f"{long} Yes. {long}"}]}  # fmt: skip
        found = shared.cues(transcript)
        self.assertEqual([c["text"] for c in found], [long, "Yes.", long])
        share = shared.MIN_TIME_CHARS / (2 * len(long) + shared.MIN_TIME_CHARS)
        self.assertAlmostEqual(found[1]["end"] - found[1]["start"], 9.0 * share)

    def test_short_pieces_do_not_join_across_speakers_or_past_a_cue(self):
        units = [("Yes.", "SPEAKER 0"), ("No.", "SPEAKER 1"), ("x" * 82, "SPEAKER 1"), ("Ok.", "SPEAKER 1")]
        self.assertEqual(shared.joined(units), [("Yes.", "SPEAKER 0"), ("No.", "SPEAKER 1"),
                                                   ("x" * 82, "SPEAKER 1"), ("Ok.", "SPEAKER 1")])  # fmt: skip


class FormatTest(unittest.TestCase):
    def test_stamps(self):
        self.assertEqual(shared.stamp(3725.5, "."), "01:02:05.500")
        self.assertEqual(shared.stamp(1.2345, ","), "00:00:01,234")

    def test_webvtt_has_its_header_the_note_voices_and_escapes(self):
        vtt = subtitles.to_vtt(shared.cues(TRANSCRIPT), complete=False)
        self.assertTrue(vtt.startswith("WEBVTT\n\nNOTE\nMade from transcript.json. Times are estimated"))
        self.assertIn("Parts missing from the transcript have no cues.", vtt)
        self.assertIn("1\n00:00:00.000 --> 00:00:", vtt)
        self.assertIn("<v SPEAKER 0>Hello there.", vtt)
        self.assertIn("A &amp; B &lt;3", vtt)

    def test_srt_is_numbered_with_comma_times_and_no_labels(self):
        srt = shared.to_srt(shared.cues(TRANSCRIPT))
        self.assertTrue(srt.startswith("1\n00:00:00,000 --> 00:00:"))
        self.assertIn("\n\n3\n00:00:", srt)
        self.assertNotIn("SPEAKER", srt)
        self.assertIn("A & B <3", srt)


class WriteTest(unittest.TestCase):
    def test_both_files_are_written_next_to_the_transcript(self):
        with tempfile.TemporaryDirectory() as folder:
            count, files = subtitles.write_subtitles(Path(folder), TRANSCRIPT)
            self.assertEqual((count, files), (3, ["transcript.vtt", "transcript.srt"]))
            self.assertTrue((Path(folder) / "transcript.vtt").read_text().startswith("WEBVTT"))

    def test_no_speech_writes_nothing(self):
        silent = {"complete": True, "parts": [{"start_seconds": 0, "end_seconds": 5, "text": ""}]}
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(subtitles.write_subtitles(Path(folder), silent), (0, []))
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_only_result_folders_are_accepted(self):
        with self.assertRaises(SystemExit):
            subtitles.result_dir("/tmp")


if __name__ == "__main__":
    unittest.main()
