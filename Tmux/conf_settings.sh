echo 'Installing Tmux configurations'

# installing tmux and tmux-256color terminfo
tic -x tmux.terminfo

# Install config.
rm -rf ~/.tmux.conf
ln -s $(pwd)/tmux.conf $HOME/.tmux.conf

echo 'Done.'
