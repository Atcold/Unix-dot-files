echo 'Installing Neovim configuration'
brew list neovim >/dev/null 2>&1 || brew install neovim
mkdir -p ~/.config
rm -rf ~/.config/nvim
ln -s "$(pwd)" ~/.config/nvim
nvim --headless "+Lazy! sync" +qa
echo 'Done.'
