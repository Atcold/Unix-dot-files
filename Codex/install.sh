#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "$0")"
source_file="$PWD/AGENTS.md"
target="$HOME/.codex/AGENTS.md"
mkdir -p "$HOME/.codex"

if [ -L "$target" ] && [ "$(readlink "$target")" = "$source_file" ]; then
    echo 'Codex instructions are already linked.'
    exit 0
fi
if [ -e "$target" ] || [ -L "$target" ]; then
    mkdir -p "$HOME/Work/Scratch/codex-setup"
    backup=$(mktemp -d "$HOME/Work/Scratch/codex-setup/install.XXXXXX")
    mv "$target" "$backup/AGENTS.md"
    echo "Previous instructions are in $backup"
fi
ln -s "$source_file" "$target"
echo 'Codex instructions installed.'
