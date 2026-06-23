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
    sudo apt-get install -y neovim fzf ripgrep
    # tree-sitter-cli is not in apt; install via cargo if Rust is present.
    command -v tree-sitter >/dev/null 2>&1 || cargo install tree-sitter-cli
fi

mkdir -p ~/.config
rm -rf ~/.config/nvim
ln -s "$(pwd)" ~/.config/nvim
nvim --headless "+Lazy! sync" +qa
echo 'Done.'
