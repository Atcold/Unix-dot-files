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

## Where am I?

- **Which window**: the **top row** is the window list. The current window is shown in **red** with a `•`; `◀` marks the last window.
- **Which pane**: when a window is split, the **active pane** has a **bold violet** border (thicker than the dim grey inactive borders), and its top edge is labelled in violet with the pane index and running command; inactive panes are labelled in dim grey.
- **Exact coordinates**: the **bottom-right** always shows `session  window:pane` — e.g. `myproj 2:1` means session *myproj*, window 2, pane 1.

> Note: a pane border (and the green/`here` label) only appears when a window has **more than one pane**. With a single pane, use the bottom-right `window:pane` readout instead.

## Status bar

- **Top row**: window list — `•` current window, `◀` last window
- **Bottom row**: hostname :: session window:pane :: date :: time
- Window names: repo root (if in a git repo), `~` (if home), or current dir — up to 16 chars
