# Development

Run checks from the repository root:

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

Windows Terminal checks: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File fonts/tests/test-windows-terminal.ps1`.

## Demo

With Pillow installed, run `python3 doc/render_demo.py`. It captures an isolated tmux session and renders its published glyphs with the patched font. The demo uses Pet Cats, roaming, xlarge size, an eight-second idle timeout, and a 24 FPS cap. Cuts separate different pauses.

Artwork: [Pet Cats Pack by LuizMelo](https://luizmelo.itch.io/pet-cat-pack), CC0. Font sources and licences are in `fonts/vendor/`.

## Coverage

Install `coverage==7.10.7`, then run:

```sh
export COVERAGE_RCFILE="$PWD/.coveragerc"
export COVERAGE_FILE="$PWD/target/coverage/.coverage"
python3 -m coverage run -m unittest discover -s fonts/tests -p 'test_*.py'
python3 -m coverage combine
python3 -m coverage report
```
