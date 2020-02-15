echo 'Installing Vim configurations'

/usr/local/bin/pip3 install jupytext
rm -rf vim/bundle
rm -rf ~/.vim*
mkdir vim/bundle
git clone --quiet https://github.com/VundleVim/Vundle.vim.git vim/bundle/Vundle.vim
ln -s $(pwd)/vimrc $HOME/.vimrc
ln -s $(pwd)/vim   $HOME/.vim
vim -u vim/myBundle.vim +PluginInstall +qall

echo 'Done.'
