# Fix terminal colours
gconftool-2 -s -t bool   /apps/gnome-terminal/profiles/Default/use_theme_background false
gconftool-2 -s -t bool   /apps/gnome-terminal/profiles/Default/use_theme_colors false
gconftool-2 -s -t string /apps/gnome-terminal/profiles/Default/background_color '#121212121212'
gconftool-2 -s -t string /apps/gnome-terminal/profiles/Default/foreground_color '#c5c5c8c8c6c6'
gconftool-2 -s -t string /apps/gnome-terminal/profiles/Default/palette          '#28282a2a2e2e:#8c8c38383838:#73737a7a3535:#c4c483835454:#51516d6d8585:#6d6d54547575:#4d4d73736e6e:#59595f5f6666:#37373b3b4141:#cccc66666666:#b5b5bdbd6868:#f0f0c6c67474:#8181a2a2bebe:#b2b29494bbbb:#8a8abebeb7b7:#c5c5c8c8c6c6'
