# Radio

My stations, from one folder: `radio` plays them in the terminal on the Macs through mpv, and AlfDROID relays and records them on the tailnet, so the iPhone listens three minutes behind live out of the droid's tape and rides out a subway run on its buffer. Both read the same titles and write the same log, because the rules that decide what a piece is live in one file.

`radio` alone, or `radio mpv`, prints a header per station with its name in block letters in its own colour and the stream's format, bitrate, sample rate and channels underneath, then a line for each piece. Keys: `1-8` and letters jump to a station, `<` and `>` step, `9` and `0` set the volume, `c` opens the channels menu with what each station is playing now, `space` pauses, `q` quits. A piece that plays 30 s on one station goes to `~/.local/share/radio/log.tsv` as date, time, station and piece.

## Files

- **radio**: the command on the Macs. Bare, it plays; `radio status`, `watch`, `log`, `on`, `off`, `start`, `stop`, `up`, `down`, `restart`, `deploy` and `logos` look after the droid's service, and `radio help` lists them.
- **radio.m3u**: the stations, in the order the codes are handed out.
- **radio.lua**: the mpv script that owns the pane: header, piece lines, colours, keys, and the log.
- **mpv.conf**: the `radio` profile, which hides mpv's own messages and loads the script at `~~/radio.lua`.
- **radio_core.py**: the shared rules, run by the Mac script and imported by the server: it reads the icy `StreamTitle` chunks, undoes the encoding some stations double-apply, drops a station's own announcement between pieces, and decides when a piece has already been written.
- **radio-server.py**: the AlfDROID service: one ffmpeg per station re-encoding it to 128 kbit/s MP3 for icecast on :8001 and for a five-minute tape in RAM, a supervisor that restarts it on a drop, and the page and its streams on :8080. Safari plays a station as HLS, 6 s segments cut from the tape, starting three minutes back and buffering up to live; other browsers stream the tape directly. Each station's titles are kept with the time they arrived, and every page reports where it is listening, so the page, the lock screen and the droid's log name the piece the listener hears, three minutes behind the live title. Each piece's cover comes from Apple's iTunes search and stays in RAM while the piece is on the tape; the station logo stands in when Apple has none. The recording switch starts and stops every relay, which also sleep fifteen minutes after the last listener.
- **radio-page.html**: the page, read fresh on every request, so a page change ships with `radio deploy` and no restart. In debug mode its bottom buttons wrap into rows of three: the recording switch, `⇣ refill` (throw away the phone's buffer and download a fresh one from the same spot), `page` (load the page again), and debug off.
- **logos-dark**: draws dark versions of the bright station logos and copies them to the droid; `radio logos` runs it.
- **boot/radio**: the Termux:Boot script that brings the service up when the droid starts, together with AlfRADIO: a second Tailscale, compiled in Termux with its Go and run without root, whose Funnel publishes the page at `https://alfradio.<tailnet>.ts.net/`. A request from the internet needs the key in `~/.local/share/radio/key`, given once as `?k=` and kept by the browser as a cookie; requests on the tailnet need nothing.
- **install.sh**: `./install.sh mac`, `droid` or `all`, with `--boot` for the droid's boot script and `-y` for a scripted run. With no role it asks.

## Settings

`$RADIO_M3U` names a playlist elsewhere; otherwise the Macs take it from mpv's config folder and the droid from this one. `$RADIO_CORE` points at the shared rules if they are not next to the script. State, logs and station logos live under `~/.local/share/radio/` on every machine, so a Mac and the droid each keep their own listening history.

`python3 radio_core.py --selftest` checks the rules against titles the stations really send, and runs at the end of every install. Without python3 the Mac still plays: the script says so once and shows titles as they come.

The droid itself, from a OnePlus 6 running Debian in Termux, is the `alfdroid` lesson in learning-with-claude.

The source folder is `Scripts/radio/` in the settings repository. The command and mpv configuration link to this folder; the server’s boot entry uses the same location.
