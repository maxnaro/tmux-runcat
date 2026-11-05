"""Capture real roaming output; render two themed GIFs. Requires Pillow."""
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


def main():
    subprocess.run(['cargo', 'build', '--release', '--locked', '--offline'], cwd=ROOT, check=True)
    with tempfile.TemporaryDirectory(prefix='cat-demo-') as temporary:
        directory = Path(temporary)
        env = dict(os.environ, TERM='xterm-256color', XDG_DATA_HOME=temporary)
        env.pop('TMUX', None)
        subprocess.run(['bash', 'fonts/setup.sh', '--build-only'], cwd=ROOT, env=env, check=True,
                       stdout=subprocess.DEVNULL)
        font = ImageFont.truetype(str(directory / 'tmux-runcat/generated/RunCat-Regular.ttf'), 28)
        cell = font.getlength(' ')
        command = ['tmux', '-S', str(directory / 'socket')]

        def run(*args):
            return subprocess.check_output(command + list(args), env=env, text=True).rstrip('\n')

        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 8, 64, 0, 0))
        stopped = threading.Event()
        client = None

        def drain():
            while not stopped.is_set():
                if select.select([master], [], [], .05)[0]:
                    try:
                        os.read(master, 65536)
                    except OSError:
                        return

        try:
            run('-f', '/dev/null', 'new-session', '-d', '-s', 'demo', 'cat >/dev/null')
            for key, value in [('status-left', 'CAT '), ('status-right', ' tmux '),
                               ('window-status-current-format', '1:shell '),
                               ('@runcat-skin', 'pet-cats'), ('@runcat-roam', 'on'),
                               ('@runcat-size', 'xlarge'), ('@runcat-idle', '8'),
                               ('@runcat-max-fps', '24')]:
                run('set', '-g', key, value)
            client = subprocess.Popen(command + ['attach', '-t', 'demo'], stdin=slave,
                                      stdout=slave, stderr=slave, env=env)
            threading.Thread(target=drain, daemon=True).start()
            run('run-shell', str(ROOT / 'runcat.tmux'))
            time.sleep(.5)
            pid = run('list-clients', '-F', '#{client_pid}')
            clips = []
            # Advance the genuine rest cycle. Retain body licking and sitting.
            for cycle in range(6):
                samples = []
                start = time.monotonic()
                next_key = start
                while time.monotonic() - start < 15:
                    now = time.monotonic()
                    if now - start < 8 and now >= next_key:
                        os.write(master, b'abcdefghij')
                        next_key = now + .1
                    text = run('display-message', '-p',
                               '#{@runcat-state}|#{@runcat-client-' + pid + '}')
                    state, lane = text.split('|', 1)
                    lane = re.sub(r'#\[[^]]*\]', '', lane)
                    samples.append((now, state, lane))
                    time.sleep(.04)
                if cycle in (3, 5):
                    clips.append(samples)
            states = {state for clip in clips for _, state, _ in clip}
            assert {'lick-body', 'sit', 'lie-down', 'sleep'} <= states, states
            moving = [lane for _, state, lane in clips[0] if state == 'run']
            positions = [len(lane) - len(lane.lstrip()) - 1 for lane in moving]
            room = len(moving[0]) - 6
            assert min(positions) == 0 and max(positions) == room, (min(positions), max(positions), room)
            for clip in clips:
                previous = None
                for _, state, lane in clip:
                    position = len(lane) - len(lane.lstrip()) - 1
                    left = bool(lane.strip()) and ord(lane.strip()[0]) >= 0x101000
                    if previous:
                        old_position, old_left, old_state = previous
                        if left != old_left:
                            assert min(position, room - position) <= 1
                        if state not in ('walk', 'run') and old_state not in ('walk', 'run'):
                            assert position == old_position
                    previous = position, left, state
            for theme, background, foreground in [('dark', '#0d1117', 'white'),
                                                    ('light', 'white', 'black')]:
                images, durations = [], []
                for index, clip in enumerate(clips):
                    for number, (stamp, state, lane) in enumerate(clip):
                        image = Image.new('RGB', (round(cell * 64), 100), background)
                        draw = ImageDraw.Draw(image)
                        if index:
                            draw.text((12, 5), 'Later pause', font=font, fill=foreground)
                        text = 'CAT 1:shell ' + lane + ' tmux '
                        for column, character in enumerate(text):
                            draw.text((column * cell, 80), character, font=font,
                                      fill=foreground, anchor='ls')
                        images.append(image)
                        delay = clip[number + 1][0] - stamp if number + 1 < len(clip) else .05
                        durations.append(max(10, round(delay * 100) * 10))
                images[0].save(ROOT / f'doc/assets/cat-{theme}.gif', save_all=True,
                               append_images=images[1:], duration=durations, loop=0, optimize=True)
        finally:
            subprocess.run(command + ['kill-server'], env=env, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
            stopped.set()
            if client:
                client.wait(timeout=5)
            os.close(master)
            os.close(slave)


if __name__ == '__main__':
    main()
