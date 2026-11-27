"""Slideshow in a tmux pane, beside a shell pane.

Usage: python3 slides.py slides.txt <shell-pane-id> [first-slide]
Slides are separated by '---'. In a slide, '# ' is the title, '$ ' a command the slideshow runs
in the shell pane, '% ' a command you type there yourself, '! ' a line of key presses
([Tab] draws a key), '> ' a note shown once the command has run, and any other line is text
(`code` in backticks). A line starting with '| ' is drawn as it is, for diagrams. A slide with no
'# ' is a title slide: its '| ' lines, such as block letters, and the line under them, the subtitle,
are drawn in the title's colour. Lines such as
'@ machine: linserv1, AlfDROID', above the first '---' block or in it, list names by kind (machine,
program, port, file), and every slide shows them in the colour of their kind. The shell pane runs bash with ble.sh in vi mode.
Keys: Return (run the command, or go to the next slide), b (back), q (quit).
"""
import os, re, select, shutil, subprocess, sys, termios, textwrap, tty


def rgb(h):
    return "\033[38;2;%d;%d;%dm" % tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


# Roles, ColorBrewer Set3: title blue, code orange, attribute purple, description pink,
# note and the Tab key green.
TITLE = "\033[1m" + rgb("#80b1d3")
CODE, ATTR, DESC, NOTE = rgb("#fdb462"), rgb("#bebada"), rgb("#fccde5"), rgb("#b3de69")
KINDS = {"machine": rgb("#8dd3c7"), "program": rgb("#fb8072"), "port": rgb("#ffed6f"),
         "file": rgb("#bebada")}
NAMES = {}   # name -> kind, from the deck's '@ ' lines
TAB = "\033[1;7m" + NOTE   # reverse video: drawn as a key cap
TEXT, DIM, RESET = "\033[0m", "\033[2m", "\033[0m"


def paint(text, base):
    """Colour the deck's names by kind, returning to base after each."""
    if not NAMES:
        return text
    names = "|".join(re.escape(n) for n in sorted(NAMES, key=len, reverse=True))
    return re.sub(rf"(?<![\w./~-])(?:{names})(?![\w-]|\.\w)",
                  lambda m: KINDS[NAMES[m[0]]] + m[0] + base, text)


def prose(lines, base=TEXT):
    """Colour `code spans` orange and names by kind; a span may run across wrapped lines."""
    out, on = [], False
    for line in lines:
        s = ""
        for j, part in enumerate(line.split("`")):
            if j:
                on = not on
            c = CODE if on else base
            s += c + paint(part, c)
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
        cur += c + (w if c == RESET + DIM else paint(w, c)) + RESET
        n += len(w)
    lines.append(cur)
    return lines


def parse(path):
    slides = []
    for block in open(path).read().split("\n---\n"):
        s = {"title": "", "text": [], "cmd": None, "type": False, "note": [], "keys": []}
        for line in block.strip().splitlines():
            if line.startswith("@ "):
                kind, _, names = line[2:].partition(":")
                NAMES.update({n.strip(): kind.strip() for n in names.split(",")})
            elif line.startswith("# "):
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
    """The pane ends in the two-line prompt, 'user@machine folder' then '$', here or over ssh."""
    lines = [l for l in tmux("capture-pane", "-p", "-t", pane).splitlines() if l.strip()]
    return len(lines) > 1 and lines[-1].strip() == "$" and bool(re.match(r"\w+@\w+ ", lines[-2]))


def clear_line(pane):
    """Empty ble.sh's line in vi mode, then enter insert mode."""
    tmux("send-keys", "-t", pane, "Escape", "dd")
    tmux("send-keys", "-t", pane, "i")


def is_code(line):
    """A diagram line, or a line that is one code span."""
    return line.startswith("| ") or bool(re.fullmatch(r"`[^`]+`", line))


def layout(s, width, note):
    """The slide's lines, with a blank line only between text and code."""
    text = []
    for j, line in enumerate(s["text"]):
        diagram = line.startswith("| ")
        if j and is_code(line) != is_code(s["text"][j - 1]):
            text.append("")
        if diagram and not s["title"]:
            text.append(TITLE + line[2:] + RESET)   # a title slide: its letters take the title's colour
        elif diagram:
            link = line[2:].lstrip().startswith("│")
            text.append(DIM + line[2:] if link else TEXT + paint(line[2:], TEXT))
        elif not s["title"] and line == next(l for l in s["text"] if l.strip() and not l.startswith("| ")):
            text += [TITLE + w + RESET for w in textwrap.wrap(line, width)]   # the subtitle, under the letters
        else:
            text += prose(textwrap.wrap(line, width))
    text = [("", l) for l in text]
    if s["title"]:
        text = [(TEXT, "")] + text
    lines = [(TITLE, s["title"])] if s["title"] else []
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
    if note and s["note"]:
        wrapped = [w for t in s["note"] for w in textwrap.wrap(t, width)]
        lines += [(TEXT, "")] + [("", l) for l in prose(wrapped, NOTE)]
    return lines


def draw(s, i, n, state):
    cols, rows = shutil.get_terminal_size()
    width = min(cols - 8, 100)
    lines = layout(s, width, state == "ran")
    if state == "busy":
        lines += [(TEXT, ""), (NOTE, "The shell pane is not at a prompt. Finish what runs there, then press Return.")]
    if s["cmd"] and not s["type"] and state in ("new", "busy"):
        foot = "Return  run it in the pane below      b  back      q  quit"
    else:
        foot = "Return  next slide      b  back      q  quit"
    left = " " * max((cols - width) // 2, 1)
    top = max((rows - 1 - len(lines)) // 2, 0)   # the keys take the last row
    sys.stdout.write("\033[2J\033[H\033[?25l" + "\n" * top)
    sys.stdout.write("\n".join(left + c + t + RESET for c, t in lines))
    keys = f"{i + 1}/{n}   {foot}"[:cols - len(left)]
    sys.stdout.write(f"\033[{rows};1H" + left + DIM + keys + RESET)
    sys.stdout.flush()


def main():
    slides, pane = parse(sys.argv[1]), sys.argv[2]
    i, state = (int(sys.argv[3]) - 1 if len(sys.argv) > 3 else 0), "new"
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    try:
        draw(slides[i], i, len(slides), state)
        size = shutil.get_terminal_size()
        while True:
            if not select.select([fd], [], [], 0.2)[0]:   # no key: redraw if the pane was resized
                if shutil.get_terminal_size() != size:
                    size = shutil.get_terminal_size()
                    draw(slides[i], i, len(slides), state)
                continue
            k = os.read(fd, 1).decode(errors="ignore")
            if not k:
                break
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
