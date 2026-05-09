# Two tweaks to ranger's titlebar:
#   1. Replace fm.hostname with macOS computer name (e.g. AlfMAC5),
#      not socket.gethostname() (which on Wi-Fi yields CIMS-CFAC-AP5.local).
#   2. Tag the user / @-separator / hostname segments with distinct contexts
#      (user_part, sep_part, host_part) so the colorscheme can colour them
#      independently like the bash prompt does.

from __future__ import (absolute_import, division, print_function)

import subprocess

import ranger.api
from ranger.gui import context as _ctx
from ranger.gui.widgets.titlebar import TitleBar


for _key in ('user_part', 'sep_part', 'host_part'):
    if _key not in _ctx.CONTEXT_KEYS:
        _ctx.CONTEXT_KEYS.append(_key)
        setattr(_ctx.Context, _key, False)


def _mac_computer_name():
    try:
        out = subprocess.check_output(
            ['networksetup', '-getcomputername'],
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.decode('utf-8', 'replace').strip() or None


_orig_hook_init = ranger.api.hook_init


def hook_init(fm):
    name = _mac_computer_name()
    if name:
        fm.hostname = name
    return _orig_hook_init(fm)


ranger.api.hook_init = hook_init


def _get_left_part(self, bar):
    if self.settings.hostname_in_titlebar:
        clr = 'bad' if self.fm.username == 'root' else 'good'

        bar.add(self.fm.username, 'hostname', 'user_part', clr, fixed=True)
        bar.add('@',              'hostname', 'sep_part',  clr, fixed=True)
        bar.add(self.fm.hostname, 'hostname', 'host_part', clr, fixed=True)
        bar.add(' ',              'hostname', 'sep_part',  clr, fixed=True)

    pathway = self.fm.thistab.pathway
    if self.settings.tilde_in_titlebar \
            and (self.fm.thisdir.path.startswith(self.fm.home_path + "/")
                 or self.fm.thisdir.path == self.fm.home_path):
        pathway = pathway[self.fm.home_path.count('/') + 1:]
        bar.add('~/', 'directory', fixed=True)

    for path in pathway:
        clr = 'link' if path.is_link else 'directory'
        bar.add(path.basename, clr, directory=path)
        bar.add('/', clr, fixed=True, directory=path)

    if self.fm.thisfile is not None and \
            self.settings.show_selection_in_titlebar:
        bar.add(self.fm.thisfile.relative_path, 'file')


TitleBar._get_left_part = _get_left_part
