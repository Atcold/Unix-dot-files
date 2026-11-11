echo 'Installing OpenCode configurations'

mkdir -p $HOME/.config/opencode/plugins
rm -rf $HOME/.config/opencode/plugins/writing-check.js
ln -s $(pwd)/writing-check.js $HOME/.config/opencode/plugins/writing-check.js

rm -rf $HOME/.config/opencode/tui.json
ln -s $(pwd)/tui.json $HOME/.config/opencode/tui.json

echo 'Done.'
