echo 'Installing Neovim configuration'

# Neovim plus the picker's file-search backend: fzf-lua needs both fzf and
# ripgrep, otherwise :Obsidian quick_switch (\oo) opens an empty panel.
if [[ $(uname) == 'Darwin' ]]; then
    for pkg in neovim fzf ripgrep; do
        brew list $pkg >/dev/null 2>&1 || brew install $pkg
    done
else
    sudo apt-get update
    sudo apt-get install -y neovim fzf ripgrep
fi

mkdir -p ~/.config
rm -rf ~/.config/nvim
ln -s "$(pwd)" ~/.config/nvim
nvim --headless "+Lazy! sync" +qa
echo 'Done.'
