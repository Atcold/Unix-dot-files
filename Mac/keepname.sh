#!/bin/sh

# NYU's BigFix ("NYU IT EE | Rename Computer (macOS)") renames this Mac to its asset tag,
# CIMS-CFAC-AP5, which then shows up in AirDrop and Find My. launchd runs this as root
# whenever the network preferences change (com.atcold.keepname.plist) and puts the name
# back. Each reset is logged: log show --last 1d --predicate 'process == "logger"'
NAME=AlfMAC5

for key in ComputerName LocalHostName; do
    if [ "$(scutil --get $key 2>/dev/null)" != "$NAME" ]; then
        scutil --set $key "$NAME"
        logger -t keepname "$key reset to $NAME"
    fi
done
