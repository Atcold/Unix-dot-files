echo 'Installing Tmux configurations'

# installing tmux and tmux-256color terminfo
mkdir -p $HOME/.terminfo
TERMINFO=$HOME/.terminfo tic -x tmux.terminfo

# Install config.
rm -rf ~/.tmux.conf
ln -s $(pwd)/tmux.conf $HOME/.tmux.conf

# Install scripts.
mkdir -p $HOME/.tmux
ln -sf $(pwd)/window-name.sh $HOME/.tmux/window-name.sh

# If on Mac, get also Mac specific settings
if [[ $(uname) == 'Darwin' ]]; then
    brew install tmux
    rm -rf ~/.tmux.mac.conf
    ln -s $(pwd)/tmux.mac.conf $HOME/.tmux.mac.conf
    ln -sf $(pwd)/battery.sh $HOME/.tmux/battery.sh
fi

echo 'Done.'
echo
echo 'NOTE: a running tmux server caches the old terminfo. To apply the cursor-shape'
echo 'fix (block no longer sticks after leaving Neovim), detach/save your work then:'
echo '  tmux kill-server   # then reattach to pick up the freshly tic-ed terminfo'
