"""Exercise real client input, idle/wake, mouse forwarding, and reloads."""

import fcntl
import os
from pathlib import Path
import pty
import re
import select
import struct
import subprocess
import tempfile
import termios
import threading
import time

PLUGIN = Path(__file__).resolve().parents[1]
SLEEP = chr(0xEFFA) + chr(0xEFFB)
SLEEP_POSES = {chr(0xEFFA + 2*frame) + chr(0xEFFB + 2*frame) for frame in range(3)}


def main():
    with tempfile.TemporaryDirectory(prefix="runcat-live-") as temporary:
        directory = Path(temporary)
        socket = str(directory / "tmux.sock")
        command = ["tmux", "-S", socket]
        environment = dict(os.environ, TERM="xterm-256color")
        environment["RUNCAT_BINARY"] = str(PLUGIN / "target/release/tmux-runcat")
        environment.pop("TMUX", None)
        config = directory / "tmux.conf"
        config.write_text(
            "set -s exit-empty off\n"
            "set -g status-position top\nset -g mouse on\nset -s escape-time 0\n"
            "set -g status-right '#{@runcat-frame}'\n"
            "set -g @runcat-min-fps 4\n"
            f"run-shell '\"{PLUGIN}/runcat.tmux\" \"#{{socket_path}}\" \"#{{pid}}\"'\n"
        )
        capture = directory / "capture.py"
        capture.write_text(
            "import os, sys, tty\n"
            "from pathlib import Path\n"
            "tty.setraw(sys.stdin.fileno())\n"
            "os.write(1, b'\\x1b[?1003h\\x1b[?1006h')\n"
            "Path(__file__).with_suffix('.ready').touch()\n"
            "with open(Path(__file__).with_suffix('.input'), 'ab', buffering=0) as log:\n"
            "    while True:\n"
            "        data = os.read(0, 4096)\n"
            "        if not data: break\n"
            "        log.write(data)\n"
        )
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 100, 0, 0))
        client = None
        stop = threading.Event()

        def drain():
            while not stop.is_set():
                if select.select([master], [], [], 0.05)[0]:
                    try:
                        os.read(master, 65536)
                    except OSError:
                        return

        def run(*args):
            return subprocess.check_output(command + list(args), env=environment, text=True).strip()

        def wait_for(predicate, message, timeout=4):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if predicate():
                    return
                time.sleep(0.03)
            raise AssertionError(message)

        def pose():
            result = subprocess.run(command + ["show-option", "-v", "-t", "runcat-live", "@runcat-frame"],
                                    env=environment, text=True, capture_output=True)
            return result.stdout.rstrip("\r\n") if result.returncode == 0 else ""

        def visible_pose():
            return re.sub(r"#\[[^]]*\]", "", pose())

        def state():
            return run("show-option", "-v", "-t", "runcat-live", "@runcat-state")

        def sleeping():
            text = visible_pose()
            if len(text) == 1:
                return 0xF605 <= ord(text[0]) <= 0xF607
            if len(text) == 3:
                return ord(text[0]) in (0xF62F, 0xF632, 0xF635)
            return text in SLEEP_POSES

        try:
            # Load before any session exists, as happens when other plugins
            # continue processing the startup config after runcat is loaded.
            run("-f", str(config), "start-server")
            wait_for(lambda: "watch" in run("show-messages", "-J"), "worker did not start")
            time.sleep(0.3)
            jobs = run("show-messages", "-J")
            assert "tmux-runcat" in jobs and "watch" in jobs, (
                "worker exited before the first session was created\n" + jobs + "\n" + run("show-messages")
            )
            run("new-session", "-d", "-s", "runcat-live", f"python3 {capture}")
            client = subprocess.Popen(command + ["attach-session", "-t", "runcat-live"],
                                      stdin=slave, stdout=slave, stderr=slave,
                                      env=environment, start_new_session=True)
            reader = threading.Thread(target=drain, daemon=True)
            reader.start()
            wait_for(lambda: capture.with_suffix(".ready").exists(), "capture pane did not start")
            wait_for(lambda: run("list-clients", "-F", "#{client_name}"), "client did not attach")
            wait_for(sleeping, "cat did not start asleep")
            assert run("show-option", "-gv", "@runcat-min-fps") == "4", "loader replaced user option"
            assert run("show-option", "-gv", "@runcat-max-fps") == "0", "default speed is capped"

            keys = [b"a", b"\t", b"\x1b[A", b"\x1bq", "é".encode(), b"\x03", b"\r"]
            for key in keys:
                os.write(master, key)
                time.sleep(0.04)
            wait_for(lambda: bool(pose()) and not sleeping(), "typing did not wake the cat")
            count = int(run("show-option", "-v", "-t", "runcat-live", "@runcat-keys"))
            assert count == len(keys), ("incorrect key count", count)
            received = capture.with_suffix(".input").read_bytes()
            assert received == b"".join(keys), ("input was changed", received)

            # Mouse movement reaches the app and does not count as typing.
            os.write(master, b"\x1b[<35;5;5M")
            wait_for(lambda: b"\x1b[<35;" in capture.with_suffix(".input").read_bytes(),
                     "mouse movement was not forwarded")
            assert int(run("show-option", "-v", "-t", "runcat-live", "@runcat-keys")) == count
            wait_for(sleeping, "cat did not sleep after idle")
            sleeping_frames = set()
            deadline = time.monotonic() + 2.5
            while time.monotonic() < deadline and len(sleeping_frames) < 3:
                text = visible_pose()
                assert len(text) == 2, ("sleep animation changed layout width", text)
                sleeping_frames.add(text[:2])
                time.sleep(0.05)
            assert sleeping_frames == SLEEP_POSES, "breathing frames did not cycle"

            # Simulate a fast burst and observe actual status updates, catching
            # both a configured cap and a worker still limited to 50 ms frames.
            run("set-option", "-F", "-t", "runcat-live", "@runcat-keys", "#{e|+:#{@runcat-keys},120}")
            wait_for(lambda: not sleeping(), "fast typing did not wake the cat")
            changes = 0
            previous = visible_pose()
            deadline = time.monotonic() + 0.8
            while time.monotonic() < deadline:
                current = visible_pose()
                changes += current != previous
                previous = current
                time.sleep(0.002)
            assert changes > 20, ("fast typing still has a frame-rate cap", changes)
            wait_for(sleeping, "cat did not sleep after fast typing")

            # Pet Cats uses the same key forwarding and activity counter, with
            # distinct wake, locomotion, pause, and bedtime transitions.
            run("set-option", "-t", "runcat-live", "@runcat-skin", "pet-cats")
            wait_for(lambda: all(0xF700 <= ord(value) < 0xF8A4 for value in visible_pose())
                     and bool(visible_pose()), "Pet Cats skin did not apply live")
            wait_for(lambda: state() == "sleep", "Pet Cats did not start asleep")
            before = capture.with_suffix(".input").read_bytes()
            observed = set()
            for _ in range(5):
                os.write(master, b"z")
                time.sleep(0.2)
                observed.add(state())
            assert {"stretch", "walk"} <= observed, ("Pet Cats did not wake and walk", observed)
            assert capture.with_suffix(".input").read_bytes() == before + b"z"*5
            run("set-option", "-F", "-t", "runcat-live", "@runcat-keys", "#{e|+:#{@runcat-keys},120}")
            wait_for(lambda: state() == "run", "Pet Cats did not run with faster typing")
            wait_for(lambda: state() in {"lick-paw", "idle", "itch", "lick-body", "meow", "sit"},
                     "Pet Cats did not show a pause gesture")
            wait_for(lambda: state() == "lie-down", "Pet Cats did not lie down before sleeping")
            wait_for(lambda: state() == "sleep", "Pet Cats did not sleep after inactivity")
            first = visible_pose()
            wait_for(lambda: visible_pose() != first, "Pet Cats did not breathe while sleeping", timeout=1)
            for size, width in (("small", 1), ("large", 3), ("medium", 2)):
                run("set-option", "-t", "runcat-live", "@runcat-size", size)
                wait_for(lambda: len(visible_pose()) == width, "Pet Cats size did not apply")
                assert state() == "sleep", "resizing woke Pet Cats"
            run("set-option", "-t", "runcat-live", "@runcat-skin", "classic")
            wait_for(sleeping, "switching back to the classic skin did not apply")

            # Resizing applies live in both states without changing width
            # during the animation or interfering with the application's input.
            run("set-option", "-t", "runcat-live", "@runcat-idle", "0.25")
            for size, width in (("small", 1), ("large", 3), ("medium", 2)):
                run("set-option", "-t", "runcat-live", "@runcat-size", size)
                wait_for(lambda: len(visible_pose()) == width, "live size update did not apply")
                assert sleeping(), "resizing woke an idle cat"
                run("set-option", "-F", "-t", "runcat-live", "@runcat-keys", "#{e|+:#{@runcat-keys},1}")
                wait_for(lambda: not sleeping(), "resized cat did not wake")
                assert len(visible_pose()) == width
                wait_for(sleeping, "resized cat did not return to sleep", timeout=1)
                assert len(visible_pose()) == width

            # The existing prefix shortcut still splits a pane.
            os.write(master, b"\x02%")
            wait_for(lambda: len(run("list-panes", "-F", "#{pane_id}").splitlines()) == 2,
                     "prefix shortcut was intercepted")
            generation = run("show-option", "-gv", "@runcat-generation")
            run("source-file", str(config))
            wait_for(lambda: run("show-option", "-gv", "@runcat-generation") != generation,
                     "reload did not replace the worker generation")
            time.sleep(0.4)

            def workers():
                found = []
                for process in Path("/proc").iterdir():
                    try:
                        args = (process / "cmdline").read_bytes().split(b"\0")
                        if len(args) > 2 and args[0].endswith(b"/tmux-runcat") and args[1] == b"watch" and args[2] == socket.encode():
                            found.append(process.name)
                    except (FileNotFoundError, PermissionError, ProcessLookupError, NotADirectoryError):
                        pass
                return found

            wait_for(lambda: len(workers()) == 1, "reload left duplicate workers")
            assert len(workers()) == 1, workers()
            # Runtime options apply without restarting the server.
            run("set-option", "-t", "runcat-live", "@runcat-idle", "0.3")
            run("set-option", "-F", "-t", "runcat-live", "@runcat-keys", "#{e|+:#{@runcat-keys},1}")
            wait_for(lambda: bool(pose()) and not sleeping(), "reloaded worker did not wake")
            wait_for(sleeping, "custom idle timeout did not apply", timeout=1)
            run("detach-client")
            generation = run("show-option", "-gv", "@runcat-generation")
            run("source-file", str(config))
            wait_for(lambda: run("show-option", "-gv", "@runcat-generation") != generation,
                     "detached reload did not replace worker generation")
            time.sleep(0.4)
            wait_for(lambda: len(workers()) == 1, "detached reload left duplicate workers")
            # A custom Any binding is rejected without changing it.
            run("bind-key", "-T", "root", "Any", "display-message", "custom-binding")
            pid = run("display-message", "-p", "#{pid}")
            rejected = subprocess.run([str(PLUGIN / "target/release/tmux-runcat"), "load", str(PLUGIN), socket, pid],
                                      capture_output=True, text=True, env=environment)
            assert rejected.returncode != 0 and "already bound" in rejected.stderr
            assert "custom-binding" in run("list-keys", "-T", "root", "Any")
            print("PASS: Pet Cats states, live skin/size changes, uncapped speed, breathing, key forwarding, mouse, shortcuts, and reloads")
        finally:
            subprocess.run(command + ["kill-server"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if client:
                client.kill()
                client.wait(timeout=5)
            stop.set()
            os.close(master)
            os.close(slave)


if __name__ == "__main__":
    main()
