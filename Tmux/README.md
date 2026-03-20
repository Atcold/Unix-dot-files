# Tmux cheatsheet

## Concepts

- **Session**: a collection of windows, persists even when detached. Useful to have one per project.
- **Window**: like a tab — full-screen, shows in the status bar.
- **Pane**: a split within a window.

## Sessions

| Key | Action |
|-----|--------|
| `s` | List and switch sessions interactively |
| `(` / `)` | Previous / next session |
| `$` | Rename current session |
| `d` | Detach (session keeps running in background) |

To re-attach: `tmux attach`, then `s` to pick a session.

## Status bar

- **Top row**: window list — `•` current window, `◀` last window
- **Bottom row**: hostname :: session window:pane :: date :: time
- Window names: repo root (if in a git repo), `~` (if home), or current dir — up to 16 chars
