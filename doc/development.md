# Development

[![Rust coverage](https://codecov.io/gh/maxnaro/tmux-runcat/branch/main/graph/badge.svg?flag=rust)](https://app.codecov.io/gh/maxnaro/tmux-runcat)
[![Python coverage](https://codecov.io/gh/maxnaro/tmux-runcat/branch/main/graph/badge.svg?flag=python)](https://app.codecov.io/gh/maxnaro/tmux-runcat)


```sh
cargo fmt --check
cargo clippy --locked --offline --all-targets -- -D warnings
cargo test --locked --offline
cargo build --release --locked --offline
python3 fonts/tests/test_build.py
python3 tests/live_tmux.py
python3 tests/roaming_tmux.py
bash -n runcat.tmux fonts/setup.sh
```

The live test starts an isolated tmux server and PTY, checking Pet Cats actions,
live skin changes, fast redraws,
input forwarding, idle/wake behavior, mouse events, prefix shortcuts, live
settings, and reloads.
Font tests verify repeatable builds, preserved character mappings, spacing,
font features, custom base fonts, and running/sleeping glyph geometry.
On Windows, `powershell.exe -NoProfile -ExecutionPolicy Bypass -File
fonts/tests/test-windows-terminal.ps1` checks terminal settings using temporary
files. Build outputs stay in
`target/` and the user's data directory. Set `RUNCAT_BINARY` to run an alternate
executable through the shell entry point.

Third-party font sources and their licenses are in `fonts/` and `fonts/vendor/`.

### Continuous integration

Tests run on every push and pull request. Rust tests cover Rust 1.89 and stable;
Linux integration tests use tmux 3.6 and the release binary. Font tests use
Python 3.11. Windows Terminal settings tests use Windows PowerShell 5.1.
Lint checks Rust formatting and Clippy, ShellCheck, Ruff correctness rules,
actionlint, and PSScriptAnalyzer error-level findings.

Rust coverage measures unit-test execution. Python coverage includes the font
builder subprocesses and excludes tests and vendored code. Reports remain
available as Actions artifacts for 14 days. Each language has its own Codecov
check, allowing no coverage decrease relative to the base commit.

To reproduce Python coverage locally, install `coverage==7.10.7`, then run:

```sh
export COVERAGE_RCFILE="$PWD/.coveragerc"
export COVERAGE_FILE="$PWD/target/coverage/.coverage"
python3 -m coverage run -m unittest discover -s fonts/tests -p 'test_*.py'
python3 -m coverage combine
python3 -m coverage report
```

Install `ruff==0.12.12` to run
`ruff check --select E9,F --target-version py311 fonts tests`.
Run `shellcheck runcat.tmux fonts/setup.sh` and `actionlint` for shell and
workflow checks. CI never rewrites source files.

## Artwork

The README demos use Cat-1 from the bundled CC0 [Pet Cats Pack](https://luizmelo.itch.io/pet-cat-pack), rendered as foreground silhouettes with eye cutouts. They illustrate the optional Pet Cats skin with roaming enabled.
