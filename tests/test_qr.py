"""The QR code generator, against matrices taken once from another encoder
(qr_references.json, from node-qrcode 1.5.4), and its PNG read back byte by byte."""

import json
import struct
import unittest
import zlib
from pathlib import Path

from qr import (
    QrTooLong,
    balance_penalty,
    finder_like_penalty,
    penalty,
    png_bytes,
    qr_matrix,
    runs_penalty,
    text_art,
)

REFERENCES = json.loads(
    (Path(__file__).with_name("qr_references.json")).read_text(encoding="utf-8")
)


def as_rows(matrix):
    return ["".join("1" if module else "0" for module in row) for row in matrix]


class Matrix(unittest.TestCase):
    def test_every_version_and_mask_matches_the_other_encoder(self):
        for case in REFERENCES["masked"]:
            with self.subTest(version=case["version"], mask=case["mask"]):
                self.assertEqual(
                    as_rows(qr_matrix(case["text"], mask=case["mask"])), case["rows"]
                )

    def test_it_chooses_the_mask_with_the_lowest_penalty(self):
        # Any mask scans, and encoders differ on this: node-qrcode doesn't count
        # rule 4 as the standard does, so its choice is no reference
        for case in REFERENCES["masked"]:
            chosen = penalty(qr_matrix(case["text"]))
            others = [penalty(qr_matrix(case["text"], mask=m)) for m in range(8)]
            self.assertEqual(chosen, min(others), case["version"])

    def test_the_smallest_version_that_fits_is_the_one_it_uses(self):
        for text, size in (
            ("x" * 14, 21),
            ("x" * 15, 25),
            ("x" * 106, 41),
            ("x" * 107, 45),
            ("x" * 213, 57),
        ):
            self.assertEqual(len(qr_matrix(text)), size, len(text))

    def test_the_length_that_counts_is_in_bytes(self):
        self.assertEqual(len(qr_matrix("ñ" * 7)), 21)
        self.assertEqual(len(qr_matrix("ñ" * 8)), 25)

    def test_more_than_fits_is_an_error(self):
        with self.assertRaises(QrTooLong):
            qr_matrix("x" * 214)


class PenaltyRules(unittest.TestCase):
    """The cases worked out by hand from the standard."""

    def test_rule_1_counts_runs_of_five_or_more(self):
        self.assertEqual(runs_penalty([True] * 4), 0)
        self.assertEqual(runs_penalty([True] * 5), 3)
        self.assertEqual(runs_penalty([True] * 7), 5)
        self.assertEqual(runs_penalty([True] * 5 + [False] * 6), 7)

    def test_rule_2_counts_each_square_of_one_colour(self):
        three_by_three = [[True] * 3 for _ in range(3)]
        # 4 squares (12), and the 3 rows and 3 columns are too short for rule 1
        self.assertEqual(penalty(three_by_three) - balance_penalty(9, 9), 12)

    def test_rule_3_counts_what_looks_like_a_finder_with_light_to_one_side(self):
        pattern = [c == "1" for c in "10111010000"]
        self.assertEqual(finder_like_penalty(pattern), 40)
        self.assertEqual(finder_like_penalty(pattern[::-1]), 40)
        self.assertEqual(finder_like_penalty([c == "1" for c in "10111011111"]), 0)

    def test_rule_4_counts_the_distance_to_half_dark(self):
        self.assertEqual(balance_penalty(50, 100), 0)
        self.assertEqual(balance_penalty(52, 100), 0)  # node-qrcode says 10
        self.assertEqual(balance_penalty(47, 100), 0)
        self.assertEqual(balance_penalty(44, 100), 10)
        self.assertEqual(balance_penalty(39, 100), 20)
        self.assertEqual(balance_penalty(61, 100), 20)
        self.assertEqual(balance_penalty(100, 100), 100)


class Png(unittest.TestCase):
    def chunks(self, png):
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        at, found = 8, []
        while at < len(png):
            length = struct.unpack(">I", png[at : at + 4])[0]
            kind, body = png[at + 4 : at + 8], png[at + 8 : at + 8 + length]
            crc = struct.unpack(">I", png[at + 8 + length : at + 12 + length])[0]
            self.assertEqual(crc, zlib.crc32(kind + body))
            found.append((kind, body))
            at += 12 + length
        return found

    def pixels(self, png):
        chunks = self.chunks(png)
        self.assertEqual([kind for kind, _ in chunks], [b"IHDR", b"IDAT", b"IEND"])
        width, height, depth, color, _, _, _ = struct.unpack(">IIBBBBB", chunks[0][1])
        self.assertEqual((depth, color), (8, 0))  # 8-bit greyscale
        raw = zlib.decompress(chunks[1][1])
        rows = [raw[i * (width + 1) : (i + 1) * (width + 1)] for i in range(height)]
        self.assertEqual({row[0] for row in rows}, {0})  # No filter
        return width, height, [row[1:] for row in rows]

    def test_each_module_is_a_black_or_white_square_with_a_quiet_zone(self):
        matrix = [[True, False], [False, True]]
        width, height, rows = self.pixels(png_bytes(matrix, scale=3, border=1))
        self.assertEqual((width, height), (12, 12))
        white, black = 255, 0
        self.assertEqual(rows[0], bytes([white] * 12))
        self.assertEqual(
            rows[3], bytes([white] * 3 + [black] * 3 + [white] * 3 + [white] * 3)
        )
        self.assertEqual(
            rows[6], bytes([white] * 3 + [white] * 3 + [black] * 3 + [white] * 3)
        )

    def test_by_default_it_has_the_quiet_zone_the_standard_asks_for(self):
        matrix = qr_matrix("nevera")
        width, _, rows = self.pixels(png_bytes(matrix))
        scale = width // (len(matrix) + 8)
        self.assertGreaterEqual(scale, 8)  # Big enough to scan from a screen
        self.assertEqual(width, scale * (len(matrix) + 8))
        self.assertEqual(rows[4 * scale - 1], bytes([255] * width))
        self.assertEqual(rows[4 * scale][4 * scale], 0)  # The finder's corner


class TextArt(unittest.TestCase):
    """Painted is light, for a dark terminal: what's left unpainted is the code."""

    def test_two_modules_share_each_character(self):
        self.assertEqual(
            text_art([[True, False], [False, True]], border=1), "█▀██\n██▄█"
        )

    def test_an_odd_number_of_rows_ends_in_quiet_zone(self):
        self.assertEqual(text_art([[True]], border=1), "█▀█\n███")

    def test_it_reads_back_as_the_same_code_with_its_quiet_zone(self):
        matrix = qr_matrix("nevera://import?from=http%3A%2F%2F192.168.1.39%3A8765")
        lines = text_art(matrix).split("\n")
        tops = {"█": True, "▀": True, "▄": False, " ": False}
        bottoms = {"█": True, "▄": True, "▀": False, " ": False}
        rows = []
        for line in lines:
            rows.append([tops[character] for character in line])
            rows.append([bottoms[character] for character in line])
        side = len(matrix)
        self.assertEqual(len(rows[0]), side + 8)
        self.assertTrue(all(all(row) for row in rows[:4]))
        self.assertTrue(all(all(row) for row in rows[4 + side :]))
        self.assertTrue(all(all(row[:4]) and all(row[4 + side :]) for row in rows))
        read = [[not light for light in row[4 : 4 + side]] for row in rows[4 : 4 + side]]
        self.assertEqual(read, matrix)


if __name__ == "__main__":
    unittest.main()
