#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "$0")"
source_dir=$PWD
mkdir -p "$HOME/.claude" "$HOME/Work/Scratch/claude-setup"
backup=$(mktemp -d "$HOME/Work/Scratch/claude-setup/install.XXXXXX")

# Preserve each old file or folder, then link its versioned source.
for name in CLAUDE.md rules hooks statusline.sh settings.json; do
    target="$HOME/.claude/$name"
    if [ -L "$target" ] && [ "$(readlink "$target")" = "$source_dir/$name" ]; then
        continue
    fi
    if [ -e "$target" ] || [ -L "$target" ]; then
        mv "$target" "$backup/$name"
    fi
    ln -s "$source_dir/$name" "$target"
done

echo "Claude settings installed; previous files are in $backup"
