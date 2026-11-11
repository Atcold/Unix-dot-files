# mpv radio

`radio` plays the stations in `radio.m3u`; the alias is in [`Bash/bashrc`](../Bash/bashrc). It uses the `radio` profile in `mpv.conf`, which hides mpv's own messages and loads `radio.lua`. The script clears the screen once, lists the keys, prints each station's name in block letters in its own colour with the stream's format, bitrate, sample rate, and channels underneath, and adds a line for each new piece. A piece that plays for 30 s on the same station is appended to `~/.local/share/radio/log.tsv`.

From this folder, `./install.sh` links `mpv.conf` into `~/.config/mpv/`.
