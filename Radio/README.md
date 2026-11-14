# Radio

My stations, from one folder: `radio` plays them in the terminal on the Macs through mpv, and AlfDROID relays them on the tailnet through icecast so a listener plays one plain MP3 URL per station. Both read the same titles and write the same log, because the rules that decide what a piece is live in one file.

`radio` prints a header per station with its name in block letters in its own colour and the stream's format, bitrate, sample rate and channels underneath, then a line for each piece. Keys: `1-8` and letters jump to a station, `<` and `>` step, `9` and `0` set the volume, `c` opens the channels menu with what each station is playing now, `space` pauses, `q` quits. A piece that plays 30 s on one station goes to `~/.local/share/radio/log.tsv` as date, time, station and piece.

## Files

- **radio.m3u**: the stations, in the order the codes are handed out.
- **radio.lua**: the mpv script that owns the pane: header, piece lines, colours, keys, and the log.
- **mpv.conf**: the `radio` profile, which hides mpv's own messages and loads the script at `~~/radio.lua`.
- **radio_core.py**: the shared rules, run by the Mac script and imported by the server: it reads the icy `StreamTitle` chunks, undoes the encoding some stations double-apply, drops a station's own announcement between pieces, and decides when a piece has already been written.
- **radio-server.py**: the AlfDROID service: one ffmpeg per station republishing it as a 128k MP3 mount, a supervisor that restarts it on a drop, and a page on port 8080 to switch stations and copy mount URLs into a player such as Evermusic.
- **boot/radio**: the Termux:Boot script that brings the service up when the phone starts.
- **install.sh**: `./install.sh mac`, `phone` or `all`, with `--boot` for the phone's boot script and `-y` for a scripted run. With no role it asks.

## Settings

`$RADIO_M3U` names a playlist elsewhere; otherwise the Macs take it from mpv's config folder and the phone from this one. `$RADIO_CORE` points at the shared rules if they are not next to the script. State, logs and station logos live under `~/.local/share/radio/` on every machine, so a Mac and the phone each keep their own listening history.

`python3 radio_core.py --selftest` checks the rules against titles the stations really send, and runs at the end of every install. Without python3 the Mac still plays: the script says so once and shows titles as they come.

The phone itself, from a OnePlus 6 running Debian in Termux, is the `alfdroid` lesson in learning-with-claude.
