"""Instagram: what a post gives without a session, what the skill asks
before it reads the browser's cookies, and the reason a link fails. The
error lines are yt-dlp's own (2026.10), copied from real runs."""

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from instagram import (
    browsers_for,
    fetch_meta,
    main,
    meta_command,
    permission_question,
    post_url,
    why_it_failed,
)

EMPTY = (
    "WARNING: [Instagram] AAA111: No CSRF token set by Instagram API\n"
    "ERROR: [Instagram] AAA111: Instagram sent an empty media response. Check if "
    "this post is accessible in your browser without being logged-in. If it is "
    "not, then use --cookies-from-browser or --cookies for the authentication. "
    "See  https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp"
    "  for how to manually pass cookies. Otherwise, if the post is accessible in "
    "browser without being logged-in, please report this issue on  "
    "https://github.com/yt-dlp/yt-dlp/issues?q= , filling out the appropriate "
    "issue template. Confirm you are on the latest version using  yt-dlp -U\n"
)
RESTRICTED = (
    "ERROR: [Instagram] C48gWvyty-t: This content isn't available to everyone: "
    "It can't be seen by certain audiences.\n"
)
RATE_LIMIT = (
    "ERROR: [Instagram] DdHvVqBoycU: The webpage request was redirected to the "
    "login page. You have exceeded the rate-limit for accessing posts anonymously. "
    "Use --cookies-from-browser or --cookies for the authentication.\n"
)
PRIVATE = (
    "ERROR: [Instagram] DdHvVqBoycUxxxxxxxxxxxxxxxxxxxxxxxxxxxx: This content is "
    "only available for registered users who follow this account. Use "
    "--cookies-from-browser or --cookies for the authentication.\n"
)
BROKEN = (
    "WARNING: The program functionality for this site has been marked as broken, "
    "and will probably not work.\n"
    "ERROR: [Instagram] DdHvVqBoycU: Unable to extract data; please report this "
    "issue on  https://github.com/yt-dlp/yt-dlp/issues?q= , filling out the "
    "appropriate issue template. Confirm you are on the latest version using  yt-dlp -U\n"
)
NETWORK = (
    "ERROR: [Instagram] DdHvVqBoycU: Unable to download webpage: <urlopen error "
    "[Errno 8] nodename nor servname provided, or not known> (caused by "
    "TransportError('<urlopen error [Errno 8] nodename nor servname provided, or "
    "not known>'))\n"
)
COOKIES_UNREADABLE = (
    "ERROR: [Errno 1] Operation not permitted: "
    "'/Users/chef/Library/Containers/com.apple.Safari/Data/Library/Cookies/"
    "Cookies.binarycookies'\n"
)


class WhyItFailed(unittest.TestCase):
    """Every failure leaves one reason for the report, and says whether a
    session (the browser's cookies) could get the post."""

    def reason(self, stderr, **kw):
        failure = why_it_failed(stderr, **kw)
        return failure["reason"], failure["session_helps"]

    def test_an_empty_answer_may_be_a_deleted_post_or_one_behind_the_login(self):
        self.assertEqual(self.reason(EMPTY), ("empty", True))

    def test_restricted_private_and_rate_limited_posts_want_a_session(self):
        self.assertEqual(self.reason(RESTRICTED), ("restricted", True))
        self.assertEqual(self.reason(PRIVATE), ("private", True))
        self.assertEqual(self.reason(RATE_LIMIT), ("rate-limited", True))

    def test_once_with_a_session_the_session_no_longer_helps(self):
        # the cookies were already used: asking again for them goes nowhere
        self.assertEqual(self.reason(EMPTY, with_session=True), ("empty", False))
        self.assertEqual(self.reason(PRIVATE, with_session=True), ("private", False))

    def test_a_yt_dlp_that_instagram_has_outrun_asks_for_an_update(self):
        self.assertEqual(self.reason(BROKEN), ("outdated", False))

    def test_no_network_and_unreadable_cookies_are_their_own_reasons(self):
        self.assertEqual(self.reason(NETWORK), ("network", False))
        self.assertEqual(
            self.reason(COOKIES_UNREADABLE, with_session=True), ("cookies", False)
        )

    def test_anything_else_keeps_the_error_line_as_it_came(self):
        failure = why_it_failed("ERROR: [Instagram] X1: Something new\n")
        self.assertEqual(failure["reason"], "other")
        self.assertIn("Something new", failure["message"])

    def test_every_reason_brings_a_sentence_for_the_report(self):
        for stderr in (EMPTY, RESTRICTED, PRIVATE, RATE_LIMIT, BROKEN, NETWORK):
            with self.subTest(stderr=stderr[:60]):
                message = why_it_failed(stderr)["message"]
                self.assertTrue(message.endswith("."))
                self.assertNotIn("ERROR:", message)


class TheCommand(unittest.TestCase):
    """The yt-dlp call for a post's metadata: public unless the Chef said
    yes to a browser, and never one that writes the cookies down."""

    URL = "https://www.instagram.com/reel/DdHvVqBoycU/?igsh=abc"

    def test_without_permission_it_asks_only_for_what_anyone_sees(self):
        command = meta_command(self.URL, yt_dlp="/opt/homebrew/bin/yt-dlp")
        self.assertEqual(
            command,
            [
                "/opt/homebrew/bin/yt-dlp",
                "--skip-download",
                "--ignore-no-formats-error",
                "-J",
                self.URL,
            ],
        )
        self.assertFalse(any("cookies" in part for part in command))

    def test_with_permission_it_reads_the_session_of_the_browser_named(self):
        command = meta_command(self.URL, browser="Safari")
        self.assertEqual(
            command[command.index("--cookies-from-browser") + 1], "safari"
        )
        self.assertNotIn("--cookies", command)

    def test_the_extra_flags_of_the_machine_go_before_the_url(self):
        command = meta_command(self.URL, extra=["--js-runtimes", "node"])
        self.assertEqual(command[-3:], ["--js-runtimes", "node", self.URL])

    def test_a_browser_yt_dlp_cannot_read_is_refused(self):
        with self.assertRaises(ValueError):
            meta_command(self.URL, browser="dia")

    def test_a_flag_that_would_write_the_cookies_to_a_file_is_refused(self):
        for extra in (["--cookies", "jar.txt"], ["--cookies=jar.txt"]):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                meta_command(self.URL, browser="chrome", extra=extra)


class ThePermission(unittest.TestCase):
    """The question before reading any cookies: one for the whole batch,
    naming the posts that need it, what the session is for and that nothing
    is kept."""

    POSTS = [
        "https://www.instagram.com/reel/DdHvVqBoycU/",
        "https://www.instagram.com/p/C48gWvyty-t/",
    ]

    def test_it_names_the_posts_and_what_the_session_is_for(self):
        question = permission_question(self.POSTS, "macos")
        for url in self.POSTS:
            self.assertIn(url, question)
        self.assertIn("Instagram shows 2 posts only", question)
        self.assertIn("only to signed-in", question)

    def test_it_says_nothing_is_kept_and_what_a_no_means(self):
        question = permission_question(self.POSTS[:1], "linux")
        self.assertIn("Instagram shows 1 post only", question)
        self.assertIn("never saved", question)
        self.assertIn("If you say no", question)

    def test_it_offers_only_the_browsers_of_this_system(self):
        self.assertIn("safari", browsers_for("macos"))
        self.assertNotIn("safari", browsers_for("windows"))
        self.assertNotIn("safari", browsers_for("linux"))
        self.assertIn("Safari", permission_question(self.POSTS, "macos"))
        self.assertNotIn("Safari", permission_question(self.POSTS, "windows"))

    def test_on_a_mac_it_warns_of_what_the_system_will_ask(self):
        question = permission_question(self.POSTS, "macos")
        self.assertIn("Full Disk Access", question)
        self.assertIn("Keychain", question)
        self.assertNotIn("Keychain", permission_question(self.POSTS, "linux"))


class FetchMeta(unittest.TestCase):
    """One post's metadata, through a stand-in for yt-dlp: what the skill
    gets back to go on, or the reason for the report."""

    URL = "https://www.instagram.com/reel/DdHvVqBoycU/?igsh=MWQ1ZGUxMzBkMA=="

    def setUp(self):
        self.out = Path(tempfile.mkdtemp()) / "meta.json"
        self.calls = []

    def yt_dlp(self, returncode=0, meta=None, stderr=""):
        def run(command, **_):
            self.calls.append(command)
            stdout = json.dumps(meta) if meta is not None else ""
            return subprocess.CompletedProcess(command, returncode, stdout, stderr)

        return run

    def test_a_public_reel_gives_its_metadata_and_its_clean_address(self):
        meta = {"channel": "chefbosquet", "description": "MAYONESA", "formats": [{"format_id": "1"}]}
        result = fetch_meta(self.URL, self.out, run=self.yt_dlp(meta=meta))
        self.assertEqual(
            result,
            {
                "ok": True,
                "url": "https://www.instagram.com/reel/DdHvVqBoycU/",
                "has_video": True,
                "session_args": [],
            },
        )
        self.assertEqual(json.loads(self.out.read_text())["channel"], "chefbosquet")
        self.assertNotIn("--cookies-from-browser", self.calls[0])

    def test_a_photo_post_has_only_its_text(self):
        meta = {"description": "Receta: ...", "formats": []}
        result = fetch_meta(self.URL, self.out, run=self.yt_dlp(meta=meta))
        self.assertFalse(result["has_video"])

    def test_a_carousel_with_a_video_among_its_photos_has_a_video(self):
        meta = {"_type": "playlist", "entries": [{"formats": []}, {"formats": [{"format_id": "1"}]}]}
        result = fetch_meta(self.URL, self.out, run=self.yt_dlp(meta=meta))
        self.assertTrue(result["has_video"])

    def test_with_a_session_every_later_call_carries_the_same_browser(self):
        meta = {"formats": [{"format_id": "1"}]}
        result = fetch_meta(self.URL, self.out, browser="firefox", run=self.yt_dlp(meta=meta))
        self.assertEqual(result["session_args"], ["--cookies-from-browser", "firefox"])
        self.assertIn("--cookies-from-browser", self.calls[0])

    def test_a_failure_writes_nothing_and_says_if_a_session_could_help(self):
        public = fetch_meta(self.URL, self.out, run=self.yt_dlp(1, stderr=EMPTY))
        self.assertEqual(
            (public["ok"], public["reason"], public["session_helps"]),
            (False, "empty", True),
        )
        self.assertFalse(self.out.exists())
        signed_in = fetch_meta(
            self.URL, self.out, browser="safari", run=self.yt_dlp(1, stderr=EMPTY)
        )
        self.assertFalse(signed_in["session_helps"])

    def test_a_missing_yt_dlp_is_a_reason_too(self):
        def missing(command, **_):
            raise FileNotFoundError(command[0])

        result = fetch_meta(self.URL, self.out, yt_dlp="/nope/yt-dlp", run=missing)
        self.assertEqual((result["ok"], result["reason"]), (False, "no-yt-dlp"))


class PostUrl(unittest.TestCase):
    def test_the_address_of_a_post_drops_the_tracking_and_the_account(self):
        self.assertEqual(
            post_url("https://www.instagram.com/reel/DdHvVqBoycU/?igsh=abc"),
            "https://www.instagram.com/reel/DdHvVqBoycU/",
        )
        self.assertEqual(
            post_url("https://instagram.com/veggie.rabbit/reels/DdjCD3GIX49?utm_source=ig"),
            "https://www.instagram.com/reel/DdjCD3GIX49/",
        )
        self.assertEqual(
            post_url("https://www.instagram.com/p/C3TivygNTId"),
            "https://www.instagram.com/p/C3TivygNTId/",
        )
        self.assertEqual(
            post_url("https://www.instagram.com/tv/C3TivygNTId/"),
            "https://www.instagram.com/p/C3TivygNTId/",
        )
        self.assertIsNone(post_url("https://www.instagram.com/chefbosquet/"))


class CommandLine(unittest.TestCase):
    """What the skill runs: the exit code tells it what to do next (0 go
    on, 3 ask for a session, 1 report it), the JSON what to say."""

    URL = "https://www.instagram.com/p/C48gWvyty-t/"

    def call(self, argv, returncode=0, stdout="", stderr=""):
        commands = []

        def run(command, **_):
            commands.append(command)
            return subprocess.CompletedProcess(command, returncode, stdout, stderr)

        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            code = main(argv, run=run)
        return code, printed.getvalue(), commands

    def test_meta_exits_3_when_a_session_could_get_the_post(self):
        out = str(Path(tempfile.mkdtemp()) / "meta.json")
        code, printed, _ = self.call(["meta", self.URL, out], 1, stderr=RESTRICTED)
        self.assertEqual(code, 3)
        self.assertEqual(json.loads(printed)["reason"], "restricted")

    def test_meta_with_a_browser_exits_1_on_the_same_failure(self):
        out = str(Path(tempfile.mkdtemp()) / "meta.json")
        code, _, commands = self.call(
            ["meta", self.URL, out, "--browser", "chrome", "--yt-dlp", "/x/yt-dlp"],
            1,
            stderr=RESTRICTED,
        )
        self.assertEqual(code, 1)
        self.assertEqual(commands[0][:3], ["/x/yt-dlp", "--cookies-from-browser", "chrome"])

    def test_meta_passes_the_machine_flags_on_to_yt_dlp(self):
        out = str(Path(tempfile.mkdtemp()) / "meta.json")
        code, printed, commands = self.call(
            ["meta", self.URL, out, "--js-runtimes", "node"], stdout='{"formats": []}'
        )
        self.assertEqual(code, 0)
        self.assertEqual(commands[0][-3:], ["--js-runtimes", "node", self.URL])
        self.assertFalse(json.loads(printed)["has_video"])

    def test_ask_prints_the_question(self):
        code, printed, _ = self.call(["ask", "--system", "windows", self.URL])
        self.assertEqual(code, 0)
        self.assertIn(self.URL, printed)
        self.assertIn("Firefox", printed)


if __name__ == "__main__":
    unittest.main()
