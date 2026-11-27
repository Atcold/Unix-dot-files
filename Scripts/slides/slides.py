#!/usr/bin/env python3
r"""slides: a deck of slides in this tmux pane, its commands run in a shell pane.

Usage: slides deck.slides [first-slide] [%shell-pane]

Without a pane, the panes show their numbers, as after the tmux prefix and q,
and the one you press is the shell.

Keys: $ runs the slide's command (again if pressed again), n or Return goes
to the next slide, b goes back, and q quits.

After an edit, pkill -USR1 -f '/slides(\.py)? ' reloads the deck on the same
slide. The deck format is in README.md, next to this file.
"""
import os, re, select, shutil, signal, socket, subprocess, sys, tempfile, termios, textwrap, tty


def rgb(h):
    return "\033[38;2;%d;%d;%dm" % tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


# Roles, ColorBrewer Set3: title blue, code orange, attribute purple, description pink,
# note and the Tab key green.
TITLE = "\033[1m" + rgb("#80b1d3")
CODE, ATTR, DESC, NOTE = rgb("#fdb462"), rgb("#bebada"), rgb("#fccde5"), rgb("#b3de69")
KINDS = {"machine": rgb("#8dd3c7"), "program": rgb("#fb8072"), "port": rgb("#ffed6f"),
         "file": rgb("#bebada")}
NAMES = {}   # name -> kind, from the deck's '@ ' lines
TAB = rgb("#bc80bd")   # a key name, such as [Tab] or [Return]: purple
TEXT, DIM, RESET = "\033[0m", "\033[2m", "\033[0m"
PROMPT = "\033[1;32m"   # the $ of my bash prompt: bold green
TYPED = "\033[1m" + rgb("#ffed6f")   # the % of a line you type yourself: bold yellow


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


def command(line, width, mark="$"):
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
    lines, cur, n = [], (PROMPT if mark == "$" else TYPED) + mark + RESET, 1
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
            text += [TITLE + w + RESET for w in textwrap.wrap(line, width)] + [""]   # the subtitle, under the letters
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
        lines += [(TEXT, "")] + [("", l) for l in command(s["cmd"], width, "%" if s["type"] else "$")]   # % : you type it
        if s["keys"]:
            lines += [(TEXT, "")]
            keyed = [w for t in s["keys"] for w in textwrap.wrap(t, width)]
            lines += [("", re.sub(r"(?<!\x1b)\[([^\]\[\x1b]+)\]", lambda m: TAB + m[1] + RESET, w)) for w in prose(keyed)]
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
        lines += [(TEXT, ""), (NOTE, "The shell pane is not at a prompt. Finish what runs there, then press $.")]
    if s["cmd"] and not s["type"]:
        run = "run again" if state == "ran" else "run below"
        foot = f"$  {run}      n  next      b  back      q  quit"
    else:
        foot = "n  next      b  back      q  quit"
    left = " " * max((cols - width) // 2, 1)
    top = max((rows - 1 - len(lines)) // 2, 0)   # the keys take the last row
    sys.stdout.write("\033[2J\033[H\033[?25l" + "\n" * top)
    sys.stdout.write("\n".join(left + c + t + RESET for c, t in lines))
    page = f"{i + 1}/{n}"
    keys = foot[:max(cols - 2 * len(left) - len(page) - 3, 0)]
    keys = keys.replace("$", RESET + PROMPT + "$" + RESET + DIM, 1)   # the run key in the prompt's green
    sys.stdout.write(f"\033[{rows};1H" + left + DIM + keys + RESET)
    sys.stdout.write(f"\033[{rows};{cols - len(left) - len(page) + 1}H" + DIM + page + RESET)   # the page number at the right
    sys.stdout.flush()


def pick_pane():
    """Show the panes' numbers, as after prefix q, and return the id of the one pressed."""
    with tempfile.NamedTemporaryFile("r", suffix=".pane") as f:
        tmux("display-panes", "-d", "0", f"run-shell 'echo %% > {f.name}'")
        while not open(f.name).read().strip():
            select.select([], [], [], 0.1)
        return open(f.name).read().strip()


# The help, laid out and coloured like radio's and spark's: name, arguments in grey, what it does
KEYS = [("$", "Run the slide's command in the shell pane."),
        ("n", "The next slide. Return too."),
        ("b", "Back one slide."),
        ("q", "Quit.")]


def usage():
    tty_ = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
    def c(t, code): return f"\033[{code}m{t}\033[0m" if tty_ else t
    print("\n" + c("slides", "1;35") + c(" — a deck in this tmux pane, its commands in a shell beside it", "2"))
    print(c("The deck reloads on the same slide after pkill -USR1 -f '/slides(\\.py)? '.", "2"))
    print("\n" + c("Usage", "1"))
    print("  " + c("slides", "1;36") + c(" deck.slides [first-slide] [%shell-pane]", "2"))
    print(c("  Without a pane, the panes show their numbers; press the shell's.", "2"))
    print("\n" + c("Keys", "1"))
    for key, what in KEYS:
        print(f"  {c(key.ljust(4), '1;36')}{what}")
    print("\n" + c("The deck format is in README.md, next to this script.", "2") + "\n")


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        usage()
        sys.exit(0)
    if not os.path.isfile(sys.argv[1]):
        sys.exit(f"slides: no deck at {sys.argv[1]}")
    rest = sys.argv[2:]
    first = next((int(a) for a in rest if a.isdigit()), 1)
    pane = next((a for a in rest if a.startswith("%")), None) or pick_pane()
    slides = parse(sys.argv[1])
    i, state = min(first, len(slides)) - 1, "new"
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    sys.stdout.write(f"\033]2;{os.path.basename(sys.argv[1])}\033\\")   # the pane's title, which its border shows
    try:
        draw(slides[i], i, len(slides), state)
        # Signals wake the loop through a pipe: SIGWINCH when the pane is resized, SIGUSR1 to reload.
        wake, waker = os.pipe()
        os.set_blocking(waker, False)
        signal.set_wakeup_fd(waker)
        for sig in (signal.SIGWINCH, signal.SIGUSR1):
            signal.signal(sig, lambda *_: None)
        while True:
            if wake in select.select([fd, wake], [], [])[0]:
                if signal.SIGUSR1 in os.read(wake, 64):   # the deck was edited: read it again
                    NAMES.clear()
                    slides = parse(sys.argv[1])
                    i = min(i, len(slides) - 1)
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
            elif k == "$" and s["cmd"] and not s["type"]:
                if not at_prompt(pane):
                    state = "busy"
                else:
                    clear_line(pane)
                    tmux("send-keys", "-t", pane, s["cmd"], "C-j")
                    state = "ran"
            elif k in "n\r\n" and i + 1 < len(slides):   # Return also goes on
                i, state = i + 1, "new"
            draw(slides[i], i, len(slides), state)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        sys.stdout.write(f"\033]2;{socket.gethostname()}\033\\")   # the default title back: the host
        sys.stdout.write("\033[?25h" + RESET + "\n")


if __name__ == "__main__":
    main()
