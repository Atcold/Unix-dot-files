# Neovim

Minimal Neovim config for the `cc.md` Claude channel — live Markdown rendering via
`render-markdown.nvim` (Treesitter-backed), plus `conceallevel=2` on `cc.md`.

Kept separate from the Vim config: this is for the Claude back-and-forth, not a Vim
replacement.

Plugin manager: lazy.nvim (bootstraps itself on first launch).
Run `./install.sh` to symlink `~/.config/nvim` here and sync plugins.
