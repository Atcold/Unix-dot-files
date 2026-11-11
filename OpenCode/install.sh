echo 'Installing OpenCode configurations'

mkdir -p $HOME/.config/opencode/plugins
rm -rf $HOME/.config/opencode/plugins/writing-check.js
ln -s $(pwd)/writing-check.js $HOME/.config/opencode/plugins/writing-check.js

echo 'Done.'
