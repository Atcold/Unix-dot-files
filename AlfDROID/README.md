# AlfDROID

Config and services for the OnePlus 6 server (see the `alfdroid` lesson in learning-with-claude). Built for Termux: `pkg install ffmpeg icecast python` first.

## `radio-server.py`

Serves the stations in `Mpv/radio.m3u` as icecast mounts on the phone, so a listener plays one plain URL per station instead of each device chasing the station's own stream. One station is on at a time: its relay is one ffmpeg that decodes the upstream and republishes it as a uniform 128k MP3 mount at `http://<host>:8000/<slug>.mp3`, restarted automatically when the station's stream drops; switching stations stops the previous relay so the phone never streams more upstream than it plays. `radio-server.py up` starts icecast, the relay and a page at `http://<host>:8080/`, where tapping a station row switches to it and plays it in the page's own player (bottom bar: ⏮ ▶ ⏭, volume, piece title); `start`, `stop`, `status` and `down` drive the same from the shell, naming stations by slug, number or a word of the name. Add `http://<host>:8080/radio.m3u` once to a player such as Evermusic and it lists whatever is currently on. What plays goes to `~/.local/share/radio/log.tsv` in the same shape `Mpv/radio.lua` logs on the Macs, once a piece has held for 30 s with a listener connected.
