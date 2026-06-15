# Neovim

Neovim config for driving the Obsidian `md-Wiki` vault from the terminal, and for the
`cc.md` Claude back-and-forth channel. Live Markdown rendering via `render-markdown.nvim`
(Treesitter-backed), with `conceallevel=2` on `cc.md`.

Kept separate from the Vim config: this is for the vault and the Claude channel, not a
Vim replacement.

## Requirements

- **Neovim** (recent — the config targets 0.12 and uses the bundled markdown Treesitter).
- **fzf** and **ripgrep** — the file-search backend for the Obsidian pickers
  (`fzf-lua`). Without a real `rg` binary on `PATH`, `\oo` / `\os` open an *empty*
  panel. `./install.sh` installs both (brew on macOS, `apt-get` on Linux).

Note: a shell `rg` alias/function (e.g. Claude Code's bundled ripgrep) does **not**
count — Neovim resolves binaries on `PATH`, not shell functions.

## Plugins (lazy.nvim)

- `render-markdown.nvim` — live rendering; raw markup revealed only on the cursor line in insert mode.
- `obsidian.nvim` — vault navigation: follow `[[wikilinks]]`, quick-switch, search, backlinks.
- `blink.cmp` — completion; `[[` and `#` fuzzy-complete note names / tags via obsidian's in-process LSP.
- `fzf-lua` — picker backend for the Obsidian commands.
- `which-key.nvim` — press `\` and wait 3 s for a popup of available mappings.
- Colour schemes: catppuccin (default), tokyonight, dracula, nightfox, monokai — flip live with `:colorscheme <name>`.

## Keymaps

Leader is `\` (Neovim default; no `mapleader` override).

| Key       | Action                                    | Scope            |
|-----------|-------------------------------------------|------------------|
| `\oo`     | Quick-switch: open note by name           | global           |
| `\os`     | Search vault contents                     | global           |
| `\oa`     | Open current note in the Obsidian app     | global           |
| `<CR>`    | Smart Action: follow link / toggle checkbox / fold heading | markdown |
| `<C-]>`   | Follow `[[link]]` under cursor (`<C-o>` jumps back) | markdown |
| `\v`      | Follow `[[link]]` in a vertical split     | markdown         |
| `<C-w>]`  | Follow `[[link]]` in a horizontal split   | markdown         |
| `]o` / `[o` | Hop to next / previous link             | markdown         |
| `@`       | Insert `@` + file-path completion         | `cc.md`          |

Checkbox toggle is binary (blank <-> `x`); frontmatter auto-injection is disabled, matching
the vault's plain-markdown convention.

## Install

`./install.sh` installs Neovim + `fzf` + `ripgrep`, symlinks `~/.config/nvim` here, and
syncs plugins. lazy.nvim bootstraps itself on first launch.
