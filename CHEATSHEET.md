# My Unix shortcuts and tips

 - [Bash](#bash)
 - [Git](#git)
 - [Vim](#vim)
    - [Vimdidd](#vimdiff)
 - [Tmux](#tmux)
 - [Mac](#mac)
 - [FFmpeg](#ffmpeg)
 - [LaTeX](#latex)
 - [Python tools](#python-tools)
 - [Networking](#networking)


## Bash

### List fields in `awk`'s first matching like
```bash
awk '/<pattern>/{for (i = 1; i <= NF; ++i) print i, $i; exit}' <fileName>
```

### Find net dev, address, gateway, mask and DNS
To find out your current network devices' status
```bash
nmcli device status
```
To find out all the useful numbers about our `<net dev>` (say, `eth0`)
```bash
nmcli device show <net dev> | grep -e IP4.DNS -e IP4.GATEWAY -e IP4.ADDRESS
```
The `IP4.ADDRESS[1]` field carries information about the subnet mask too.
If we prefer a more extended version
```bash
ifconfig <net dev> | awk '/Mask:/{print $4}'
```

### Use Jupyter notebook remotely
After having run `jupyter notebook` on the remote machine `R`, keep track of the remote port `R_port` (*e.g.* `8888`) and *Jupyter* token `J_token` (*e.g.* `a1b2c3d4`).
On your local machine `L` bind a `L_port` (*e.g.* `9000`) to where *Jupyter* is running at on `R`.
```bash
l@L ~ $ ssh -NfL L_port:localhost:R_port r@R
```
Finally, on `L`, go to `http://localhost:L_port/?token=J_token`, and you should be able to use the notebook remotely.
To close the `ssh` tunnel, you can `ps aux | grep ssh`, take note of `ssh_PID` and `kill ssh_PID`.

### Display a CSV file
```bash
column -ts, <fileName.csv>
```
Or, from *Vim*
```vim
:read !column -ts, <fileName.csv>
```

### How to list disks and partitions
All users:
```bash
sudo lsblk -o NAME,FSTYPE,SIZE,MOUNTPOINT,LABEL
```
Current user (`FSTYPE` and `LABEL` available only with `sudo`):
```bash
lsblk -o NAME,SIZE,MOUNTPOINT
```

### Automount a device (like *Nautilus*)
```bash
udisks --mount <deviceName>
```
or
```
udisksctl mount -b <deviceName>
```

### Searching a string within a directory
```bash
grep -Inri "<keyword to search for>" .
```

### Show all files' name and content
```bash
find . -type f -exec sh -c "echo '{}'; cat {}; echo '\n'" \;
```

### Show how many files each folder contains
```bash
find . -maxdepth 1 -type d -exec sh -c "echo {} \`ls {} | wc -l;\`" \;
```
or, better
```bash
ls -d */ | while read dir; do
    echo "$dir: $(ls $dir | wc -l)"
done
```

### Groups

#### List groups for user
```bash
groups <user>
```

> #### Add new group
> ```bash
> groupadd <group>
> ```

#### Add user to (secondary) group or to another user's user-group
```bash
usermod -aG <group> <user>
```
or
```bash
adduser <user> <group>
```

#### Group belongness inheritance
```bash
chmod g+s <folder>
```
### Accessing permission for folders

```bash
find <folder> -type d -exec chmod g+s {} +
```

### Ssh without password
```bash
a@A ~ $ ssh-keygen -t rsa
a@A ~ $ ssh b@B mkdir -p .ssh
a@A ~ $ cat ~/.ssh/id_rsa.pub | ssh b@B 'cat >> .ssh/authorized_keys'
a@A ~ $ ssh b@B
```

### Killing a process
```bash
ps -a | grep <program to kill>
kill 9 <ID of program to kill>
```

### Checking size
```bash
du -chs *
```

### Check free space
```bash
df -h [<path>]
```

### Get info on process (RAM, time)
```bash
/usr/bin/time -v <running instruction>
```

### Tar and untar
```bash
tar -czf myTar.tar.gz <files>
tar -xf myTar.tar.gz
```
Add `-v` for verbose output.

### Logout users
```bash
who -u
kill "pid"
```

### Ubuntu packages

#### List packages `apt` knows about, starting with `<packagePrefix>`
```bash
apt-cache pkgnames <packagePrefix>
```
To know more, *e.g.* whether the packages are installed,
```bash
apt list <packagePrefix>*
```

#### Know what a package installs
```bash
dpkg -L <packageName>
```

#### Discover what shared objects are used
```bash
lld <library/executable>
```


## Git

### Reset HEAD to origin/master
```bash
git fetch origin
git reset --hard origin/master
```

### Reset repo to HEAD
```bash
git reset --hard
```

### Tracking history
```bash
git log --decorate --graph -p -- fileName
git blame fileName
```

### Remove untracked files (and directories) (and ignored files `-x`)
```bash
git clean -df
```
If the repo has sumbodules, then
```bash
git submodule foreach git clean -df
```

### Full diff, word by word
```bash
git diff --word-diff
```
or, on older versions,
```bash
git diff --color-words -U9999999
```

### Pruning on-the-fly
```bash
git fetch -p
```

### Forget/remember to track files
```bash
git update-index --assume-unchanged <file>
git update-index --no-assume-unchanged <file>
```
For example, to loose track of the status of your notebook you can `git update-index --assume-unchanged notebook/*.ipynb`.
To list all assumed unchanged files type
```bash
git ls-files -v | egrep '^h'
```

### Follow history of a file (even if renamed)
```bash
git log --follow <fileName>
```

### Locally ignore files
Edit `.git/info/exclude` as you would for `.gitignore`.

### The `diff` comand
 - `git diff`: what you can still add to the index;
 - `git diff --cached`: what you have on the index *vs.* what's committed;
 - `git diff HEAD`: everything that has not been committed (working dir + index);
 - `git diff <commit>`: working tree − `<commit>`;
 - `git diff --cached <commit>`: index − `<commit>`;
 - `git diff <commitFrom> <commitTo>`: `<commitTo>` − `<commitFrom`> (chronological order!);
 - `git diff <commitFrom>..<commitTo>`: same;
 - `git diff <commitFrom> <commmitTo> --stat`: summary of changes;
 - `git diff <commitFrom> <commmitTo> -- <filename>`: changes per `<filename>` only.

### `add`, `commit`, `reset` and `checkout` commands
  - `git add <filename>`: copies a file from the working dir to the index;
  - `git commit ...`: copies a file from the index to (a new) HEAD;
  - `git reset <filename>`: copies a file from HEAD to the index (*i.e.* removes file from index);
  - `git checkout <filename>`: copies a file from the index to the working dir (*i.e.* removes local changes);
  - `git checkout  -- '*.c'`: copies all C files (even removed one) from the index to the working dir.


## Vim

### List all recognised syntaxes
```vimscript
:setfiletype CTRL-D
```

### Removing trailing whitespaces
```vimscript
:%s/\s\+$
```

### Pasting yanked text while in insert mode
```vimscript
<c>-R 0
```

### Exploring file's location / split and explore
```vimscript
:Ex
:Sex
```

### Show command and search history
```vimscript
q:
q/
```

### Find within a project (excluding binaries)
```vimscript
:grep -rI "<text>" .
:cw
```

> ### Vimdiff
> 
> #### Sourcing correct file during conflict
> ```
> :diffg RE/BA/LO
> ```
> 
> #### Previous and next conflict
> ```
> [c
> ]c
> ```

## Tmux

### Move windows around
```
move-window -t <nb>
```

### Attach and disattach others
```
tmux attach -d
```


## Mac

### Show and hide hidden files in *Finder*
```
defaults write com.apple.finder AppleShowAllFiles TRUE
defaults write com.apple.finder AppleShowAllFiles FALSE
killall Finder
```

## FFmpeg

### Get a video out of images
```
ffmpeg -framerate 30 -i <path>/%03d.png -pix_fmt yuv420p -filter:v "crop=floor(iw/2)*2:floor(ih/2)*2" video.mp4
```
 
## LaTeX

### Documentation
```
texdoc <package name>
```

### Update distribution
```
tlmgr update --all
```


## Python tools

Command-line Python tools are installed with `pipx` (see `Mac/install.sh`, `Vim/install.sh`, `Git/install.sh`): each gets its own environment, and its commands land in `~/.local/bin`.

### List what is installed
```bash
pipx list          # each package, with a `- <command>` line per command it provides
pipx list --short  # package names and versions only
```


## Networking

### Tailnet: which path the traffic takes
```bash
tailscale status          # one line per machine; last column: direct <address>, relay "<city>", -, or offline
tailscale ping alfspark   # pings until the path is direct; `via DERP(<city>)` = relay, `via <address>` = direct
tailscale netcheck        # this machine's public address and its distance to each relay
```
On the Mac, `tailscale` lives inside the app: *Settings* → *CLI integration* puts it on the `PATH`.

### List devices on the LAN
```bash
ip neigh       # Linux: LAN devices this machine has talked to lately
```
For every device, see the router's list (`http://192.168.4.1`) or scan with `nmap -sn <network>/<prefix>`.

### Kasa smart plug
```bash
kasa --alias AlfSPARK state  # find the plug by name, whatever its address; shows power in W
kasa --alias AlfSPARK off
kasa --alias AlfSPARK on
```
