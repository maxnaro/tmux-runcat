# tmux-runcat

A small cat for your tmux status bar. It wakes when you type, runs faster as
your typing speeds up, slows down, and curls up to sleep after two idle seconds.
Each session has independent activity. The animation occupies two character
cells and preserves the surrounding status-bar layout.

The loader and animation worker are one Rust executable with no third-party
Rust dependencies. Key counting uses tmux commands; no process is started per
keystroke, and the plugin never reads or stores key contents.

## Requirements

- tmux (tested against 3.6) on Linux or WSL
- Rust 1.89+ and Cargo to build; the running plugin needs only tmux
- Bash for the `.tmux` entry point
- Python 3.11+, tar with xz support, and sha256sum for the one-time font setup
- On WSL: Windows interoperability and Windows PowerShell for font installation

## Install

```sh
git clone https://github.com/maxnaro/tmux-runcat.git ~/.config/tmux/plugins/tmux-runcat
cd ~/.config/tmux/plugins/tmux-runcat
cargo build --release --locked --offline
bash fonts/setup.sh
```

The pinned font sources and build tools are bundled, so building the binary
and fonts needs no network after cloning. Font setup installs both the clean
JetBrainsMono Nerd Font family and `JetBrainsMono RunCat Active`, which adds
the running and sleeping poses while preserving existing glyphs and spacing.

On WSL, setup installs fonts on Windows and selects the combined font in stable
Windows Terminal. On Linux, select `JetBrainsMono RunCat Active` in your terminal.
See [font setup](fonts/README.md) for details and backups.

Include `#{@runcat-frame}` wherever you want the cat, and load the plugin after
your status settings:

```tmux
set -g status-right '#{@runcat-frame} | #h | %H:%M '
run-shell '~/.config/tmux/plugins/tmux-runcat/runcat.tmux "#{socket_path}" "#{pid}"'
```

Pass the socket and PID as shown to support custom tmux sockets during startup.
Reload with `tmux source-file ~/.config/tmux/tmux.conf`.

For TPM, add `set -g @plugin 'maxnaro/tmux-runcat'` to your plugin list. After
TPM clones it, build the binary, run font setup, add the status placeholder,
and reload tmux. The entry point uses the current `TMUX` environment when no
socket arguments are supplied.

## Options

Set these before loading the plugin; existing values are preserved. Values
can also be changed with `set-option` while the animation is running.

| Option | Default | Meaning |
| --- | --- | --- |
| `@runcat-idle` | `2` | Idle seconds before sleeping (0.1–3600) |
| `@runcat-min-fps` | `3` | Minimum running speed (1–20 FPS) |
| `@runcat-max-fps` | `12` | Maximum running speed (minimum–20 FPS) |

```tmux
set -g @runcat-idle 3
set -g @runcat-min-fps 4
set -g @runcat-max-fps 15
```

## Behavior

The plugin reserves the root table's `Any` binding for counting ordinary keys
and forwarding the original input. Specific bindings, including prefixes and
your shortcuts, keep precedence. Mouse input is forwarded without counting it
as typing, and bracketed paste bypasses the counter. Copy-mode, popup, and tmux
command-prompt keys do not contribute to the typing rate.

An existing custom root `Any` binding causes the loader to stop with an error;
it is never silently overwritten. Other key tables and status formats are
preserved. Repeated loads replace the worker generation, so code updates take
effect while one worker per server remains active. Workers stop when the
server stops and pause animation when clients detach.

## Use as a dotfiles submodule

```sh
git submodule add git@github.com:maxnaro/tmux-runcat.git tmux/.config/tmux/plugins/tmux-runcat
git submodule update --init --recursive
cargo build --release --locked --offline --manifest-path tmux/.config/tmux/plugins/tmux-runcat/Cargo.toml
bash tmux/.config/tmux/plugins/tmux-runcat/fonts/setup.sh
```

Commit plugin changes in this repository first, then update its pointer in the
parent dotfiles repository. Rebuild the executable after updating the plugin.

## Development

```sh
cargo fmt --check
cargo clippy --locked --offline --all-targets -- -D warnings
cargo test --locked --offline
cargo build --release --locked --offline
python3 fonts/tests/test_build.py
python3 tests/live_tmux.py
bash -n runcat.tmux fonts/setup.sh
```

The live test starts an isolated tmux server and PTY, checking input forwarding,
idle/wake behavior, mouse events, prefix shortcuts, live settings, and reloads.
Font tests verify repeatable builds, preserved character mappings, spacing,
font features, and running/sleeping glyph geometry. Build outputs stay in
`target/` and the user's data directory. Set `RUNCAT_BINARY` to run an alternate
executable through the shell entry point.

Third-party font sources and their licenses are in `fonts/` and `fonts/vendor/`.
