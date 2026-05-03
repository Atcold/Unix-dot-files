#!/usr/bin/env bash

# `set -u` -> abort if we read an unset variable. Catches typos like $UR
# instead of $URL. We don't add `set -e` because the inner loop intentionally
# checks exit codes manually.
set -u

# ANSI colours for status messages. `\033[Xm` is an escape sequence the
# terminal interprets — 31 = red, 32 = green, 33 = yellow, 36 = cyan,
# 1 = bold, 2 = dim, 0 = reset to default. Codes can be combined with `;`,
# e.g. `\033[1;31m` for bold red.
# `$'...'` is bash's ANSI-C quoting: it turns the literal `\033` into a
# real ESC byte (you can't do that with plain "...").
# `[ -t 1 ]` / `[ -t 2 ]` are true only when stdout/stderr is a terminal.
# We enable colours if either is — otherwise piping the output to a file
# would pepper the log with raw escape codes.
if [ -t 1 ] || [ -t 2 ]; then
  RED=$'\033[31m'
  GREEN=$'\033[32m'
  YELLOW=$'\033[33m'
  CYAN=$'\033[36m'
  BOLD=$'\033[1m'
  DIM=$'\033[2m'
  RESET=$'\033[0m'
else
  RED= GREEN= YELLOW= CYAN= BOLD= DIM= RESET=
fi

# $# is the number of positional arguments. Need at least the URL.
# When called with none, print a description + usage line to stderr (`>&2`).
# Convention in the usage line: required <args> in yellow, optional [args] dim.
# A heredoc (`cat <<EOF ... EOF`) lets us write the multi-line block as
# plain text while still expanding the colour variables and `$0`.
if [ $# -lt 1 ]; then
  cat >&2 <<EOF
Resumable wget with stall detection. Re-launches wget if the file size
hasn't grown for ~30 s, so a silently-frozen download (server stops
sending bytes but keeps the connection open) doesn't hang forever.

${BOLD}Usage:${RESET} ${CYAN}$0${RESET} ${YELLOW}<url>${RESET} ${DIM}[output]${RESET}

If ${DIM}[output]${RESET} is omitted, the filename is derived from the URL
(query string stripped).
EOF
  exit 1
fi

URL=$1
# ${2:-DEFAULT} -> use $2 if set, otherwise DEFAULT.
# ${URL%%[?&]*} strips the longest trailing match of `[?&]*`, i.e. the
# query string (everything from the first `?` or `&` onward), leaving the
# bare URL path. `basename` then gives just the filename.
# Example: .../foo.zip?api-key=... -> foo.zip
OUT=${2:-$(basename "${URL%%[?&]*}")}

# Outer loop: keep retrying until wget exits cleanly (exit 0).
while true; do
  # `wget -c` resumes a partial download (continues from existing $OUT).
  # `-O $OUT` writes to a fixed filename so resume works across restarts.
  # `-t 20` retries up to 20 times on transient network errors.
  # Trailing `&` runs wget in the background so this script can babysit it.
  wget -c -O "$OUT" -t 20 "$URL" &
  # `$!` is the PID of the most recently backgrounded process.
  WGET_PID=$!

  LAST_SIZE=0    # file size at the previous check
  IDLE_COUNT=0   # consecutive checks where size didn't change

  # `kill -0 PID` doesn't actually kill — it just tests whether the
  # process exists (and we have permission to signal it). Loop while
  # wget is still running.
  while kill -0 "$WGET_PID" 2>/dev/null; do
    sleep 10

    if [ -f "$OUT" ]; then
      # Portable byte count: `wc -c < file` works on macOS and Linux.
      # (macOS `stat -f%z` and Linux `stat -c%s` are mutually incompatible.)
      # `tr -d ' '` strips the leading whitespace BSD `wc` likes to add.
      SIZE=$(wc -c < "$OUT" 2>/dev/null | tr -d ' ')

      # ${SIZE:-0} -> fall back to 0 if SIZE is empty (e.g. wc raced the file).
      if [ "${SIZE:-0}" -eq "$LAST_SIZE" ]; then
        IDLE_COUNT=$((IDLE_COUNT + 1))
      else
        IDLE_COUNT=0
        LAST_SIZE=$SIZE
      fi

      # 3 idle checks * 10 s sleep = ~30 s of zero progress -> restart.
      if [ "$IDLE_COUNT" -ge 3 ]; then
        echo
        echo " > ${RED}Stall detected. Restarting wget...${RESET}"
        kill "$WGET_PID"
        break
      fi
    fi
  done

  # `wait PID` blocks until that background job ends and yields its
  # exit code via `$?`. Needed even after we kill it, to reap the
  # zombie and get a real status.
  wait "$WGET_PID"
  EXIT_CODE=$?

  if [ "$EXIT_CODE" -eq 0 ]; then
    echo " > ${GREEN}Download completed. Exiting.${RESET}"
    break
  fi

  # Brief pause before relaunching, so we don't hammer the server.
  sleep 5
done
