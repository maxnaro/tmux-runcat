#!/usr/bin/env bash
# Standalone / TPM entry point. Font installation is a separate setup step.
set -euo pipefail
plugin_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
binary="${RUNCAT_BINARY:-$plugin_dir/target/release/tmux-runcat}"
if [[ ! -x "$binary" ]]; then
    printf 'tmux-runcat: build first with cargo build --release --locked --manifest-path "%s/Cargo.toml"\n' "$plugin_dir" >&2
    exit 1
fi
exec "$binary" load "$plugin_dir" "$@"
