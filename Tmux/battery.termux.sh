#!/usr/bin/env bash
# Battery indicator for the tmux status bar (Termux only).
# Draws the same 10-segment ◼/◻ bar, percentage and ↑ as battery.sh on the Mac.
# Android denies an app the sysfs node (/sys/class/power_supply is unreadable),
# the battery service (cmd battery: "Can't find service") and dumpsys, so the
# number comes from the Termux:API companion app. The bridge broadcasts an
# intent and waits for that app to answer, so without the app installed the
# call hangs: the 2 s timeout is what keeps the status bar refreshing, and an
# unanswered call simply shows no battery.
j=$(timeout 2 termux-battery-status 2>/dev/null) || exit 0

pct=$(printf '%s' "$j" | grep -Eo '"level": *[0-9]+' | grep -Eo '[0-9]+')
[ -z "$pct" ] && exit 0

length=10
full=$(( (pct * length + 50) / 100 ))

bar=''
for ((i = 0; i < length; i++)); do
    if [ "$i" -lt "$full" ]; then bar+='◼'; else bar+='◻'; fi
done

charging=''
[[ "${j,,}" == *'"status": "charging"'* ]] && charging=' ↑'

echo "$bar ${pct}%${charging}"
