echo 'Installing Bash configurations'

rm -rf ~/.bashrc
ln -s $(pwd)/bashrc $HOME/.bashrc

echo 'Done.'
