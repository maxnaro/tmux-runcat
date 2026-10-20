# RunCat status animation

Run `bash fonts/setup.sh` from the plugin repository root. It builds and installs the clean
JetBrainsMono Nerd Font family and the separate `JetBrainsMono RunCat v3`
family. No manual downloads, pip, or virtual
environment are needed. Python 3.11+ must be available on PATH.

The font sources, pure Python fontTools wheel, exact versions, checksums, and
licenses live in [vendor](vendor/README.md). The build verifies its inputs and
produces identical font files on repeated runs. Generated files live in
`${XDG_DATA_HOME:-~/.local/share}/tmux-runcat/`, outside the repository.

To rebuild and install only this feature:

```bash
bash fonts/setup.sh
```

To build without installing or changing terminal settings:

```bash
bash fonts/setup.sh --build-only
```

## Windows Terminal / WSL

Setup detects WSL and installs fonts in the current Windows user's font
directory using Windows PowerShell. WSL Windows interoperability must be
enabled. It selects `JetBrainsMono RunCat v3` in stable Windows Terminal's
defaults, WSL profiles, and existing JetBrainsMono profiles, preserving other
settings. Settings and font registrations are backed up before changes.
Settings containing comments or trailing commas are accepted; changed files
are saved as standard JSON. Other terminal apps need their font selected in
their own settings.

Open a new terminal window if it has cached the old font. Choose
`JetBrainsMono Nerd Font` to use the clean font without the cat glyphs.
Installing fonts only inside WSL cannot supply them to Windows Terminal.

## Linux terminals

Setup installs the fonts in the user's font directory and refreshes fontconfig
when available. Select `JetBrainsMono RunCat v3` in your terminal. For Kitty,
you can instead map only the cat characters while keeping another main font:

```conf
symbol_map U+EFF0-U+EFFF,U+F600-U+F607,U+F620-U+F637 JetBrainsMono RunCat v3
```

## Animation and font construction

Place `#{@runcat-frame}` in your status format. The Rust
worker runs at 3–12 FPS according to the last second of
typing, slows smoothly, and shows a curled-up sleeping pose after two idle
seconds. A native tmux `Any` binding counts ordinary forwarded keys, then
passes the original input to the application. Existing specific bindings keep
precedence; mouse input is forwarded separately, and paste does not inflate
the typing rate. The helper reads only the count, not the key contents.

Each session has its own activity and pose. A per-server lock prevents duplicate
helpers on reload. Animation pauses when clients detach, and the worker exits
when the tmux server stops. The `@runcat-idle`, `@runcat-min-fps`, and
`@runcat-max-fps` tmux options control the delay and speed.

Medium poses occupy two adjacent characters: U+EFF0–U+EFF4 for the left halves
and U+EFF5–U+EFF9 for the right halves. U+EFFA–U+EFFF contain three breathing
poses, drawn from `sleeping-cat.svg`. They raise the silhouette by 0%, 4%, and
8% over a three-second cycle. Small poses use U+F600–U+F607 (one cell);
large poses use U+F620–U+F637 (three cells). All presets contain five running
and three breathing poses. Both states keep the selected width, preserving
the status layout. The large cat fills more of the existing row height.
The silhouette fills most of the text
height without changing terminal character widths. Existing JetBrainsMono
glyphs, spacing, weights, and ligature features are preserved.

The source `runcat-tmux.ttf` comes from
[runcat-text](https://github.com/bzglve/runcat-text/blob/master/runcat.ttf),
with the five original poses remapped from U+E900–U+E904 to U+EFF0–U+EFF4.
Its BSD license is in `LICENSE`. Setup builds the two-character poses from this
source and the pinned JetBrainsMono files.

Run the build regression checks with:

```bash
python3 fonts/tests/test_build.py
cargo test --locked --offline
python3 tests/live_tmux.py
```
