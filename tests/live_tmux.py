"""Exercise real client input, idle/wake, mouse forwarding, and reloads."""

import fcntl
import os
from pathlib import Path
import pty
import select
import struct
import subprocess
import tempfile
import termios
import threading
import time

PLUGIN = Path(__file__).resolve().parents[1]
SLEEP = chr(0xEFFA) + chr(0xEFFB)


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
            return result.stdout.strip() if result.returncode == 0 else ""

        try:
            run("-f", str(config), "new-session", "-d", "-s", "runcat-live", f"python3 {capture}")
            client = subprocess.Popen(command + ["attach-session", "-t", "runcat-live"],
                                      stdin=slave, stdout=slave, stderr=slave,
                                      env=environment, start_new_session=True)
            reader = threading.Thread(target=drain, daemon=True)
            reader.start()
            wait_for(lambda: capture.with_suffix(".ready").exists(), "capture pane did not start")
            wait_for(lambda: run("list-clients", "-F", "#{client_name}"), "client did not attach")
            wait_for(lambda: pose() == SLEEP, "cat did not start asleep")
            assert run("show-option", "-gv", "@runcat-min-fps") == "4", "loader replaced user option"

            keys = [b"a", b"\t", b"\x1b[A", b"\x1bq", "é".encode(), b"\x03", b"\r"]
            for key in keys:
                os.write(master, key)
                time.sleep(0.04)
            wait_for(lambda: pose() != SLEEP, "typing did not wake the cat")
            count = int(run("show-option", "-v", "-t", "runcat-live", "@runcat-keys"))
            assert count == len(keys), ("incorrect key count", count)
            received = capture.with_suffix(".input").read_bytes()
            assert received == b"".join(keys), ("input was changed", received)

            # Mouse movement reaches the app and does not count as typing.
            os.write(master, b"\x1b[<35;5;5M")
            wait_for(lambda: b"\x1b[<35;" in capture.with_suffix(".input").read_bytes(),
                     "mouse movement was not forwarded")
            assert int(run("show-option", "-v", "-t", "runcat-live", "@runcat-keys")) == count
            wait_for(lambda: pose() == SLEEP, "cat did not sleep after idle")

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
            wait_for(lambda: pose() != SLEEP, "reloaded worker did not wake")
            wait_for(lambda: pose() == SLEEP, "custom idle timeout did not apply", timeout=1)
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
            print("PASS: idle/wake, key counts, exact key forwarding, mouse forwarding, prefix shortcut, and one worker after reload")
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
