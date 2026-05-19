#!/bin/bash
# Battery indicator for the tmux status bar (Mac only).
# Draws a 10-segment ◼/◻ bar of the charge level, the percentage,
# and a ↑ when charging (on AC power). Style borrowed from gpakosz/.tmux.
batt=$(pmset -g batt)

pct=$(printf '%s' "$batt" | grep -Eo '[0-9]+%' | head -1)
[ -z "$pct" ] && exit 0
pct=${pct%\%}

length=10
full=$(( (pct * length + 50) / 100 ))

bar=''
for ((i = 0; i < length; i++)); do
    if [ "$i" -lt "$full" ]; then bar+='◼'; else bar+='◻'; fi
done

charging=''
[[ "$batt" == *"'AC Power'"* ]] && charging=' ↑'

echo "$bar ${pct}%${charging}"
