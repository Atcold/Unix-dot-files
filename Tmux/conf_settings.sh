echo 'Installing Tmux configurations'

# installing tmux and tmux-256color terminfo
mkdir -p $HOME/.terminfo
TERMINFO=$HOME/.terminfo tic -x tmux.terminfo

# Install config.
rm -rf ~/.tmux.conf
ln -s $(pwd)/tmux.conf $HOME/.tmux.conf

# If on Mac, get also Mac specific settings
if [[ $(uname) == 'Darwin' ]]; then
    ln -s $(pwd)/tmux.mac.conf $HOME/.tmux.mac.conf
fi


echo 'Done.'
