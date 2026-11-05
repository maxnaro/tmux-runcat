# Installation

Start with the [quick start](../README.md#quick-start).

## Requirements

- tmux (tested against 3.6) on Linux or WSL
- Rust 1.89+ and Cargo to build; the running plugin needs only tmux
- Bash for the `.tmux` entry point
- Python 3.11+, tar with xz support, and sha256sum for the one-time font setup
- On WSL: Windows interoperability and Windows PowerShell for font installation

## TPM

For TPM, add `set -g @plugin 'maxnaro/tmux-runcat'` to your plugin list. After
TPM clones it, build the binary, run font setup, add the status placeholder,
and reload tmux. The entry point uses the current `TMUX` environment when no
socket arguments are supplied.


## Updating

Update your checkout through Git or TPM, then rebuild the executable:

```sh
cd ~/.config/tmux/plugins/tmux-runcat
cargo build --release --locked --offline
```

Run `bash fonts/setup.sh` when an update adds or changes cat glyphs, then reload
your tmux configuration. Repeated loads replace the worker with the new build.

## Use as a dotfiles submodule

```sh
git submodule add git@github.com:maxnaro/tmux-runcat.git tmux/.config/tmux/plugins/tmux-runcat
git submodule update --init --recursive
cargo build --release --locked --offline --manifest-path tmux/.config/tmux/plugins/tmux-runcat/Cargo.toml
bash tmux/.config/tmux/plugins/tmux-runcat/fonts/setup.sh
```

Commit plugin changes in this repository first, then update its pointer in the
parent dotfiles repository. Rebuild the executable after updating the plugin.

