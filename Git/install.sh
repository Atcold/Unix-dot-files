echo 'Installing Nbdime'

pip install nbdime

echo 'Installing Git configurations'

rm -rf ~/.gitconfig
ln -s $(pwd)/gitconfig $HOME/.gitconfig

echo 'Done.'
