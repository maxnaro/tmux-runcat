# RunCat status animation

Run from the repository root:

```sh
bash fonts/setup.sh
```

Setup installs `JetBrainsMono RunCat v7` alongside the clean Nerd Font.
Use `--build-only` to build without installing or changing terminal settings.
Sources and tools are [bundled](vendor/README.md); setup needs Python 3.11+
but no downloads or pip. Build files live in
`${XDG_DATA_HOME:-~/.local/share}/tmux-runcat/`.

## Custom base fonts

Select a regular monospaced static TrueType font with `--base-font`. The
bundled fontTools handles the build offline; the original files are read only.

```bash
bash fonts/setup.sh \
  --base-font '/path/to/MyMono-Regular.ttf' \
  --bold-font '/path/to/MyMono-Bold.ttf' \
  --italic-font '/path/to/MyMono-Italic.ttf' \
  --bold-italic-font '/path/to/MyMono-BoldItalic.ttf'
```

Only the regular face is required. Supply optional faces from the same family
when available; missing faces are left for the terminal to synthesize. The
patched family defaults to `<original family> RunCat v7`. Use `--family
'My Mono RunCat'` to name it yourself. `--build-only` works with these options.
Setup prints the selected family, and WSL setup passes it to Windows Terminal.

The same options are available through environment variables, including when
the parent dotfiles setup invokes this script:

| Setup option | Environment variable |
| --- | --- |
| `--base-font` | `RUNCAT_BASE_FONT` |
| `--bold-font` | `RUNCAT_BOLD_FONT` |
| `--italic-font` | `RUNCAT_ITALIC_FONT` |
| `--bold-italic-font` | `RUNCAT_BOLD_ITALIC_FONT` |
| `--family` | `RUNCAT_FONT_FAMILY` |

Command arguments override environment variables. Keep your font files and options
together to reproduce custom builds.

Custom inputs must contain printable ASCII with equal character widths and
TrueType `glyf` outlines. Variable fonts, CFF/OpenType outlines, and web fonts
are rejected with an explanation; use a static TrueType export. Existing
characters and metrics are preserved. Use a Nerd Font base if your status bar
also needs Nerd Font device icons. A base that already uses one of the cat
codepoints is rejected rather than having its glyphs overwritten.

## Windows Terminal / WSL

Setup detects WSL and installs fonts in the current Windows user's font
directory using Windows PowerShell. WSL Windows interoperability must be
enabled. It selects the generated family (`JetBrainsMono RunCat v7` by default)
in stable Windows Terminal's defaults, WSL profiles, and profiles using the
previous default or an existing RunCat family, preserving other
settings. Settings and font registrations are backed up before changes.
Settings containing comments or trailing commas are accepted; changed files
are saved as standard JSON. Other terminal apps need their font selected in
their own settings.

Open a new terminal window if it has cached the old font. Choose
`JetBrainsMono Nerd Font` to use the clean font without the cat glyphs.
Installing fonts only inside WSL cannot supply them to Windows Terminal.

## Linux terminals

Setup installs the fonts in the user's font directory and refreshes fontconfig
when available. Select the printed family in your terminal. For Kitty,
you can instead map only the cat characters while keeping another main font:

```conf
symbol_map U+E400-U+E517,U+EFF0-U+EFFF,U+F600-U+F607,U+F620-U+F637,U+F640-U+F65F,U+F700-U+F8A3,U+100000-U+10009F,U+101000-U+10135B JetBrainsMono RunCat v7
```
