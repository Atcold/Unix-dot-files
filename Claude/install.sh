echo 'Installing Claude configurations'

mkdir -p $HOME/.claude

# Symlink statusline script
rm -rf $HOME/.claude/statusline.sh
ln -s $(pwd)/statusline.sh $HOME/.claude/statusline.sh
chmod +x $(pwd)/statusline.sh

# Configure statusline in settings.json
SETTINGS=$HOME/.claude/settings.json
[ -f "$SETTINGS" ] || echo '{}' > "$SETTINGS"
TMP=$(mktemp)
jq '. + {"statusLine": {"type": "command", "command": "~/.claude/statusline.sh"}}' "$SETTINGS" > "$TMP" && mv "$TMP" "$SETTINGS"

echo 'Done.'
