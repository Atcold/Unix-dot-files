echo 'Installing Vim configurations'

mkdir vim/bundle
git clone --quiet https://github.com/VundleVim/Vundle.vim.git vim/bundle/Vundle.vim
ln -s $(pwd)/vimrc $HOME/.vimrc
ln -s $(pwd)/vim   $HOME/.vim
vim -u vim/myVundle.vim +PluginInstall +qall

echo 'Done.'
