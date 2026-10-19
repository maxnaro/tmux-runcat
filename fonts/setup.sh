#!/usr/bin/env bash
# Build and install the pinned font dependencies without pip or network access.
set -euo pipefail

FONT_SETUP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FONT_DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/tmux-runcat"
FONT_BUILD_ONLY=false
case "${1:-}" in
    '') ;;
    --build-only) FONT_BUILD_ONLY=true ;;
    *) printf 'Usage: %s [--build-only]\n' "$0" >&2; exit 2 ;;
esac

if ! command -v python3 >/dev/null 2>&1 || ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))'; then
    printf 'RunCat setup requires Python 3.11 or newer on PATH.\n' >&2
    exit 1
fi

(
    cd "$FONT_SETUP_DIR/vendor"
    sha256sum --check SHA256SUMS
)
mkdir -p "$FONT_DATA_DIR/source" "$FONT_DATA_DIR/generated"
tar -xJf "$FONT_SETUP_DIR/vendor/JetBrainsMono-v3.5.1.tar.xz" -C "$FONT_DATA_DIR/source"
PYTHONPATH="$FONT_SETUP_DIR/vendor/fonttools-4.67.0-py3-none-any.whl" \
    PYTHONDONTWRITEBYTECODE=1 python3 "$FONT_SETUP_DIR/build-runcat-font.py" \
    "$FONT_DATA_DIR/source" "$FONT_DATA_DIR/generated"

if "$FONT_BUILD_ONLY"; then
    printf 'Built RunCat fonts in %s\n' "$FONT_DATA_DIR/generated"
    exit 0
fi

if [[ -n "${WSL_DISTRO_NAME:-}" ]]; then
    # The terminal renders on Windows. Font installation inside WSL alone
    # cannot supply its glyphs to Windows Terminal.
    FONT_POWERSHELL='/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe'
    if [[ ! -x "$FONT_POWERSHELL" ]] || ! command -v wslpath >/dev/null 2>&1; then
        printf 'RunCat requires WSL Windows interoperability and wslpath to install its Windows fonts.\n' >&2
        exit 1
    fi
    "$FONT_POWERSHELL" -NoProfile -ExecutionPolicy Bypass \
        -File "$(wslpath -w "$FONT_SETUP_DIR/install-windows.ps1")" \
        -FontDirectory "$(wslpath -w "$FONT_DATA_DIR/generated")"
else
    FONT_INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/fonts/tmux-runcat"
    mkdir -p "$FONT_INSTALL_DIR"
    for font_file in "$FONT_DATA_DIR/generated/"*.ttf; do
        ln -sfn "$font_file" "$FONT_INSTALL_DIR/$(basename "$font_file")"
    done
    if command -v fc-cache >/dev/null 2>&1; then
        fc-cache -f "$FONT_INSTALL_DIR"
    fi
    printf 'Installed RunCat fonts. Select "JetBrainsMono RunCat Active" in your terminal.\n'
fi
