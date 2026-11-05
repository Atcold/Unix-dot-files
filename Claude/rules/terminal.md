# Terminal

## Terminal experiments

- You teach me by experiment on my own machines: you run each step in my tmux pane, and I watch what you type and what comes out. On another machine, you open `ssh` in the pane and carry on there.
- Use the tool’s own interactive session: the shell, `ipython --nosep --no-banner`, or the equivalent for that language. Leave it open at the end, because I may carry on from there.
- Every step ends with two spaces, `#`, one space, and a short comment saying what it shows, so the explanation sits beside the code and its output and the line fits the pane. Chat only says what the experiment found.
- Suggest one in a line when a few steps would settle something better than prose.
- A change to my terminal setup is tested the same way: you run it in my pane while I watch, instead of testing it out of sight and telling me what to try.

## Blackboard

- My pane is also a blackboard: output I should look at goes there, because it keeps its colour and layout (`git s`, `git lg -5`, `git diff`, `rg`). Chat says only what matters in it.
- Colour is for the screen. Anything going into a pipe stays plain, so the next tool reads clean input.
- To show a few lines of a file, use `bat --paging=never -r 38:41 file`.

## Shared tmux panes

- If my window has no split, split it: side by side on a horizontal screen, stacked on a vertical one.
- Confirm the host from the prompt first. When you aren’t showing me something, check a remote machine with `ssh host '…'`.
- `clear` is its own step, followed by the command, so I can see what you type.
- Bash runs ble.sh in vi mode. Empty the buffer with `Escape`, then `dd`, then check it’s empty before typing `i`. `C-c` at a prompt only switches to normal mode. End every bash command with `C-j`, because Return doesn’t run a multi-line one.
