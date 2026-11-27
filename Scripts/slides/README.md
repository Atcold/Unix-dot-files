# slides

`slides` shows a deck of slides in one tmux pane and runs the deck's commands in a shell in another, so each command lands in that shell's history and its output stays on screen beside the explanation.

```
slides lesson.slides 3
```

The panes then show their numbers, as after the tmux prefix and `q`, and the one you press is the shell. The number after the deck is the first slide to show. A pane id such as `%7` skips the choice.

## Keys

`$` runs the slide's command in the shell, and again if pressed again. `n` or Return goes to the next slide, `b` goes back, and `q` quits. While the deck runs, its file name is the pane's title.

## Decks

Slides are separated by `---`. In a slide, `# ` starts the title, `$ ` a command that `$` runs, `% ` a command you type yourself, `! ` a step to follow, with keys in square brackets, `> ` a note shown once the command has run, and `| ` a line drawn as it is, for diagrams. Any other line is text, with `code` in backticks. A slide without a title is a title slide, whose `| ` lines and the line under them take the title's colour.

Lines such as `@ machine: linserv1, AlfDROID` at the top list names by kind (machine, program, port, file), and every slide shows them in the colour of their kind.

After the deck's file changes, `pkill -USR1 -f '/slides(\.py)? '` makes the player read it again, on the same slide. The pattern matches only the player: any other program that gets this signal stops.

## Install

```
ln -s ~/.settings/Scripts/slides/slides.py ~/.local/bin/slides
```

It needs Python 3 and tmux, and expects the shell to be bash with ble.sh in vi mode.
