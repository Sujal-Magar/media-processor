from __future__ import annotations

import unittest

import helpers  # noqa: F401  (puts the repo root on sys.path)

from lib import numbers

DATA = [48200, 34900, 38.11, 27, 9, 3412, -8.64, 2026]


class UnmatchedTest(unittest.TestCase):
    def test_display_forms_of_a_recorded_number_match(self):
        for line in ("48,200 people", "48.2K people", "48.2k people", "48K people",
                     "48200 people", "up 38%", "up 38 per cent", "up 38.1%"):  # fmt: skip
            self.assertEqual(numbers.unmatched(line, DATA), [], line)

    def test_a_fall_matches_without_its_sign(self):
        self.assertEqual(numbers.unmatched("down 9% on last month", DATA), [])

    def test_number_words_count_but_one_does_not(self):
        self.assertEqual(numbers.unmatched("Nine more enquiries. One thing didn't land.", DATA), [])
        self.assertEqual(numbers.unmatched("eleven new posts", DATA), ["eleven"])

    def test_dates_are_not_figures(self):
        self.assertEqual(numbers.unmatched("posted on 8 October 2026 and October 22", DATA), [])

    def test_a_number_the_data_does_not_hold_is_listed_as_written(self):
        self.assertEqual(numbers.unmatched("48,000 people saw 52% of it", DATA), ["48,000", "52"])

    def test_rounding_stays_within_the_shown_precision(self):
        self.assertEqual(numbers.unmatched("15.4K reached", [15400]), [])
        self.assertEqual(numbers.unmatched("15.5K reached", [15400]), ["15.5K"])


class RatiosTest(unittest.TestCase):
    def test_ratios_and_fractions_are_found(self):
        self.assertEqual(
            numbers.ratios("three times your usual post, twice the saves, a quarter of "
                           "your posts, 3.2× the reach"),
            ["three times your", "twice", "quarter", "3.2×"],
        )  # fmt: skip

    def test_plain_numbers_and_counts_are_not_ratios(self):
        self.assertEqual(numbers.ratios("27 enquiries, up 9 on September"), [])
        self.assertEqual(numbers.ratios("played 9,000 times and shared 40 times."), [])

    def test_a_number_of_times_compared_is_a_ratio(self):
        self.assertEqual(numbers.ratios("3 times more shares, 1.5x the saves"), ["3 times more", "1.5x"])


if __name__ == "__main__":
    unittest.main()
