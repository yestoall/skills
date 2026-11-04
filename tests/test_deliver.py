"""Getting the batch to the phone: the AirDrop window, with the Finder when that
doesn't send it, a copy to iCloud Drive, or a server on the local network that
Nevera downloads it from."""

import http.client
import io
import ipaddress
import os
import re
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlsplit

from deliver import (
    AIRDROP_SCRIPT,
    AIRDROP_TIMEOUT,
    DeliverError,
    QR_GRACE,
    QR_TIMEOUT,
    default_route_ip,
    local_ip,
    main,
    open_image,
    qr_link,
    send_to_icloud,
    serve_batch,
)
import deliver as deliver_module
from qr import png_bytes, qr_matrix, text_art


class ICloud(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.batch = self.home / "nevera-lote-2026-11-01.zip"
        self.batch.write_bytes(b"PK")
        self.drive = self.home / "Library/Mobile Documents/com~apple~CloudDocs"

    def test_it_copies_the_batch_to_a_nevera_folder_in_icloud_drive(self):
        self.drive.mkdir(parents=True)
        copy = send_to_icloud(self.batch, self.home)
        self.assertEqual(copy, self.drive / "Nevera" / self.batch.name)
        self.assertEqual(copy.read_bytes(), b"PK")

    def test_the_batch_stays_where_it_was(self):
        self.drive.mkdir(parents=True)
        send_to_icloud(self.batch, self.home)
        self.assertTrue(self.batch.exists())

    def test_a_second_batch_goes_into_the_same_folder(self):
        (self.drive / "Nevera").mkdir(parents=True)
        self.assertEqual(
            send_to_icloud(self.batch, self.home).parent, self.drive / "Nevera"
        )

    def test_without_icloud_drive_on_this_mac_it_says_so(self):
        with self.assertRaisesRegex(DeliverError, "iCloud Drive"):
            send_to_icloud(self.batch, self.home)

    def test_a_batch_that_is_not_there_is_an_error(self):
        self.drive.mkdir(parents=True)
        with self.assertRaisesRegex(DeliverError, "nope.zip"):
            send_to_icloud(self.home / "nope.zip", self.home)


class AirDrop(unittest.TestCase):
    """Runs `deliver.py airdrop` with the machine faked: what matters is which
    commands it starts, and where the batch ends up when AirDrop doesn't send."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.batch = Path(self.tmp.name) / "nevera-lote.zip"
        self.batch.write_bytes(b"PK")

        self.commands = []
        self.swift = 0
        self.xcode_select = 0
        self.which = "/usr/bin/swift"

        def run(command, **kwargs):
            self.commands.append(command[0])
            if command[0] == "swift":
                if isinstance(self.swift, Exception):
                    raise self.swift
                return subprocess.CompletedProcess(command, self.swift, "why", "")
            if command[0] == "xcode-select":
                return subprocess.CompletedProcess(command, self.xcode_select)
            return subprocess.CompletedProcess(command, 0)

        for patcher in (
            mock.patch("deliver.this_system", return_value="macos"),
            mock.patch("deliver.subprocess.run", side_effect=run),
            mock.patch("deliver.shutil.which", side_effect=lambda _: self.which),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def deliver(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(["airdrop", str(self.batch)])
        return code, out.getvalue().strip(), err.getvalue().strip()

    def test_a_send_the_mac_reports_as_done_stays_out_of_the_finder(self):
        self.assertEqual(self.deliver()[:2], (0, "sent"))
        self.assertNotIn("open", self.commands)

    def test_a_failed_send_shows_the_file_in_the_finder_and_says_why(self):
        self.swift = 1
        self.assertEqual(self.deliver(), (0, "finder", "why"))
        self.assertIn("open", self.commands)

    def test_a_send_that_never_ends_shows_the_file_in_the_finder(self):
        self.swift = subprocess.TimeoutExpired("swift", AIRDROP_TIMEOUT)
        self.assertEqual(self.deliver()[:2], (0, "finder"))

    def test_without_swift_it_goes_straight_to_the_finder(self):
        self.which = None
        self.assertEqual(self.deliver()[:2], (0, "finder"))
        self.assertEqual(self.commands, ["open"])

    def test_the_swift_stub_without_the_tools_never_runs(self):
        # Running /usr/bin/swift there can make macOS offer to install them
        self.xcode_select = 2
        self.assertEqual(self.deliver()[:2], (0, "finder"))
        self.assertNotIn("swift", self.commands)

    def test_a_batch_that_is_not_there_is_an_error(self):
        self.batch.unlink()
        code, out, err = self.deliver()
        self.assertEqual((code, out), (1, ""))
        self.assertIn("nevera-lote.zip", err)
        self.assertEqual(self.commands, [])

    def test_the_swift_script_travels_with_this_one(self):
        self.assertTrue(AIRDROP_SCRIPT.is_file())
        self.assertLess(self.script_wait(), AIRDROP_TIMEOUT)

    def script_wait(self):
        text = AIRDROP_SCRIPT.read_text(encoding="utf-8")
        return float(re.search(r"waitSeconds = ([\d.]+)", text).group(1))


TOKEN = "d7307b775524dfb8add214c1334a8d89"
# The fake IP in QrCommand has to count as private to reach the real server
TEST_NETWORKS = (ipaddress.ip_network("127.0.0.0/8"),)


class QrLink(unittest.TestCase):
    """The link is a public contract: Nevera reads it, and these are the cases
    of isBatchDownloadUrl in Nevera's src/utils/incoming.test.ts."""

    def test_it_has_the_exact_form_nevera_reads(self):
        self.assertEqual(
            qr_link("nevera", "192.168.1.39", 58663, TOKEN),
            "nevera://import?from=http%3A%2F%2F192.168.1.39%3A58663%2F"
            "d7307b775524dfb8add214c1334a8d89%2Flote.zip",
        )

    def test_another_variant_only_changes_the_scheme(self):
        self.assertTrue(
            qr_link("nevera-dev", "10.0.0.2", 8080, TOKEN).startswith(
                "nevera-dev://import?from=http%3A%2F%2F10.0.0.2%3A8080%2F"
            )
        )


class LocalIp(unittest.TestCase):
    def route(self, ip=None, error=None):
        return mock.patch(
            "deliver.default_route_ip", return_value=ip, side_effect=error
        )

    def test_it_accepts_what_nevera_accepts(self):
        for ip in (
            "192.168.1.39",
            "10.0.0.2",
            "172.16.0.1",
            "172.31.255.254",
            "172.20.10.2",  # an iPhone's personal hotspot
        ):
            with self.route(ip):
                self.assertEqual(local_ip(), ip)

    def test_it_rejects_what_nevera_rejects_and_proposes_another_way(self):
        for ip in (
            "8.8.8.8",
            "172.15.0.1",
            "172.32.0.1",
            "192.167.1.1",
            "127.0.0.1",
            "169.254.1.1",
        ):
            with self.route(ip), self.assertRaisesRegex(DeliverError, "another way"):
                local_ip()

    def test_without_a_network_it_says_so_and_proposes_another_way(self):
        unreachable = OSError("Network is unreachable")
        with self.route(error=unreachable):
            with self.assertRaisesRegex(DeliverError, "another way"):
                local_ip()


class QrServer(unittest.TestCase):
    """The real server, on this machine, with its times made short."""

    BYTES = b"PK batch"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.batch = Path(self.tmp.name) / "nevera-lote.zip"
        self.batch.write_bytes(self.BYTES)
        self.lines = []
        self.got_link = threading.Event()

    def start(self, grace=0.05, timeout=5.0, finish=5.0):
        def emit(line):
            self.lines.append(line)
            self.got_link.set()

        self.thread = threading.Thread(
            target=serve_batch,
            args=(self.batch, "127.0.0.1", "nevera", emit),
            kwargs={"grace": grace, "timeout": timeout, "finish": finish},
        )
        self.thread.start()
        self.addCleanup(self.thread.join)
        self.assertTrue(self.got_link.wait(5))
        link = urlsplit(self.lines[0])
        self.url = urlsplit(parse_qs(link.query)["from"][0])

    def request(self, method="GET", path=None):
        connection = http.client.HTTPConnection(
            self.url.hostname, self.url.port, timeout=5
        )
        self.addCleanup(connection.close)
        connection.request(method, path if path is not None else self.url.path)
        return connection.getresponse()

    def finished(self):
        self.thread.join(10)
        self.assertFalse(self.thread.is_alive())
        return self.lines[1:]

    def assert_port_closed(self):
        with self.assertRaises(OSError):
            socket.create_connection((self.url.hostname, self.url.port), timeout=1)

    def test_the_link_comes_first_with_a_token_of_32_hex_characters(self):
        self.start(timeout=0.05)
        self.assertRegex(self.url.path, r"^/[0-9a-f]{32}/lote\.zip$")
        self.assertEqual(self.finished(), ["timeout"])

    def test_every_run_has_its_own_token(self):
        self.start(timeout=0.05)
        first = self.url.path
        self.finished()
        self.lines.clear()
        self.got_link.clear()
        self.start(timeout=0.05)
        self.assertNotEqual(self.url.path, first)
        self.finished()

    def test_it_serves_the_bytes_says_downloaded_and_closes_the_port(self):
        self.start()
        response = self.request()
        self.assertEqual(response.status, 200)
        self.assertEqual(response.read(), self.BYTES)
        self.assertEqual(self.finished(), ["downloaded"])
        self.assert_port_closed()

    def test_it_tells_the_size_so_nevera_can_check_it_first(self):
        self.start()
        response = self.request()
        self.assertEqual(response.getheader("Content-Length"), str(len(self.BYTES)))
        response.read()
        self.finished()

    def test_nobody_scans_it_says_timeout_and_closes_the_port(self):
        self.start(timeout=0.1)
        self.assertEqual(self.finished(), ["timeout"])
        self.assert_port_closed()

    def test_head_answers_without_a_body_and_is_not_a_download(self):
        self.start(timeout=0.3)
        response = self.request("HEAD")
        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader("Content-Length"), str(len(self.BYTES)))
        self.assertEqual(response.read(), b"")
        self.assertEqual(self.finished(), ["timeout"])

    def test_anything_else_is_a_404_and_is_not_a_download(self):
        self.start(timeout=0.5)
        token = self.url.path.split("/")[1]
        for path in (
            "/",
            "/lote.zip",
            f"/{token}",
            f"/{token}/",
            f"/{token}/other.zip",
            f"/{'0' * 32}/lote.zip",
            f"/{token}/lote.zip?a=1",
            f"/{token}/lote.zip/",
            f"//{token}/lote.zip",
        ):
            response = self.request(path=path)
            self.assertEqual(response.status, 404, path)
            response.read()
        self.assertEqual(self.finished(), ["timeout"])

    def test_other_methods_on_the_right_path_are_a_404_too(self):
        self.start(timeout=0.5)
        for method in ("POST", "PUT", "DELETE", "PATCH", "OPTIONS", "TRACE", "PROPFIND"):
            response = self.request(method)
            self.assertEqual(response.status, 404, method)
            response.read()
        self.assertEqual(self.finished(), ["timeout"])

    def test_it_says_downloaded_at_once_without_waiting_for_the_grace(self):
        self.start(grace=1.0)
        self.request().read()
        deadline = time.monotonic() + 0.5
        while "downloaded" not in self.lines and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(self.lines[1:], ["downloaded"])
        self.assertTrue(self.thread.is_alive())

    def test_scanning_again_within_the_grace_downloads_it_again(self):
        self.start(grace=0.5)
        self.request().read()
        again = self.request()
        self.assertEqual(again.status, 200)
        self.assertEqual(again.read(), self.BYTES)
        self.assertEqual(self.finished(), ["downloaded"])
        self.assert_port_closed()

    def big_batch(self):
        # More than the socket buffers hold, so the server has to wait for us
        self.batch.write_bytes(bytes(64 * 1024 * 1024))

    def test_a_download_in_progress_when_the_grace_ends_finishes(self):
        self.big_batch()
        self.start(grace=0.2)
        self.request().read()
        slow = self.request()
        first = slow.read(1024)
        time.sleep(0.4)
        rest = slow.read()
        self.assertEqual(len(first) + len(rest), self.batch.stat().st_size)
        self.assertEqual(self.finished(), ["downloaded"])

    def test_a_download_cut_halfway_is_not_a_download(self):
        self.big_batch()
        self.start(timeout=0.5)
        response = self.request()
        response.read(1024)
        response.close()
        self.assertEqual(self.finished(), ["timeout"])

    def raw_client(self, data=b""):
        client = socket.create_connection((self.url.hostname, self.url.port))
        self.addCleanup(client.close)
        client.sendall(data)
        return client

    def test_a_client_that_reads_nothing_is_not_a_download(self):
        # The whole batch fits in the socket buffers, so sending it proves nothing
        self.start(timeout=0.3, finish=0.2)
        self.raw_client(f"GET {self.url.path} HTTP/1.0\r\n\r\n".encode())
        self.assertEqual(self.finished(), ["timeout"])

    def test_a_client_that_goes_away_without_reading_is_not_a_download(self):
        self.start(timeout=0.3)
        client = self.raw_client(f"GET {self.url.path} HTTP/1.0\r\n\r\n".encode())
        client.close()
        self.assertEqual(self.finished(), ["timeout"])

    def test_a_stuck_connection_without_the_token_cannot_stop_the_end(self):
        self.start(timeout=0.1)
        self.raw_client(b"GET /")  # A request line that never ends
        started = time.monotonic()
        self.assertEqual(self.finished(), ["timeout"])
        self.assertLess(time.monotonic() - started, 2)

    def test_a_download_that_never_ends_cannot_stop_the_end_either(self):
        self.big_batch()
        self.start(timeout=0.1, finish=0.2)
        self.raw_client(f"GET {self.url.path} HTTP/1.0\r\n\r\n".encode())
        started = time.monotonic()
        self.assertEqual(self.finished(), ["timeout"])
        self.assertLess(time.monotonic() - started, 2)
        self.assert_port_closed()

    def test_a_download_in_progress_when_the_time_runs_out_gets_the_grace(self):
        self.big_batch()
        self.start(timeout=0.2, grace=0.5)
        slow = self.request()
        first = slow.read(1024)
        time.sleep(0.3)
        rest = slow.read()
        self.assertEqual(len(first) + len(rest), self.batch.stat().st_size)
        self.batch.write_bytes(self.BYTES)
        deadline = time.monotonic() + 1
        while "downloaded" not in self.lines and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(self.lines[1:], ["downloaded"])
        again = self.request()
        self.assertEqual(again.read(), self.BYTES)
        self.assertEqual(self.finished(), ["downloaded"])

    def test_a_broken_request_line_leaves_no_traceback(self):
        err = io.StringIO()
        with redirect_stderr(err):
            self.start(timeout=0.2)
            client = self.raw_client(b"GET\t/x\tHTTP/1.0\r\n\r\n")
            client.recv(1024)
            self.assertEqual(self.finished(), ["timeout"])
        self.assertEqual(err.getvalue(), "")

    def test_it_listens_only_on_that_ip(self):
        try:
            other_ip = default_route_ip()
        except OSError:
            self.skipTest("this machine has no network")
        self.start(timeout=0.2)
        with self.assertRaises(OSError):
            socket.create_connection((other_ip, self.url.port), timeout=0.1)
        self.finished()


class QrCommand(unittest.TestCase):
    """`deliver.py qr`, on any system, with the IP and the times faked."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.batch = Path(self.tmp.name) / "nevera-lote.zip"
        self.batch.write_bytes(b"PK")

    def deliver(self, *args, ip="127.0.0.1", system="linux", opens=True):
        out, err = io.StringIO(), io.StringIO()
        self.opened = []

        def fake_open(path):
            self.opened.append((path, path.read_bytes()))
            if isinstance(opens, BaseException):
                raise opens
            if callable(opens):
                opens(out.getvalue().splitlines()[0], path)
                return True
            return opens

        with mock.patch("deliver.this_system", return_value=system), mock.patch(
            "deliver.default_route_ip", return_value=ip
        ), mock.patch("deliver.PRIVATE_NETWORKS", TEST_NETWORKS), mock.patch(
            "deliver.QR_TIMEOUT", 0.05
        ), mock.patch(
            "deliver.QR_FINISH", 0.05
        ), mock.patch(
            "deliver.QR_GRACE", 0.3
        ), mock.patch(
            "deliver.open_image", fake_open
        ), redirect_stdout(
            out
        ), redirect_stderr(
            err
        ):
            code = main(["qr", *map(str, args)])
        return code, out.getvalue().splitlines(), err.getvalue()

    def test_it_works_on_any_system_and_ends_in_timeout(self):
        for system in ("macos", "windows", "linux"):
            code, out, _ = self.deliver(self.batch, system=system)
            self.assertEqual(code, 0)
            self.assertTrue(out[0].startswith("nevera://import?from=http%3A"))
            self.assertEqual(out[-1], "timeout")

    def test_the_scheme_can_be_another_variant(self):
        _, out, _ = self.deliver(self.batch, "--scheme", "nevera-dev")
        self.assertTrue(out[0].startswith("nevera-dev://import?from="))

    def test_a_scheme_that_cannot_be_one_is_an_error(self):
        code, out, err = self.deliver(self.batch, "--scheme", "not a scheme")
        self.assertEqual((code, out), (1, []))
        self.assertIn("not a scheme", err)

    def test_a_batch_that_is_not_there_is_an_error(self):
        self.batch.unlink()
        code, out, err = self.deliver(self.batch)
        self.assertEqual((code, out), (1, []))
        self.assertIn("nevera-lote.zip", err)

    def test_a_public_ip_is_an_error_that_proposes_another_way(self):
        code, out, err = self.deliver(self.batch, ip="8.8.8.8")
        self.assertEqual((code, out), (1, []))
        self.assertIn("another way", err)

    def test_it_waits_long_enough_to_scan_and_to_scan_again(self):
        self.assertEqual(QR_TIMEOUT, 300)
        self.assertEqual(QR_GRACE, 120)

    def test_it_opens_the_qr_code_of_the_link_it_prints(self):
        _, out, _ = self.deliver(self.batch)
        (path, image), = self.opened
        self.assertEqual(path.suffix, ".png")
        self.assertEqual(image, png_bytes(qr_matrix(out[0])))

    def test_it_prints_the_qr_code_between_the_link_and_how_it_ended(self):
        _, out, _ = self.deliver(self.batch)
        self.assertEqual("\n".join(out[1:-1]), text_art(qr_matrix(out[0])))

    def test_a_terminal_that_cannot_print_blocks_still_gets_the_image(self):
        opened = []
        ascii_only = io.TextIOWrapper(io.BytesIO(), encoding="ascii")
        with mock.patch("deliver.open_image", opened.append), redirect_stdout(
            ascii_only
        ):
            deliver_module.show_qr("nevera://import", Path(self.tmp.name))
        self.assertEqual([path.name for path in opened], ["nevera-qr.png"])

    def test_the_image_is_gone_when_it_ends(self):
        self.deliver(self.batch)
        (path, _), = self.opened
        self.assertFalse(path.exists())
        self.assertFalse(path.parent.exists())

    def test_the_image_stays_for_scanning_again_and_goes_when_it_ends(self):
        seen = {}

        def phone_downloads_it(link, path):
            def download():
                url = parse_qs(urlsplit(link).query)["from"][0]
                parts = urlsplit(url)
                connection = http.client.HTTPConnection(parts.hostname, parts.port)
                connection.request("GET", parts.path)
                connection.getresponse().read()
                connection.close()
                time.sleep(0.1)  # Within the grace
                seen["during_the_grace"] = path.exists()

            phone = threading.Thread(target=download)
            phone.start()
            self.addCleanup(phone.join)

        with mock.patch("deliver.QR_TIMEOUT", 5):
            _, out, _ = self.deliver(self.batch, opens=phone_downloads_it)
        (path, _), = self.opened
        self.assertEqual(out[-1], "downloaded")
        self.assertTrue(seen["during_the_grace"])
        self.assertFalse(path.exists())

    def test_when_it_cannot_open_it_says_where_it_is_and_goes_on(self):
        code, out, err = self.deliver(self.batch, opens=False)
        (path, _), = self.opened
        self.assertEqual(code, 0)
        self.assertTrue(out[0].startswith("nevera://import?from="))
        self.assertEqual(out[-1], "timeout")
        self.assertIn(str(path), err)

    def test_interrupted_it_leaves_no_image_and_closes(self):
        code, out, _ = self.deliver(self.batch, opens=KeyboardInterrupt())
        (path, _), = self.opened
        self.assertEqual(code, 130)
        self.assertFalse(path.parent.exists())
        self.assertNotIn("timeout", out)
        self.assertNotIn("downloaded", out)

    def test_a_scheme_too_long_for_a_qr_code_still_prints_the_link(self):
        scheme = "n" * 200
        code, out, err = self.deliver(self.batch, "--scheme", scheme)
        self.assertEqual(self.opened, [])
        self.assertEqual(code, 0)
        self.assertTrue(out[0].startswith(scheme))
        self.assertIn("QR code", err)

    def test_a_flag_without_its_value_shows_the_usage(self):
        code, out, _ = self.deliver(self.batch, "--scheme")
        self.assertEqual((code, out), (2, []))


class OpenImage(unittest.TestCase):
    def opening(self, returncode=None, error=None, system="macos"):
        process = mock.Mock()
        if returncode is None:
            process.wait.side_effect = subprocess.TimeoutExpired("open", 2)
        else:
            process.wait.return_value = returncode
        with mock.patch("deliver.this_system", return_value=system), mock.patch(
            "deliver.subprocess.Popen", return_value=process, side_effect=error
        ) as popen:
            return open_image(Path("/tmp/qr.png")), popen

    def test_it_asks_this_system_to_open_it(self):
        opened, popen = self.opening(returncode=0)
        self.assertTrue(opened)
        self.assertEqual(popen.call_args[0][0], ["open", "/tmp/qr.png"])

    def test_a_viewer_that_stays_running_counts_as_opened(self):
        # Some xdg-open wait for the viewer to close
        self.assertTrue(self.opening(returncode=None, system="linux")[0])

    def test_a_command_that_fails_does_not(self):
        self.assertFalse(self.opening(returncode=1, system="linux")[0])

    def test_a_system_without_the_command_does_not(self):
        self.assertFalse(self.opening(error=FileNotFoundError("xdg-open"))[0])

    def test_on_windows_it_asks_the_shell_directly(self):
        # Not through `cmd`, which can't be told about a path with an & in it
        path = Path("C:/Users/A&B/qr.png")
        with mock.patch("deliver.this_system", return_value="windows"), mock.patch(
            "deliver.os.startfile", create=True
        ) as startfile:
            self.assertTrue(open_image(path))
            startfile.assert_called_once_with(str(path))
        with mock.patch("deliver.this_system", return_value="windows"), mock.patch(
            "deliver.os.startfile", create=True, side_effect=OSError("no viewer")
        ):
            self.assertFalse(open_image(path))


@unittest.skipIf(os.name == "nt", "Windows has no signals to send")
class QrInterrupted(unittest.TestCase):
    """The real command, stopped from outside, as a tool or the user would."""

    DRIVER = """
import ipaddress, sys
import deliver
deliver.open_image = lambda path: True
deliver.default_route_ip = lambda: "127.0.0.1"
deliver.PRIVATE_NETWORKS = (ipaddress.ip_network("127.0.0.0/8"),)
sys.exit(deliver.main(["qr", sys.argv[1]]))
"""

    def stop_with(self, *signal_numbers):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "nevera-lote.zip"
            batch.write_bytes(b"PK")
            images = Path(tmp) / "tmp"
            images.mkdir()
            scripts = Path(deliver_module.__file__).parent
            process = subprocess.Popen(
                [sys.executable, "-u", "-c", self.DRIVER, str(batch)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=scripts,
                env={**os.environ, "TMPDIR": str(images)},
            )
            self.addCleanup(process.kill)
            self.addCleanup(process.stdout.close)
            self.addCleanup(process.stderr.close)
            self.assertIn("://import?from=", process.stdout.readline())
            deadline = time.monotonic() + 5
            while not list(images.glob("*/*.png")) and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertEqual(len(list(images.glob("*/*.png"))), 1)
            for signal_number in signal_numbers:
                process.send_signal(signal_number)
            self.assertEqual(process.wait(10), 130)
            self.assertEqual(list(images.iterdir()), [])
            self.assertEqual(process.stderr.read(), "")

    def test_control_c_leaves_no_image(self):
        self.stop_with(signal.SIGINT)

    def test_being_killed_politely_leaves_no_image(self):
        self.stop_with(signal.SIGTERM)

    def test_closing_the_terminal_leaves_no_image(self):
        self.stop_with(signal.SIGHUP)

    def test_several_signals_at_once_still_end_cleanly(self):
        self.stop_with(signal.SIGINT, signal.SIGTERM, signal.SIGHUP)


if __name__ == "__main__":
    unittest.main()
