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

Rename the containing files and/or folders adding a dot `.` at the beginning of their name

```bash
for i in * ; do mv $i .$i ; done
```

And then copy them (recursively) to your home folder

```bash
cp -r .??* ~
```
