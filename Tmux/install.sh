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
    brew install tmux reattach-to-user-namespace
    rm -rf ~/.tmux.mac.conf
    ln -s $(pwd)/tmux.mac.conf $HOME/.tmux.mac.conf
    brew install reattach-to-user-namespace
fi

echo 'Done.'
