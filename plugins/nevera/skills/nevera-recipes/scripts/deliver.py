#!/usr/bin/env python3
"""Gets the batch closer to the phone when the user asks.

    python3 deliver.py airdrop <batch.zip>   Mac: open the AirDrop window with
                                             the file, and wait for the user to
                                             pick a device
    python3 deliver.py icloud <batch.zip>    Mac: copy it to iCloud Drive/Nevera
    python3 deliver.py qr <batch.zip> [--scheme nevera]
                                             any system: serve it on the local
                                             network until the phone has it

`airdrop` prints `sent` when the Mac reports the send as done, and `finder` when
it doesn't, with the file shown in the Finder too: Control-click, Share, AirDrop.
That report can come after the file arrives, so `finder` doesn't prove it never
did. It's also where it ends up on a Mac without Xcode or the Command Line Tools,
since the window comes from `airdrop.swift`, run with `swift`. Dragging the file
onto the AirDrop window started no send on macOS 27, even with the phone in
sight.

`qr` prints the link Nevera opens and its QR code as text, for a dark background,
and shows the code in the system's image viewer. Then it prints `downloaded` as soon
as the phone has the batch, or `timeout` if nobody asked for it in 5 minutes. After `downloaded` it keeps serving for 2 more
minutes, and only then does the command end, removing the image: scanning the code
again closes the preview in Nevera and downloads the batch once more.

Standard library only: it runs with any Python 3.9+.
"""

from __future__ import annotations

import ipaddress
import os
import re
import secrets
import shutil
import signal
import socket
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Iterator, List
from urllib.parse import quote

from machine import open_image_command, this_system
from qr import QrTooLong, png_bytes, qr_matrix, text_art

ICLOUD_DRIVE = "Library/Mobile Documents/com~apple~CloudDocs"
AIRDROP_SCRIPT = Path(__file__).resolve().with_name("airdrop.swift")

# airdrop.swift gives up after 240 seconds. This covers compiling it as well,
# and a run that hangs before its own timer starts.
AIRDROP_TIMEOUT = 300

# What Nevera accepts as the local network: its isBatchDownloadUrl, in
# src/utils/incoming.ts. An iPhone's personal hotspot (172.20.10.x) is in there.
PRIVATE_NETWORKS = tuple(
    ipaddress.ip_network(network)
    for network in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
)
SCHEME = re.compile(r"[a-z][a-z0-9+.-]*")
DEFAULT_SCHEME = "nevera"
QR_TIMEOUT = 300  # seconds for someone to scan it
QR_GRACE = 120  # seconds it keeps serving after the first download
QR_FINISH = 120  # seconds a download in progress gets once the time is up
# A client that stops reading gets dropped after this.
QR_STALL = 30
# Seconds for the viewer's command to say it failed. Some xdg-open wait for the
# viewer to close, so one that is still running has done its job.
OPEN_WAIT = 2
OTHER_WAY = "Send the batch another way, like a shared drive or a cable."


class DeliverError(Exception):
    """What went wrong, in words the user can read."""


def send_to_icloud(batch: Path, home: Path) -> Path:
    """Copies the batch to a Nevera folder in iCloud Drive and returns the copy.
    The batch stays where it was."""
    if not batch.is_file():
        raise DeliverError(f"There is no batch at {batch}")
    drive = home / ICLOUD_DRIVE
    if not drive.is_dir():
        raise DeliverError("iCloud Drive is not turned on for this Mac")
    folder = drive / "Nevera"
    folder.mkdir(exist_ok=True)
    return Path(shutil.copy2(batch, folder / batch.name))


def has_swift() -> bool:
    """Asks xcode-select, because /usr/bin/swift exists even without the tools,
    and running it there can make macOS offer to install them."""
    if shutil.which("swift") is None:
        return False
    found = subprocess.run(
        ["xcode-select", "-p"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return found.returncode == 0


def send_with_airdrop(batch: Path) -> bool:
    """True when the Mac reports the send as done. Waits for the user to pick a
    device, and says why on stderr when it wasn't sent."""
    if not has_swift():
        print("Swift isn't available on this Mac", file=sys.stderr)
        return False
    try:
        done = subprocess.run(
            ["swift", str(AIRDROP_SCRIPT), str(batch)],
            capture_output=True,
            text=True,
            timeout=AIRDROP_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        print(error, file=sys.stderr)
        return False
    if done.returncode != 0:
        print(done.stdout.strip() or done.stderr.strip(), file=sys.stderr)
    return done.returncode == 0


def show_in_finder(batch: Path) -> None:
    subprocess.run(["open", "-R", str(batch)], check=True)


def default_route_ip() -> str:
    """The IP this machine uses to go out. Connecting a UDP socket sends nothing:
    it only makes the system choose the route."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.connect(("8.8.8.8", 53))
        return probe.getsockname()[0]


def local_ip() -> str:
    """The IP to serve on: one Nevera will accept, or the reason there is none."""
    try:
        ip = default_route_ip()
    except OSError as error:
        raise DeliverError(
            f"This computer isn't on a network ({error}). {OTHER_WAY}"
        ) from error
    if not any(ipaddress.ip_address(ip) in net for net in PRIVATE_NETWORKS):
        raise DeliverError(
            f"The phone can't reach this computer at {ip}, which isn't a "
            f"private network address. {OTHER_WAY}"
        )
    return ip


def batch_path(token: str) -> str:
    return f"/{token}/lote.zip"


def qr_link(scheme: str, ip: str, port: int, token: str) -> str:
    """The link Nevera opens. A public contract, like the batch: changing it means
    Nevera has to go on reading the old one."""
    url = f"http://{ip}:{port}{batch_path(token)}"
    return f"{scheme}://import?from={quote(url, safe='')}"


class BatchHandler(BaseHTTPRequestHandler):
    """GET and HEAD on the exact path; a 404 for anything else. HTTP/1.0, so that
    every connection ends with its answer and none keeps a thread waiting."""

    timeout = QR_STALL
    server: BatchServer

    def do_GET(self) -> None:
        if self.answer_headers():
            self.send_batch()

    def do_HEAD(self) -> None:
        self.answer_headers()

    def __getattr__(self, name: str) -> Callable[[], None]:
        """Any other method: http.server looks for a do_<METHOD>, and without one
        it answers 501."""
        if name.startswith("do_"):
            return lambda: self.send_error(404)
        raise AttributeError(name)

    def answer_headers(self) -> bool:
        # The request line, because self.path has already tidied up its slashes
        if self.requestline.split()[1] != self.server.batch_path:
            self.send_error(404)
            return False
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Length", str(self.server.batch.stat().st_size))
        self.end_headers()
        return True

    def send_batch(self) -> None:
        with self.server.sending():
            try:
                with self.server.batch.open("rb") as batch:
                    shutil.copyfileobj(batch, self.wfile)
                # Sending it only proves it fits in the socket buffers: a small
                # batch does, even if nobody reads it. Whoever has read it all
                # sees the end and closes, and only then do we hear nothing more.
                self.connection.shutdown(socket.SHUT_WR)
                if self.connection.recv(1):
                    return
            except (ConnectionError, TimeoutError, socket.timeout):
                return  # Cut halfway. Nevera asks again if it wants to
            self.server.downloaded.set()

    def log_message(self, format: str, *args: object) -> None:
        pass  # stdout and stderr are what the AI reads


class BatchServer(ThreadingHTTPServer):
    # Daemon threads, so a connection that never ends can't keep the command from
    # ending. The downloads in progress are waited for, up to a limit: finish()
    daemon_threads = True

    def __init__(self, ip: str, batch: Path, token: str) -> None:
        super().__init__((ip, 0), BatchHandler)
        self.batch = batch
        self.batch_path = batch_path(token)
        self.downloaded = threading.Event()
        self.in_progress = 0
        self.changed = threading.Condition()

    def server_bind(self) -> None:
        # HTTPServer's also looks up this machine's name, which can take seconds
        socketserver.TCPServer.server_bind(self)

    def handle_error(self, request: object, client_address: object) -> None:
        pass  # A client that goes away halfway is nothing to report

    @contextmanager
    def sending(self) -> Iterator[None]:
        with self.changed:
            self.in_progress += 1
        try:
            yield
        finally:
            with self.changed:
                self.in_progress -= 1
                self.changed.notify_all()

    def finish(self, limit: float) -> None:
        """Waits for the downloads in progress, up to the limit."""
        with self.changed:
            self.changed.wait_for(lambda: self.in_progress == 0, limit)


def wait_for(event: threading.Event, timeout: float) -> bool:
    """event.wait(timeout), in short waits: on Windows a long one doesn't let
    Control-C through until it ends."""
    deadline = time.monotonic() + timeout
    while not event.is_set() and time.monotonic() < deadline:
        event.wait(min(0.5, max(0.0, deadline - time.monotonic())))
    return event.is_set()


def serve_batch(
    batch: Path,
    ip: str,
    scheme: str,
    emit: Callable[[str], None],
    grace: float = QR_GRACE,
    timeout: float = QR_TIMEOUT,
    finish: float = QR_FINISH,
    show: Callable[[str], None] = lambda link: None,
) -> None:
    """Serves the batch on that IP. Tells `emit` the link first, then `show`s it,
    and later tells `emit` `downloaded` or `timeout`. It returns with the port
    closed."""
    token = secrets.token_hex(16)
    server = BatchServer(ip, batch, token)
    serving = threading.Thread(target=server.serve_forever)
    serving.start()
    try:
        link = qr_link(scheme, ip, server.server_address[1], token)
        emit(link)
        show(link)
        if not wait_for(server.downloaded, timeout):
            server.finish(finish)
        downloaded = server.downloaded.is_set()
        if downloaded:
            emit("downloaded")
            time.sleep(grace)
    finally:
        server.shutdown()
        serving.join()
        server.server_close()
    server.finish(finish)
    if not downloaded:
        emit("timeout")


def open_image(image: Path) -> bool:
    """True unless the system's viewer says it can't open it."""
    system = this_system()
    try:
        if system == "windows":
            os.startfile(str(image))  # type: ignore[attr-defined]
            return True
        process = subprocess.Popen(
            open_image_command(system, str(image)),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return process.wait(OPEN_WAIT) == 0
    except subprocess.TimeoutExpired:
        return True
    except OSError:
        return False


def show_qr(link: str, folder: Path) -> None:
    """Prints the QR code, writes it as an image and opens that. Not in the terminal
    only: what a command prints doesn't always reach the user, and a terminal may
    not have the characters or a dark background. Without either, they have the
    link."""
    image = folder / "nevera-qr.png"
    try:
        matrix = qr_matrix(link)
    except QrTooLong as error:
        print(f"There's no QR code for this link: {error}", file=sys.stderr)
        return
    try:
        print(text_art(matrix), flush=True)
    except UnicodeEncodeError:
        pass  # A terminal without these characters: the image is enough
    try:
        image.write_bytes(png_bytes(matrix))
    except OSError as error:
        print(f"There's no QR code for this link: {error}", file=sys.stderr)
        return
    if not open_image(image):
        print(f"The QR code didn't open. It's at {image}", file=sys.stderr)


def stop_signals() -> List[signal.Signals]:
    """Control-C, what a tool stops a command with, and closing the terminal.
    Windows has no SIGHUP."""
    names = ("SIGINT", "SIGTERM", "SIGHUP")
    return [getattr(signal, name) for name in names if hasattr(signal, name)]


def do_nothing(_signal: int, _frame: object) -> None:
    pass


def ignore_signals() -> None:
    """With a handler that does nothing, not SIG_IGN: Python complains about a
    signal already on its way when its handler becomes SIG_IGN."""
    for number in stop_signals():
        signal.signal(number, do_nothing)


def stop_on_signal(_signal: int, _frame: object) -> None:
    """Most of these skip the cleanup unless they become Control-C. One is
    enough: another one, while cleaning up, would leave the image behind."""
    ignore_signals()
    raise KeyboardInterrupt


def deliver_qr(args: List[str]) -> int:
    if len(args) not in (1, 3) or (len(args) == 3 and args[1] != "--scheme"):
        print(__doc__, file=sys.stderr)
        return 2
    batch = Path(args[0]).expanduser()
    scheme = args[2] if len(args) == 3 else DEFAULT_SCHEME
    folder = None
    previous = {number: signal.getsignal(number) for number in stop_signals()}
    for number in previous:
        signal.signal(number, stop_on_signal)
    try:
        if not SCHEME.fullmatch(scheme):
            raise DeliverError(f"{scheme!r} can't be a link scheme")
        if not batch.is_file():
            raise DeliverError(f"There is no batch at {batch}")
        ip = local_ip()
        folder = Path(tempfile.mkdtemp(prefix="nevera-qr-"))
        serve_batch(
            batch,
            ip,
            scheme,
            lambda line: print(line, flush=True),
            grace=QR_GRACE,
            timeout=QR_TIMEOUT,
            finish=QR_FINISH,
            show=lambda link: show_qr(link, folder),
        )
        return 0
    except (DeliverError, OSError) as error:
        print(error, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    finally:
        ignore_signals()
        if folder:
            shutil.rmtree(folder, ignore_errors=True)
        for number, handler in previous.items():
            signal.signal(number, handler)


def main(argv: List[str]) -> int:
    if argv[:1] == ["qr"]:
        return deliver_qr(argv[1:])
    if len(argv) != 2 or argv[0] not in ("icloud", "airdrop"):
        print(__doc__, file=sys.stderr)
        return 2
    action, batch = argv[0], Path(argv[1]).expanduser()
    try:
        if this_system() != "macos":
            raise DeliverError("This only works on a Mac")
        if action == "icloud":
            print(send_to_icloud(batch, Path.home()))
            return 0
        if not batch.is_file():
            raise DeliverError(f"There is no batch at {batch}")
        if send_with_airdrop(batch):
            print("sent")
            return 0
        show_in_finder(batch)
        print("finder")
        return 0
    except (DeliverError, OSError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
