echo 'Installing Neovim configuration'

# Packages Neovim depends on:
#   neovim          - the editor itself
#   fzf, ripgrep    - fzf-lua's file-search backend; without both, :Obsidian
#                     quick_switch (\oo) opens an empty panel
#   tree-sitter-cli - the `tree-sitter` build tool nvim-treesitter uses to
#                     compile language parsers (bash, python) for code-fence
#                     highlighting in markdown. Homebrew's `tree-sitter`
#                     formula ships only the library, not this CLI.
if [[ $(uname) == 'Darwin' ]]; then
    for pkg in neovim fzf ripgrep tree-sitter-cli; do
        brew list $pkg >/dev/null 2>&1 || brew install $pkg
    done
else
    sudo apt-get update
    sudo apt-get install -y fzf ripgrep
    # apt's neovim is too old (Ubuntu 24.04 ships 0.9; the config needs 0.11+),
    # so take the latest release from GitHub into ~/.local
    ARCH=$(uname -m | sed 's/aarch64/arm64/')
    mkdir -p ~/.local/bin
    curl -L "https://github.com/neovim/neovim/releases/latest/download/nvim-linux-$ARCH.tar.gz" | tar xzf - -C ~/.local
    ln -sf ~/.local/nvim-linux-$ARCH/bin/nvim ~/.local/bin/nvim
    # tree-sitter-cli is not in apt either; its release ships a prebuilt binary
    TS_ARCH=$(uname -m | sed 's/aarch64/arm64/; s/x86_64/x64/')
    curl -L "https://github.com/tree-sitter/tree-sitter/releases/latest/download/tree-sitter-linux-$TS_ARCH.gz" \
        | gunzip > ~/.local/bin/tree-sitter
    chmod +x ~/.local/bin/tree-sitter
fi

mkdir -p ~/.config
rm -rf ~/.config/nvim
ln -s "$(pwd)" ~/.config/nvim
nvim --headless "+Lazy! sync" +qa
echo 'Done.'
