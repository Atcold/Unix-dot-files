#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "$0")"
source_dir=$PWD
mkdir -p "$HOME/.claude" "$HOME/Work/Scratch/claude-setup"
backup=$(mktemp -d "$HOME/Work/Scratch/claude-setup/install.XXXXXX")
settings="$HOME/.claude/settings.json"

# Prepare the JSON update before replacing any links.
if [ -f "$settings" ]; then
    cp -p "$settings" "$backup/settings.json"
else
    echo '{}' > "$backup/settings.json"
fi
# The keys in settings.base.json are mine and win; the app keeps every other key.
jq -s '.[0] * .[1]' "$backup/settings.json" settings.base.json > "$backup/settings.new.json"

# Preserve each old file or folder, then link its versioned source.
for name in CLAUDE.md rules hooks statusline.sh; do
    target="$HOME/.claude/$name"
    if [ -L "$target" ] && [ "$(readlink "$target")" = "$source_dir/$name" ]; then
        continue
    fi
    if [ -e "$target" ] || [ -L "$target" ]; then
        mv "$target" "$backup/$name"
    fi
    ln -s "$source_dir/$name" "$target"
done

cat "$backup/settings.new.json" > "$settings"
echo "Claude settings installed; previous files are in $backup"
