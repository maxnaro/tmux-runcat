"""Capture all five runtime skins and render a themed README comparison.

Run from the repository root: python3 doc/render_family.py (requires Pillow).
Only temporary fonts, tmux sessions, and terminal clients are created.
"""
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

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FAMILY = [('Original', 'pet-cats'), ('Stocky', 'pet-cats-stocky'),
          ('Lanky', 'pet-cats-lanky'), ('Fluffy', 'pet-cats-fluffy'),
          ('Bobtail', 'pet-cats-bobtail')]


def main():
    subprocess.run(['cargo', 'build', '--release', '--locked', '--offline'], cwd=ROOT, check=True)
    with tempfile.TemporaryDirectory(prefix='cat-family-') as temporary:
        env = dict(os.environ, TERM='xterm-256color', XDG_DATA_HOME=temporary)
        env.pop('TMUX', None)
        subprocess.run(['bash', 'fonts/setup.sh', '--build-only'], cwd=ROOT, env=env,
                       check=True, stdout=subprocess.DEVNULL)
        font = ImageFont.truetype(str(Path(temporary) / 'tmux-runcat/generated/RunCat-Regular.ttf'), 28)
        label_font = ImageFont.truetype(str(Path(temporary) / 'tmux-runcat/generated/RunCat-Regular.ttf'), 18)
        command = ['tmux', '-S', str(Path(temporary) / 'socket')]
        stopped = threading.Event()
        clients, descriptors = [], []

        def run(*args):
            return subprocess.check_output(command + list(args), env=env, text=True).rstrip('\n')

        def drain(fd):
            while not stopped.is_set():
                if select.select([fd], [], [], .05)[0]:
                    try:
                        if not os.read(fd, 65536):
                            return
                    except OSError:
                        return

        try:
            for index, (_, skin) in enumerate(FAMILY):
                session = f'cat{index}'
                run('-f', '/dev/null', 'new-session', '-d', '-s', session, 'cat >/dev/null')
                for option, value in [('@runcat-skin', skin), ('@runcat-size', 'xlarge'),
                                      ('@runcat-idle', '2'), ('@runcat-max-fps', '16'),
                                      ('@runcat-roam', 'off'), ('status-right', '#{@runcat-frame}')]:
                    run('set', '-t', session, option, value)
                master, slave = pty.openpty()
                descriptors.extend([master, slave])
                fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 8, 64, 0, 0))
                clients.append(subprocess.Popen(command + ['attach', '-t', session],
                                                stdin=slave, stdout=slave, stderr=slave, env=env))
                threading.Thread(target=drain, args=(master,), daemon=True).start()
            run('run-shell', str(ROOT / 'runcat.tmux'))
            time.sleep(.5)
            samples = []
            start = time.monotonic()
            next_key = start + .4
            while time.monotonic() - start < 9:
                now = time.monotonic()
                age = now - start
                if .4 <= age < 5 and now >= next_key:
                    for master in descriptors[::2]:
                        os.write(master, b'a' if age < 2 else b'abcdefghij')
                    next_key = now + (.35 if age < 2 else .05)
                rows = []
                for index in range(len(FAMILY)):
                    state, pose = run('display-message', '-t', f'cat{index}', '-p',
                                      '#{@runcat-state}|#{@runcat-frame}').split('|', 1)
                    pose = re.sub(r'#\[[^]]*\]', '', pose)
                    if len(pose) != 4:
                        raise AssertionError((index, state, repr(pose)))
                    rows.append((state, pose))
                samples.append((now, rows))
                time.sleep(.04)
            for index in range(len(FAMILY)):
                states = {rows[index][0] for _, rows in samples}
                assert {'walk', 'run', 'sleep'} <= states, (FAMILY[index], states)
            for theme, background, foreground in [('dark', '#0d1117', 'white'), ('light', 'white', 'black')]:
                images, durations = [], []
                for number, (stamp, rows) in enumerate(samples):
                    image = Image.new('RGB', (720, 350), background)
                    draw = ImageDraw.Draw(image)
                    for index, ((name, _), (state, pose)) in enumerate(zip(FAMILY, rows)):
                        y = 30 + index * 64
                        draw.text((20, y), name, font=label_font, fill=foreground)
                        draw.text((230, y + 24), pose, font=font, fill=foreground, anchor='ls')
                        draw.text((380, y), state, font=label_font, fill=foreground)
                    images.append(image)
                    delay = samples[number + 1][0] - stamp if number + 1 < len(samples) else .05
                    durations.append(max(10, round(delay * 100) * 10))
                images[0].save(ROOT / f'doc/assets/family-{theme}.gif', save_all=True,
                               append_images=images[1:], duration=durations, loop=0, optimize=True)
        finally:
            subprocess.run(command + ['kill-server'], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            stopped.set()
            for client in clients:
                client.wait(timeout=5)
            for fd in descriptors:
                os.close(fd)


if __name__ == '__main__':
    main()
