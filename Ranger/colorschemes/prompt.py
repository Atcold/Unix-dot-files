# Ranger colorscheme matching the bash prompt and Claude statusline:
#   bold magenta user, white @, bold blue hostname, bold yellow path.
# File-listing colors for core types (DIR, LINK, EXEC, ...) come from
# ~/.dir_colors so ranger matches `ls`. Per-extension ls colors are not
# applied — ranger's own filetype detection drives those.

from __future__ import (absolute_import, division, print_function)

import curses
import os

from ranger.colorschemes.default import Default
from ranger.gui.color import (
    blue, magenta, white, yellow,
    normal, bold, dim, reverse, BRIGHT,
)


_DIR_COLORS_PATH = os.path.expanduser('~/.dir_colors')

# SGR sub-codes we care about (italic/strikethrough have no curses equivalent).
_ATTR_SGR = {
    '1': curses.A_BOLD,
    '4': curses.A_UNDERLINE,
    '5': curses.A_BLINK,
    '7': curses.A_REVERSE,
}


def _parse_sgr(code):
    """Parse a `;`-separated SGR string into (fg, bg, attr).

    Only 256-colour escapes (`38;5;N` / `48;5;N`) and the attrs in _ATTR_SGR
    are honoured. Returns (-1, -1, 0) for parts it doesn't recognise.
    """
    fg, bg, attr = -1, -1, 0
    parts = code.split(';')
    i = 0
    while i < len(parts):
        p = parts[i]
        if p in _ATTR_SGR:
            attr |= _ATTR_SGR[p]
        elif p == '38' and i + 2 < len(parts) and parts[i + 1] == '5':
            fg = int(parts[i + 2])
            i += 2
        elif p == '48' and i + 2 < len(parts) and parts[i + 1] == '5':
            bg = int(parts[i + 2])
            i += 2
        elif p == '0':
            fg, bg, attr = -1, -1, 0
        i += 1
    return fg, bg, attr


def _load_core_ls_colors(path):
    """Read core-type entries (DIR, LINK, ...) from a dir_colors file."""
    out = {}
    try:
        fh = open(path)
    except IOError:
        return out
    with fh:
        for line in fh:
            line = line.split('#', 1)[0].strip()
            if not line:
                continue
            tokens = line.split(None, 1)
            if len(tokens) != 2:
                continue
            key, val = tokens[0], tokens[1].strip()
            if val == 'target' or val == '0':
                continue
            out[key] = _parse_sgr(val)
    return out


_CORE = _load_core_ls_colors(_DIR_COLORS_PATH)


def _apply(mapping, fg, bg, attr, keep_reverse):
    """Overlay an LS_COLORS mapping onto current fg/bg/attr."""
    f, b, a = mapping
    if f != -1:
        fg = f
    if b != -1:
        bg = b
    attr = a | (reverse if keep_reverse else 0)
    return fg, bg, attr


class Scheme(Default):
    def use(self, context):
        fg, bg, attr = Default.use(self, context)

        if context.in_titlebar:
            if context.user_part:
                fg, attr = magenta + BRIGHT, bold
            elif context.host_part:
                fg, attr = blue + BRIGHT, bold
            elif context.sep_part:
                fg, attr = white + BRIGHT, normal
            elif context.directory or context.file:
                fg, attr = yellow + BRIGHT, bold
            elif context.hostname:
                fg, attr = blue + BRIGHT, bold
            return fg, bg, attr

        if context.in_browser:
            mapping = None
            if context.link and not context.good:
                # Broken symlink. lstat sees mode 0o777 so ranger also flags
                # it as 'executable'; handle this branch first so the EXEC
                # color (orange) doesn't win.
                mapping = _CORE.get('ORPHAN')
            elif context.directory:
                mapping = _CORE.get('DIR')
            elif context.link and context.good:
                mapping = _CORE.get('LINK')
            elif context.socket:
                mapping = _CORE.get('SOCK')
            elif context.device:
                mapping = _CORE.get('BLK')
            elif context.fifo:
                mapping = _CORE.get('FIFO')
            elif context.executable and not any(
                    (context.media, context.container,
                     context.fifo, context.socket)):
                mapping = _CORE.get('EXEC')
            if mapping is not None:
                fg, bg, attr = _apply(mapping, fg, bg, attr,
                                      keep_reverse=context.selected)

        if context.in_statusbar:
            attr |= dim

        return fg, bg, attr
