# Unix-dot-files

This repository aims to achieve the highest beauty in terms of Unix configuration dot-files.
This goal is not too ambitious since we are starting from my personal settings (he, he, he :wink:) which could be improved with forking and pull-requesting further updates.

## "Installation" instructions

Clone the repository

```bash
git clone git@github.com:Atcold/Unix-dot-files.git
```

Then, after having chosen the subfolder of interest (say for example [`Vim`](https://github.com/Atcold/Unix-dot-files/tree/master/Vim))

```bash
cd Unix-dot-files
cd Vim
```

Copy the containing files and/or folders, adding a dot `.` at the beginning of their name, to your home folder `~`

```bash
for i in * ; do cp -r $i ~/.$i ; done
```

# Solarized colour scheme

Let's give to our *Unix* some pretty colours!

## Ubuntu

The colour settings for [*Ubuntu*'s *Terminal*](https://help.ubuntu.com/community/UsingTheTerminal) and [*Guake*](http://guake.org/) (full screen terminal) can be tweaked in order to mirror the awesome [*Solarized*](http://ethanschoonover.com/solarized) project.

### `ls` folders and files

```bash
cd
wget https://raw.githubusercontent.com/seebi/dircolors-solarized/master/dircolors.256dark
mv dircolors.256dark .dircolors
eval `dircolors ~/.dircolors`
cd -
```

### Ubuntu's Terminal

```bash
gconftool-2 -s -t bool   /apps/gnome-terminal/profiles/Default/use_theme_background false
gconftool-2 -s -t bool   /apps/gnome-terminal/profiles/Default/use_theme_colors false
gconftool-2 -s -t string /apps/gnome-terminal/profiles/Default/background_color '#1c1c1c1c1c1c'
gconftool-2 -s -t string /apps/gnome-terminal/profiles/Default/foreground_color '#808080808080'
gconftool-2 -s -t string /apps/gnome-terminal/profiles/Default/palette          '#262626262626:#DCDC32322F2F:#858599990000:#B5B589890000:#26268B8BD2D2:#D3D336368282:#2A2AA1A19898:#E4E4E4E4E4E4:#000000000000:#CBCB4B4B1616:#585858585858:#626262626262:#808080808080:#6C6C7171C4C4:#8A8A8A8A8A8A:#FFFFFFFFD7D7'
```

### Guake

```bash
gconftool-2 -s -t string /apps/guake/style/background/color '#1c1c1c1c1c1c'
gconftool-2 -s -t string /apps/guake/style/font/color       '#808080808080'
gconftool-2 -s -t string /apps/guake/style/font/palette     '#262626262626:#DCDC32322F2F:#858599990000:#B5B589890000:#26268B8BD2D2:#D3D336368282:#2A2AA1A19898:#E4E4E4E4E4E4:#000000000000:#CBCB4B4B1616:#585858585858:#626262626262:#808080808080:#6C6C7171C4C4:#8A8A8A8A8A8A:#FFFFFFFFD7D7'
```

# Substituting `Caps Lock` with `Ctrl`

Since you will never use you `Caps Lock` key, let's get another `Ctrl` available, handy for our left pinkie when writing code in *Vim*.

## Ubuntu

In `/etc/default/keyboard` we ought to change something, so

```bash
sudo vim /etc/default/keyboard +/XKBOPTIONS
```

and let's set

```lua
XKBOPTIONS="ctrl:nocaps"
```

> To exchange the position of `Caps Lock` and `Ctrl`, instead
> ```lua
> XKBOPTIONS="ctrl:swapcaps"
> ```

and, therefore, run

```bash
sudo dpkg-reconfigure keyboard-configuration
```
