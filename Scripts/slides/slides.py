"""Slideshow in a tmux pane, beside a shell pane.

Usage: python3 slides.py slides.txt <shell-pane-id> [first-slide]
Slides are separated by '---'. In a slide, '# ' is the title, '$ ' a command the slideshow runs
in the shell pane, '% ' a command you type there yourself, '! ' a line of key presses
([Tab] draws a key), '> ' a note shown once the command has run, and any other line is text
(`code` in backticks). The shell pane runs bash with ble.sh in vi mode.
Keys: Return (run the command, or go to the next slide), b (back), q (quit).
"""
import re, shutil, subprocess, sys, termios, textwrap, tty


def rgb(h):
    return "\033[38;2;%d;%d;%dm" % tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


# Roles, ColorBrewer Set3: title blue, code orange, attribute purple, description pink,
# note and the Tab key green.
TITLE = "\033[1m" + rgb("#80b1d3")
CODE, ATTR, DESC, NOTE = rgb("#fdb462"), rgb("#bebada"), rgb("#fccde5"), rgb("#b3de69")
TAB = "\033[1;7m" + NOTE   # reverse video: drawn as a key cap
TEXT, DIM, RESET = "\033[0m", "\033[2m", "\033[0m"


def prose(lines):
    """Colour `code spans` orange; a span may run across wrapped lines."""
    out, on = [], False
    for line in lines:
        s = CODE if on else TEXT
        for ch in line:
            if ch == "`":
                on = not on
                s += CODE if on else TEXT
            else:
                s += ch
        out.append(s)
    return out


def command(line, width):
    """Colour a shell line and wrap it at width: verb orange, name:value purple,
    'description' pink, # comment dim. Continuation lines are indented."""
    code, _, comment = line.partition("  #")
    words = []
    for p in re.split(r"('[^']*')", code):
        if p.startswith("'"):
            words += [(DESC, w) for w in p.split()]
        else:
            for w in p.split():
                attr = re.fullmatch(r"[a-z.]+:\S+", w)
                words.append((ATTR if attr else CODE, w))
    if comment:
        words += [(RESET + DIM, "#")] + [(RESET + DIM, w) for w in comment.split()]
    lines, cur, n = [], DIM + "$" + RESET, 1
    for c, w in words:
        if n + 1 + len(w) > width:
            lines.append(cur)
            cur, n = "   ", 3
        else:
            cur, n = cur + " ", n + 1
        cur += c + w + RESET
        n += len(w)
    lines.append(cur)
    return lines


def parse(path):
    slides = []
    for block in open(path).read().split("\n---\n"):
        s = {"title": "", "text": [], "cmd": None, "type": False, "note": [], "keys": []}
        for line in block.strip().splitlines():
            if line.startswith("# "):
                s["title"] = line[2:]
            elif line[:2] in ("$ ", "% "):
                s["cmd"], s["type"] = line[2:], line[0] == "%"
            elif line.startswith("! "):
                s["keys"].append(line[2:])
            elif line.startswith("> "):
                s["note"].append(line[2:])
            else:
                s["text"].append(line)
        slides.append(s)
    return slides


def tmux(*args):
    return subprocess.run(["tmux", *args], capture_output=True, text=True).stdout.strip()


def at_prompt(pane):
    return tmux("display", "-p", "-t", pane, "#{pane_current_command}") == "bash"


def clear_line(pane):
    """Empty ble.sh's line in vi mode, then enter insert mode."""
    tmux("send-keys", "-t", pane, "Escape", "dd")
    tmux("send-keys", "-t", pane, "i")


def draw(s, i, n, state):
    cols, rows = shutil.get_terminal_size()
    width = min(cols - 8, 100)
    lines = [(TITLE, s["title"])]
    wrapped = [w for t in s["text"] for w in textwrap.wrap(t, width)]
    text = [(TEXT, "")] + [("", w) for w in prose(wrapped)]
    if not s["type"]:
        lines += text   # a slide that runs its command explains it first
    if s["cmd"]:
        if s["type"]:
            lines += [(TEXT, ""), (DIM, "Type this in the pane below:")]
        lines += [(TEXT, "")] + [("", l) for l in command(s["cmd"], width)]
        if s["keys"]:
            lines += [(TEXT, "")]
            keyed = [w for t in s["keys"] for w in textwrap.wrap(t, width)]
            lines += [("", re.sub(r"\[(\w+)\]", lambda m: TAB + " " + m[1] + " " + RESET, w)) for w in prose(keyed)]
    if s["type"]:
        lines += [(TEXT, ""), (DIM, "What it does:")] + text[1:]   # what to type comes first
    if state == "ran" and s["note"]:
        lines += [(TEXT, "")] + [(NOTE, w) for t in s["note"] for w in textwrap.wrap(t, width)]
    if state == "busy":
        lines += [(TEXT, ""), (NOTE, "The shell pane is not at a prompt. Finish what runs there, then press Return.")]
    if s["cmd"] and not s["type"] and state in ("new", "busy"):
        foot = "Return  run it in the pane below      b  back      q  quit"
    else:
        foot = "Return  next slide      b  back      q  quit"
    lines += [(TEXT, ""), (DIM, f"{i + 1}/{n}   {foot}")]
    left = " " * max((cols - width) // 2, 1)
    top = max((rows - len(lines)) // 2, 0)
    sys.stdout.write("\033[2J\033[H\033[?25l" + "\n" * top)
    sys.stdout.write("\n".join(left + c + t + RESET for c, t in lines))
    sys.stdout.flush()


def main():
    slides, pane = parse(sys.argv[1]), sys.argv[2]
    i, state = (int(sys.argv[3]) - 1 if len(sys.argv) > 3 else 0), "new"
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    try:
        draw(slides[i], i, len(slides), state)
        while True:
            k = sys.stdin.read(1)
            if k == "q":
                break
            s = slides[i]
            if k == "b":
                i, state = max(i - 1, 0), "new"
            elif k in "\r\n":
                if s["cmd"] and not s["type"] and state in ("new", "busy"):
                    if not at_prompt(pane):
                        state = "busy"
                    else:
                        clear_line(pane)
                        tmux("send-keys", "-t", pane, s["cmd"], "C-j")
                        state = "ran"
                elif i + 1 < len(slides):
                    i, state = i + 1, "new"
            draw(slides[i], i, len(slides), state)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        sys.stdout.write("\033[?25h" + RESET + "\n")


if __name__ == "__main__":
    main()
