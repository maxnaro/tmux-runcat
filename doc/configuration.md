# Configuration

Options apply live. Install the v7 fonts for all skins and sizes.

| Option | Default | Meaning |
| --------------------- | --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `@runcat-idle` | `2` | Maximum idle seconds before sleeping (0.1–3600); Pet Cats may finish short gestures earlier |
| `@runcat-min-fps` | `3` | Minimum running speed (1–20 FPS) |
| `@runcat-max-fps` | `0` | `0` or `unlimited` removes the cap; a positive FPS value sets an optional limit |
| `@runcat-size` | `medium` | `small` (1 cell), `medium` (2 cells), `large` (3 cells), or `xlarge` (4 cells) |
| `@runcat-skin` | `classic` | `classic` or `pet-cats` |
| `@runcat-spin-chance` | `0` | Pet Cats: percent chance per second of running to start an OIIA-style spin (0–100) |
| `@runcat-roam` | `off` | `on` lets the cat pace through the free space between the window list and right status |
| `@runcat-color` | `inherit` | Roaming foreground: ANSI colour name (including bright variants), `colour0`–`colour255`, `#RRGGBB`, `default` (terminal default), or `inherit` (status foreground) |

## Spinning and roaming

```tmux
set -g @runcat-skin pet-cats
set -g @runcat-roam on
set -g @runcat-spin-chance 0
```

Remove `#{@runcat-frame}` from your status format when roaming. The cat uses
free space between the window list and right status, turns at either edge,
and rests where it stops. Roaming needs a standard single-row status layout.
It hides when there is no room.

Typing wakes the cat and controls its speed. Pauses cycle through grooming,
idle, scratching, body licking, meowing, and sitting before lying down and
sleeping. Each pause selects one gesture. `@runcat-idle` sets the maximum delay;
short gestures may finish earlier. New input interrupts rest.

A positive spin chance enables spins while running, with an eight-second
cooldown. Spins stop after typing pauses and do not move the cat.

## Colour

Roaming inherits the status foreground. Set `@runcat-color` to override it;
invalid values inherit. For a stationary cat, use a status style:

```tmux
set -g status-right '#[fg=cyan]#{@runcat-frame}#[default] | %H:%M '
```

## Compatibility

The plugin needs the root `Any` binding and refuses to replace an existing
custom binding. Specific shortcuts retain precedence. Mouse, paste, copy-mode,
popup, and command-prompt input do not count as typing. Key contents are never
read or stored. Reloads replace the worker; detached clients pause animation.

For cursor flashes in Windows Terminal, add this before attaching a new client:

```tmux
set -as terminal-features ',xterm-256color:sync'
```
