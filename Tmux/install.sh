echo 'Installing Tmux configurations'

rm -rf ~/.tmux.conf
ln -s $(pwd)/tmux.conf $HOME/.tmux.conf

echo 'Done.'
