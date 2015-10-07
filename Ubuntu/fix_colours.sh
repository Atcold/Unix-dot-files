# Fix terminal colours
gconftool-2 -s -t bool   /apps/gnome-terminal/profiles/Default/use_theme_background false
gconftool-2 -s -t bool   /apps/gnome-terminal/profiles/Default/use_theme_colors false
gconftool-2 -s -t string /apps/gnome-terminal/profiles/Default/background_color '#000000000000'
gconftool-2 -s -t string /apps/gnome-terminal/profiles/Default/foreground_color '#F2F2F2F2F2F2'
gconftool-2 -s -t string /apps/gnome-terminal/profiles/Default/palette          '#202020202020:#5D5D1A1A1414:#42424E4E2424:#6F6F50502828:#26263E3E4E4E:#3E3E1F1F5050:#23234E4E3F3F:#979797979797:#55555555:#DADA49493939:#A5A5C2C26161:#FFFFC6C66D6D:#6D6D9C9CBEBE:#A2A25656C7C7:#6262C1C1A1A1:#FFFFFFFFFFFF'

# Fix ls colours
cd
wget https://raw.githubusercontent.com/seebi/dircolors-solarized/master/dircolors.256dark
mv dircolors.256dark .dircolors
eval `dircolors ~/.dircolors`
cd -
