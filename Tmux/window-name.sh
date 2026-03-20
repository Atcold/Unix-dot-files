#!/bin/bash
dir="${1:-$PWD}"
if [ "$dir" = "$HOME" ]; then
    echo "~"
elif root=$(git -C "$dir" rev-parse --show-toplevel 2>/dev/null); then
    basename "$root"
else
    basename "$dir"
fi
