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

In order to customise your *Terminal* (or *TotalTerminal*) application, you can simply import the file `Mac-Terminal/Pastel.terminal` and set it as default.


# Substituting `<Caps Lock>` with `<Ctrl>`

Since you will never use you `<Caps Lock>` key, let's get another `<Ctrl>` available, handy for our left pinkie when writing code in *Vim* within *Tmux*. (Remember that `<Esc>` can be obtained by typing `^[`, that is `<Ctrl>`-`[`.)


## Ubuntu

In `/etc/default/keyboard` we ought to change something, so

```bash
sudo vim /etc/default/keyboard +/XKBOPTIONS
```

and let's set

```lua
XKBOPTIONS="ctrl:nocaps"
```

> To exchange the position of `<Caps Lock>` and `<Ctrl>`, instead
> ```lua
> XKBOPTIONS="ctrl:swapcaps"
> ```

and, therefore, run

```bash
sudo dpkg-reconfigure keyboard-configuration
```


## MacOS

`System Preferences...` / `Keyboard` / `Modifier Keys...` / `Caps Lock` > choose `^ Control`.
