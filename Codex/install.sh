#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "$0")"
source_dir=$PWD
mkdir -p "$HOME/.codex" "$HOME/Work/Scratch/codex-setup"
backup=$(mktemp -d "$HOME/Work/Scratch/codex-setup/install.XXXXXX")

# Preserve each old file, then link its versioned source.
for name in AGENTS.md hooks.json; do
    target="$HOME/.codex/$name"
    if [ -L "$target" ] && [ "$(readlink "$target")" = "$source_dir/$name" ]; then
        continue
    fi
    if [ -e "$target" ] || [ -L "$target" ]; then
        mv "$target" "$backup/$name"
    fi
    ln -s "$source_dir/$name" "$target"
done

echo "Codex settings installed; previous files are in $backup"
