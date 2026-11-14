#!/usr/bin/env bash
# Install the radio on one of my machines, from this folder.
#
#   ./install.sh mac      mpv: link the profile, the script, the playlist and the core
#   ./install.sh phone    Termux: ffmpeg, icecast and python, and the server on the PATH
#   ./install.sh all      both, for a machine that plays and serves
#   ./install.sh --boot   with phone: also start the service when the phone boots
#   ./install.sh -y       no questions, so a script can run it (it then needs a role)
#
# With no role it asks, offering what uname and $PREFIX suggest. A run with no terminal to
# answer on gets the usage and a non-zero exit, so a pipeline never sits on a question.

here="$(pwd)"
ROLE="" BOOT=no YES=no

usage() {
  sed -n '4,12p' "$0" | sed 's/^# \{0,1\}//'
}

guess() {
  case "$(uname)" in
    Darwin) echo mac ;;
    Linux) case "${PREFIX:-}" in *com.termux*) echo phone ;; *) echo mac ;; esac ;;
    *) echo mac ;;
  esac
}

for a in "$@"; do
  case "$a" in
    mac | phone | all)
      if [ -n "$ROLE" ]; then echo "one role at a time"; exit 2; fi
      ROLE="$a" ;;
    --boot) BOOT=yes ;;
    -y | --yes) YES=yes ;;
    -h | --help) usage; exit 0 ;;
    *) echo "unknown argument: $a"; usage; exit 2 ;;
  esac
done

if [ -z "$ROLE" ]; then
  default="$(guess)"
  if [ "$YES" = yes ] || [ ! -t 0 ]; then
    echo "name the machine to install for: mac, phone or all"; exit 2
  fi
  printf 'What should I install here? [mac/phone/all] (%s): ' "$default"
  read -r ROLE
  ROLE="${ROLE:-$default}"
fi

if [ "$ROLE" = mac ] || [ "$ROLE" = all ]; then
  echo 'Installing the radio in mpv'
  mkdir -p "$HOME/.config/mpv"
  for f in mpv.conf radio.lua radio.m3u radio_core.py; do
    rm -rf "$HOME/.config/mpv/$f"
    ln -s "$here/$f" "$HOME/.config/mpv/$f"
  done
  echo 'Done. mpv finds them all at ~~/, so the folder name does not matter.'
fi

if [ "$ROLE" = phone ] || [ "$ROLE" = all ]; then
  echo 'Installing the packages the relays need'
  pkg install -y ffmpeg icecast python

  echo 'Installing the radio server'
  BINDIR="${PREFIX:-$HOME/.local}/bin"
  mkdir -p "$BINDIR"
  rm -f "$BINDIR/radio-server.py"
  ln -s "$here/radio-server.py" "$BINDIR/radio-server.py"
  echo "Done. radio-server.py up starts icecast, the relays and the page on port 8080."

  if [ "$BOOT" = yes ]; then
    echo 'Installing the boot script'
    mkdir -p "$HOME/.termux/boot"
    rm -f "$HOME/.termux/boot/radio"
    cp "$here/boot/radio" "$HOME/.termux/boot/radio"   # a copy: Termux:Boot runs what is there
    chmod +x "$HOME/.termux/boot/radio"
    echo 'Done. Open Termux:Boot once to let it run at the next start.'
  fi
fi

python3 "$here/radio_core.py" --selftest
