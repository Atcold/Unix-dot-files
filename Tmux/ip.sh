#!/bin/bash
# The local and public IPv4 addresses for tmux's status bar: 'local → public'.
# The local one is the address of the interface that holds the default route. The public one
# comes from icanhazip.com, at most once every 5 minutes; tmux reads the cached copy in between.

if [[ $(uname) == Darwin ]]; then
    local_ip=$(ipconfig getifaddr "$(route -n get default 2>/dev/null | awk '/interface:/ {print $2}')" 2>/dev/null)
else
    local_ip=$(ip route get 1.1.1.1 2>/dev/null | awk '{for (i = 1; i < NF; i++) if ($i == "src") print $(i + 1)}')
fi

cache=${XDG_CACHE_HOME:-$HOME/.cache}/tmux-public-ip
mkdir -p "${cache%/*}"
age=$(( $(date +%s) - $(stat -c %Y "$cache" 2>/dev/null || stat -f %m "$cache" 2>/dev/null || echo 0) ))
if (( age > 300 )); then
    touch "$cache"   # one fetch at a time, even if it hangs
    ( ip=$(curl -4 -s -m 5 icanhazip.com) && [[ $ip =~ ^[0-9.]+$ ]] && echo "$ip" > "$cache" ) &
fi
public_ip=$(cat "$cache" 2>/dev/null)

echo "${local_ip:-offline} → ${public_ip:-?}"
