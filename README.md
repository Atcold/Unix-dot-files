# Unix-dot-files

This repository aims to achieve the highest beauty in terms of Unix configuration dot-files.
This goal is not too ambitious since we are starting from my personal settings (he, he, he :wink:) which could be improved with forking and pull-requesting further updates.


## Setting up your Mac

- Since I'm still using Bash (and I'm not moving to `zsh`) we should tell Mac to revert to the old shell. \
  `System Settings…` / `Users & Groups` / (`^-click`) `Advanced options…` / `Login shell` choose `/bin/bash`.
- Install [`brew`](https://brew.sh/).

## Installation instructions

Clone the repository

```bash
git clone https://github.com/Atcold/Unix-dot-files.git
```

Then, after having chosen the subfolder of interest (say for example [`Vim`](https://github.com/Atcold/Unix-dot-files/tree/master/Vim))

```bash
cd Unix-dot-files
cd Vim
./install.sh
```

Don't forget to backup your previous configuration, since it will be overwritten.

Installation is required once only. Then you will simply need to pull in any new update.


# Better colours

Let's give to our *Unix* some pretty colours!


## Ubuntu

`cd` into `Ubuntu` and run `install.sh`. It will take care of everything.  
If you'd like only to fix the colours, then run `Ubuntu/fix_colours.sh` only.


## MacOS

In order to customise your *Terminal* application, you can simply import the file `Mac-Terminal/Monokai.terminal` and set it as default.


# Substituting <kbd>Caps Lock</kbd> with <kbd>Ctrl</kbd>

Since you will never use your <kbd>Caps Lock</kbd> key, let's get another <kbd>Ctrl</kbd>, handy for our left pinkie when writing code in *Vim* within *Tmux*.
(Remember that <kbd>Esc</kbd> can be obtained by typing `^[`, that is <kbd>Ctrl</kbd>-<kbd>[</kbd>.)


## Ubuntu

In `/etc/default/keyboard` we ought to change something, so

```bash
sudo vim /etc/default/keyboard +/XKBOPTIONS
```

and let's set

```lua
XKBOPTIONS="ctrl:nocaps,compose:ralt"
```

> To exchange the position of <kbd>Caps Lock</kbd> and <kbd>Ctrl</kbd>, instead
> ```lua
> XKBOPTIONS="ctrl:swapcaps,compose:ralt"
> ```

and, therefore, run

```bash
sudo dpkg-reconfigure keyboard-configuration
```

We have also mapped the <kbd>AltGr</kbd> (the <kbd>Alt</kbd> on the right) to the *compose-key*, so that we can write accented letters in Ubuntu.
For example, we can type an *È* by typing <kbd>AltGr</kbd>-<kbd>`</kbd> <kbd>Shift</kbd>-<kbd>E</kbd>.
We can type an *é* with <kbd>AltGr</kbd>-<kbd>'</kbd> <kbd>E</kbd>.


## MacOS

`System Settings…` / `Keyboard` / `Keyboard Shortcuts…` / `Modifier Keys` / `Caps Lock` > choose `^ Control`.
