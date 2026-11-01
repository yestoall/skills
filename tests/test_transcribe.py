"""Subtitles to plain text: what the recipe is written from. YouTube's
automatic captions repeat each line while the next one rolls in, with word
timings inside; the text has to come out once and clean."""

import unittest

from transcribe import pick_subtitles, vtt_text

AUTO = """WEBVTT
Kind: captions
Language: es

00:00:00.160 --> 00:00:02.869 align:start position:0%
 
hoy<00:00:00.480><c> vamos</c><00:00:00.719><c> a</c><00:00:00.880><c> hacer</c>

00:00:02.869 --> 00:00:02.879 align:start position:0%
hoy vamos a hacer
 

00:00:02.879 --> 00:00:05.390 align:start position:0%
hoy vamos a hacer
una<00:00:03.120><c> tortilla</c><00:00:03.600><c> de</c><00:00:03.760><c> patatas</c>

00:00:05.390 --> 00:00:05.400 align:start position:0%
una tortilla de patatas
 
"""

MANUAL = """WEBVTT

1
00:00:01.000 --> 00:00:04.000
Pela las patatas
y córtalas en láminas.

2
00:00:04.000 --> 00:00:06.000
<i>Fríelas</i> a fuego medio &amp; sin prisa.
"""


class VttText(unittest.TestCase):
    def test_automatic_captions_come_out_once_without_timings(self):
        self.assertEqual(vtt_text(AUTO), "hoy vamos a hacer\nuna tortilla de patatas")

    def test_manual_subtitles_keep_their_lines_without_tags_or_cue_numbers(self):
        self.assertEqual(
            vtt_text(MANUAL),
            "Pela las patatas\ny córtalas en láminas.\nFríelas a fuego medio & sin prisa.",
        )


class PickSubtitles(unittest.TestCase):
    """Subtitles in the language the video is spoken in: the creator's own
    first, then YouTube's automatic ones (the `-orig` track, not one of the
    hundred machine translations). None means Whisper."""

    def test_the_creator_subtitles_in_the_spoken_language_first(self):
        meta = {
            "language": "es-US",
            "subtitles": {"ja": [], "es-MX": [], "en": []},
            "automatic_captions": {"es-orig": [], "es": [], "en": []},
        }
        self.assertEqual(pick_subtitles(meta), ("es-MX", "subs"))

    def test_then_the_automatic_captions_of_the_original_audio(self):
        meta = {
            "language": "es",
            "subtitles": {"en": []},
            "automatic_captions": {"en": [], "es": [], "es-orig": []},
        }
        self.assertEqual(pick_subtitles(meta), ("es-orig", "auto"))

    def test_without_a_known_language_only_an_orig_track_says_which_it_is(self):
        meta = {"language": None, "automatic_captions": {"it-orig": [], "es": []}}
        self.assertEqual(pick_subtitles(meta), ("it-orig", "auto"))

    def test_nothing_in_the_spoken_language_means_whisper(self):
        self.assertIsNone(pick_subtitles({"language": None, "automatic_captions": {}}))
        self.assertIsNone(
            pick_subtitles({"language": "es", "subtitles": {"en": []}})
        )
        self.assertIsNone(pick_subtitles({}))


if __name__ == "__main__":
    unittest.main()
