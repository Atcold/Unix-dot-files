echo 'Installing Nbdime'

pipx install nbdime  # pipx comes from Mac/ or Linux/install.sh

echo 'Done.'


echo 'Installing Git configurations'

rm -rf ~/.gitconfig
ln -s $(pwd)/gitconfig $HOME/.gitconfig

echo 'Done.'
