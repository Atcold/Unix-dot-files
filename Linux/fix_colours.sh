# Fix terminal colours
gconftool-2 -s -t bool   /apps/gnome-terminal/profiles/Default/use_theme_background false
gconftool-2 -s -t bool   /apps/gnome-terminal/profiles/Default/use_theme_colors false
gconftool-2 -s -t string /apps/gnome-terminal/profiles/Default/background_color '#121212121212'
gconftool-2 -s -t string /apps/gnome-terminal/profiles/Default/foreground_color '#f1f1ebebebeb'
gconftool-2 -s -t string /apps/gnome-terminal/profiles/Default/palette          '#484848483e3e:#dcdc25256666:#8f8fc0c02929:#d4d4c9c96e6e:#5555bcbccece:#93935858fefe:#5656b7b7a5a5:#acacadada1a1:#8f8f89897272:#ffff26267676:#b9b9fcfc3232:#fffff7f78080:#6b6be9e9ffff:#aeae8282ffff:#6b6bffffe4e4:#eaeaebebdada'
gconftool-2 -s -t string /apps/gnome-terminal/profiles/Default/cursor_shape         'underline'
