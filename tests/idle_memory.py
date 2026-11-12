"""Check that an idle runcat worker does not grow its private tmux server."""

import fcntl
import os
from pathlib import Path
import pty
import select
import signal
import struct
import subprocess
import tempfile
import termios
import threading
import time

PLUGIN = Path(__file__).resolve().parents[1]
BINARY = PLUGIN / "target/release/tmux-runcat"
DURATION = 60
WARMUP = 5
MAX_GROWTH_KB = 512


def rss_kb(pid):
    """Return Linux resident set size, or None when /proc is unavailable."""
    try:
        with open(f"/proc/{pid}/status", encoding="ascii") as status:
            for line in status:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1])
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        return None
    return None


def main():
    if rss_kb(os.getpid()) is None:
        print("SKIP: Linux /proc RSS data unavailable")
        return
    if not BINARY.is_file():
        raise SystemExit(f"Build release binary first: {BINARY}")

    environment = dict(os.environ, TERM="xterm-256color")
    environment.pop("TMUX", None)
    with tempfile.TemporaryDirectory(prefix="runcat-idle-memory-") as temporary:
        directory = Path(temporary)
        socket = str(directory / "tmux.sock")
        command = ["tmux", "-S", socket]
        config = directory / "tmux.conf"
        config.write_text("set -s exit-empty off\n", encoding="utf-8")
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 100, 0, 0))
        client = None
        stop = threading.Event()

        def run(*args):
            return subprocess.check_output(
                command + list(args), env=environment, text=True
            ).strip()

        def drain_pty():
            while not stop.is_set():
                if not select.select([master], [], [], 0.05)[0]:
                    continue
                try:
                    if not os.read(master, 65536):
                        return
                except OSError:
                    return

        def wait_for(predicate, message, timeout=8):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if predicate():
                    return
                time.sleep(0.05)
            raise AssertionError(message)

        try:
            # Match startup ordering: loader starts before the first session.
            run("-f", str(config), "start-server")
            server_pid = int(run("display-message", "-p", "#{pid}"))
            subprocess.run(
                [str(BINARY), "load", str(PLUGIN), socket, str(server_pid)],
                env=environment,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            # The worker must survive startup before any session exists.
            time.sleep(0.3)
            jobs = run("show-messages", "-J")
            assert "tmux-runcat" in jobs and "watch" in jobs, (
                "watch worker exited before the first session was created: " + jobs
            )
            run("set-option", "-g", "status-right", "#{@runcat-frame}")
            run("new-session", "-d", "-s", "idle-memory", "sleep 600")
            client = subprocess.Popen(
                command + ["attach-session", "-t", "idle-memory"],
                stdin=slave,
                stdout=slave,
                stderr=slave,
                env=environment,
                start_new_session=True,
            )
            os.close(slave)
            threading.Thread(target=drain_pty, daemon=True).start()
            wait_for(
                lambda: bool(run("list-clients", "-F", "#{client_name}")),
                "private tmux client did not attach",
            )
            wait_for(
                lambda: run(
                    "display-message", "-p", "-t", "idle-memory", "#{@runcat-frame}"
                ),
                "runcat worker did not publish a frame",
            )
            if client.poll() is not None:
                raise AssertionError("private tmux client exited during setup")

            # Let command, format, and allocator caches reach steady state.
            time.sleep(WARMUP)
            start = rss_kb(server_pid)
            if start is None:
                print("SKIP: private tmux server exited before measurement")
                return
            print(f"idle server RSS after warmup: {start} kB", flush=True)
            for elapsed in range(10, DURATION + 1, 10):
                time.sleep(10)
                current = rss_kb(server_pid)
                if current is None:
                    raise AssertionError("private tmux server exited during measurement")
                print(f"{elapsed}s: {current} kB", flush=True)

            growth = current - start
            print(f"RSS growth: {growth} kB in {DURATION}s; limit {MAX_GROWTH_KB} kB")
            assert growth <= MAX_GROWTH_KB, (
                f"idle tmux RSS grew by {growth} kB; limit is {MAX_GROWTH_KB} kB"
            )
        finally:
            stop.set()
            if client is not None and client.poll() is None:
                client.send_signal(signal.SIGTERM)
                try:
                    client.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    client.kill()
                    client.wait(timeout=2)
            subprocess.run(
                command + ["kill-server"],
                env=environment,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            try:
                os.close(master)
            except OSError:
                pass
            try:
                os.close(slave)
            except OSError:
                pass


if __name__ == "__main__":
    main()
