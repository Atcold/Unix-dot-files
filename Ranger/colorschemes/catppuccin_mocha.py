# This file is part of ranger, the console file manager.
# Available at https://github.com/ranger/ranger
# License: GNU GPL version 3, see the file "AUTHORS" for details.
# This theme was greatly inspired by "Dracula" for ranger
# It can be found in: `https://github.com/dracula/ranger`

from ranger.gui.color import bold, default, default_colors, normal, reverse
from ranger.gui.colorscheme import ColorScheme

ROSEWATER = 224
FLAMINGO = 224
PINK = 218
MAUVE = 183
RED = 211
MAROON = 217
PEACH = 216
YELLOW = 223
GREEN = 151
TEAL = 116
SKY = 117
SAPPHIRE = 117
BLUE = 111
LAVENDER = 147
TEXT = 189
SUBTEXT_1 = 146
SUBTEXT_0 = 146
OVERLAY_2 = 103
OVERLAY_1 = 103
OVERLAY_0 = 60
SURFACE_2 = 59
SURFACE_1 = 59
SURFACE_0 = 59
BASE = 16
MANTLE = 16
CRUST = 16


class CatppuccinMocha(ColorScheme):
    progress_bar_color = BLUE

    def verify_browser(self, context, fg, bg, attr):
        if context.selected:
            # attr = reverse
            bg = SURFACE_0
            fg = BASE
            attr &= ~bold
        else:
            attr = normal

        if context.empty or context.error:
            bg = RED
            fg = BASE

        if context.border:
            fg = BLUE

        if context.document:
            attr |= normal
            fg = MAUVE

        # Media detection => image, video, audio, else
        if context.media:
            if context.image:
                attr |= normal
                fg = YELLOW
            elif context.video:
                fg = RED
            elif context.audio:
                fg = TEAL
            else:
                fg = GREEN  # e.g., .bin, .iso, etc.

        if context.container:
            # e.g. .tar, .zip, etc.
            attr |= bold
            fg = MAROON

        if context.directory:
            attr |= bold
            fg = SAPPHIRE

        elif context.executable and not any(
            (context.media, context.container, context.fifo, context.socket)
        ):
            attr |= bold
            fg = GREEN

        if context.socket:
            fg = PINK
            attr |= bold

        if context.fifo or context.device:
            fg = YELLOW
            if context.device:
                attr |= bold

        if context.link:
            # Good link => TEAL, bad => MAUVE
            fg = TEAL if context.good else MAUVE

        # Tag marker => bold highlight
        if context.tag_marker and not context.selected:
            attr |= bold
            # We'll conditionally change color if it's red/magenta
            if fg in (RED, PINK, MAROON):
                fg = 15  # white
            else:
                fg = RED

        if not context.selected and (context.cut or context.copied):
            fg = OVERLAY_1
            attr |= bold

        # Main column markings
        if context.main_column:
            if context.selected:
                attr |= bold
            if context.marked:
                attr |= bold
                fg = YELLOW

        if context.badinfo:
            if attr & reverse:
                bg = PINK
            else:
                fg = PINK

        if context.inactive_pane:
            fg = TEAL  # or CYAN

        return fg, bg, attr

    def verify_titlebar(self, context, fg, bg, attr):
        attr |= bold
        if context.hostname:
            fg = RED if context.bad else GREEN
        elif context.directory:
            fg = BLUE
        elif context.tab:
            if context.good:
                bg = GREEN
        elif context.link:
            fg = TEAL

        return fg, bg, attr

    def verify_statusbar(self, context, fg, bg, attr):
        if context.permissions:
            if context.good:
                fg = GREEN
            elif context.bad:
                bg = PINK
                fg = OVERLAY_1

        if context.marked:
            attr |= bold | reverse
            fg = YELLOW

        if context.frozen:
            attr |= bold | reverse
            fg = TEAL

        if context.message:
            if context.bad:
                attr |= bold
                fg = RED

        if context.loaded:
            bg = self.progress_bar_color

        if context.vcsinfo:
            fg = BLUE
            attr &= ~bold

        if context.vcscommit:
            fg = YELLOW
            attr &= ~bold

        if context.vcsdate:
            fg = TEAL
            attr &= ~bold

        return fg, bg, attr

    def verify_taskview(self, context, fg, bg, attr):
        if context.title:
            fg = BLUE  # or TEAL

        if context.selected:
            attr |= reverse

        if context.loaded:
            if context.selected:
                fg = self.progress_bar_color
            else:
                bg = self.progress_bar_color

        return fg, bg, attr

    def verify_vcsfile(self, context, fg, bg, attr):
        attr &= ~bold

        if context.vcsconflict:
            fg = PINK
        elif context.vcschanged:
            fg = RED
        elif context.vcsunknown:
            fg = RED
        elif context.vcsstaged:
            fg = GREEN
        elif context.vcssync:
            fg = GREEN
        elif context.vcsignored:
            fg = default

        return fg, bg, attr

    def verify_vcsremote(self, context, fg, bg, attr):
        # Same pattern: remove bold, set color by VCS status
        attr &= ~bold

        if context.vcssync or context.vcsnone:
            fg = GREEN
        elif context.vcsbehind:
            fg = RED
        elif context.vcsahead:
            fg = TEAL
        elif context.vcsdiverged:
            fg = PINK
        elif context.vcsunknown:
            fg = RED

        return fg, bg, attr

    def use(self, context):
        fg, bg, attr = default_colors

        if context.reset:
            return default_colors

        elif context.in_browser:
            fg, bg, attr = self.verify_browser(context, fg, bg, attr)

        elif context.in_titlebar:
            fg, bg, attr = self.verify_titlebar(context, fg, bg, attr)

        elif context.in_statusbar:
            fg, bg, attr = self.verify_statusbar(context, fg, bg, attr)

        # Highlight text matches
        if context.text and context.highlight:
            attr |= reverse

        # Task view
        if context.in_taskview:
            fg, bg, attr = self.verify_taskview(context, fg, bg, attr)

        # VCS file or remote
        if context.vcsfile and not context.selected:
            fg, bg, attr = self.verify_vcsfile(context, fg, bg, attr)
        elif context.vcsremote and not context.selected:
            fg, bg, attr = self.verify_vcsremote(context, fg, bg, attr)

        return fg, bg, attr
