-- Neovim config — primarily for the cc.md Claude channel with live Markdown rendering.

-- Bootstrap lazy.nvim
local lazypath = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"
if not (vim.uv or vim.loop).fs_stat(lazypath) then
  vim.fn.system({
    "git", "clone", "--filter=blob:none",
    "https://github.com/folke/lazy.nvim.git", "--branch=stable", lazypath,
  })
end
vim.opt.rtp:prepend(lazypath)

-- Basic options (mirroring the Vim setup)
vim.opt.termguicolors = true
vim.opt.number = true
vim.opt.expandtab = true
vim.opt.tabstop = 4
vim.opt.shiftwidth = 4
vim.opt.softtabstop = 4

-- Enable Neovim's bundled markdown section folding (foldexpr=MarkdownFold). Must be set
-- before the markdown ftplugin runs. This is also what lets obsidian's Smart Action fold
-- a heading on <CR> (it checks vim.g.markdown_folding) instead of falling through.
vim.g.markdown_folding = 1

-- Plugins
require("lazy").setup({
  {
    "MeanderingProgrammer/render-markdown.nvim",
    opts = {
      render_modes = true,  -- render in all modes
      -- Size table columns to the *visual* width, not the raw markdown. Default 'padded'
      -- pads each column to the raw cell span, so a concealed [[target|alias]] wikilink
      -- (long source, short rendered icon+alias) leaves a big trailing gap. 'trimmed'
      -- subtracts the concealed empty space from the width calculation.
      pipe_table = { cell = "trimmed" },
      -- Reveal the cursor line's raw markup only while editing it (insert mode);
      -- keep it rendered in normal/visual/command so reading stays clean.
      -- Two layers must agree: anti_conceal covers drawn glyphs (headings, bullets);
      -- concealcursor covers Vim-concealed inline markup (`code`, *italic*, **bold**).
      anti_conceal = { disabled_modes = { "n", "v", "V", "\22", "c" } },
      win_options = { concealcursor = { rendered = "nvc" } },  -- hide inline markers except in insert
    },
  },

  -- Completion engine. obsidian.nvim no longer ships its own completion source; it
  -- runs an in-process LSP (obsidian-ls) and leaves the UI to a real engine. blink's
  -- default sources include "lsp", so typing `[[` in a markdown buffer fuzzy-completes
  -- note names and accepting inserts a fully-closed [[link]] — no manual `]]` needed.
  {
    "saghen/blink.cmp",
    version = "*",  -- release tag ships the prebuilt fuzzy-matcher binary; no Rust build
    event = "InsertEnter",
    opts = {
      -- "enter" preset: Enter accepts the highlighted item, <C-n>/<C-p> or arrows move,
      -- <C-e> dismisses. Enter still inserts a newline when the menu is closed.
      keymap = { preset = "enter" },
      -- Only the obsidian-ls LSP (fires on `[[` and `#`) and path completion. No
      -- "buffer" source: that completes words already in the buffer, which spams a
      -- dictionary-like popup on ordinary prose.
      sources = { default = { "lsp", "path" } },
    },
  },

  -- Obsidian vault: follow [[wikilinks]], backlinks, link/tag completion.
  -- UI is left to render-markdown.nvim (ui.enable = false avoids a double-render clash).
  {
    "obsidian-nvim/obsidian.nvim",
    version = "*",
    ft = "markdown",
    cmd = "Obsidian",  -- also load on :Obsidian, so it works with no .md buffer open
    keys = {
      -- \o… = Obsidian group. All global, so they work from any buffer (or none);
      -- pressing any of them lazy-loads obsidian. \o is now a prefix, not a mapping,
      -- so there's no bare-\o wait — \oo/\os/\oa fire as fast as you type them.
      { "<leader>oo", "<cmd>Obsidian quick_switch<cr>", desc = "Open note by name" },
      -- Same picker as \oo, but open the chosen note in a new tab. quick_switch has no
      -- "tab" flag, so call the picker directly and route the selection through
      -- api.open_note(path, "tabedit") — the 2nd arg is the :open command (default "e").
      { "<leader>oO", function()
          Obsidian.picker.find_notes({
            prompt_title = "Quick Switch (new tab)",
            callback = function(path)
              require("obsidian.api").open_note(path, "tabedit")
            end,
          })
        end, desc = "Open note by name in a new tab" },
      { "<leader>os", "<cmd>Obsidian search<cr>",       desc = "Search vault contents" },
      { "<leader>oa", "<cmd>Obsidian open<cr>",         desc = "Open current note in Obsidian app" },
    },
    dependencies = {
      "nvim-lua/plenary.nvim",
      -- Picker backend for obsidian's pickers — no leader keymaps of its own.
      { "ibhagwan/fzf-lua", opts = { winopts = { fullscreen = true } } },
    },
    init = function()
      -- Smart Action on <CR>: in a markdown buffer Return follows a [[link]] under the
      -- cursor, toggles a - [ ] checkbox, folds a heading, else behaves as a plain Return.
      -- This is the *only* mapping the flag gates; <C-]> still follows links too.
      -- (Was disabled before because the checkbox toggle bumped - [ ] to - [~] instead
      -- of ticking — that was the 5-state default order, now fixed by checkbox.order below.)
      vim.g.obsidian_default_keymap = true
    end,
    opts = {
      legacy_commands = false,  -- use the new `:Obsidian <subcommand>` form
      picker = { name = "fzf-lua" },  -- backend for :Obsidian search / quick_switch / tags
      workspaces = {
        {
          name = "md-Wiki",
          path = "/Users/atcold/Library/Mobile Documents/iCloud~md~obsidian/Documents/md-Wiki",
        },
      },
      ui = { enable = false },
      -- Binary checkbox toggle: blank <-> x. Obsidian's default cycles a 5-state
      -- ladder { " ", "~", "!", ">", "x" }, so one <CR> bumped - [ ] to - [~] instead
      -- of ticking it. We only ever want done/not-done here.
      -- create_new = false: the Smart Action only toggles an *existing* checkbox. With the
      -- default (true) it would manufacture a checkbox on any line — e.g. <CR> on a heading
      -- (when folding is off) turned the title into a - [ ] box.
      checkbox = { order = { " ", "x" }, create_new = false },
      -- Don't let obsidian.nvim inject/rewrite `id/aliases/tags` frontmatter on every
      -- save. This vault's convention is plain markdown with frontmatter only where it
      -- has a function (see CLAUDE.md), so auto-frontmatter is unwanted noise.
      frontmatter = { enabled = false },
    },
  },

  -- Key hints: press <leader> (\) and a popup lists the available mappings
  { "folke/which-key.nvim", event = "VeryLazy", opts = { delay = 3000 } },  -- wait 3s before the help panel pops

  -- Colour schemes (flip live with :colorscheme <name>)
  { "folke/tokyonight.nvim" },
  { "catppuccin/nvim", name = "catppuccin" },
  { "Mofiqul/dracula.nvim" },
  { "EdenEast/nightfox.nvim" },
  { "tanvirtin/monokai.nvim" },
})

-- Default colour scheme; flip live with :colorscheme <name>.
pcall(vim.cmd.colorscheme, "catppuccin")

-- Markdown: soft wrap + spell, like the Vim config
vim.api.nvim_create_autocmd("FileType", {
  pattern = "markdown",
  callback = function()
    vim.opt_local.wrap = true
    vim.opt_local.linebreak = true
    vim.opt_local.spell = false
    -- Folding is enabled (vim.g.markdown_folding) but start every note fully open;
    -- <CR> on a heading then folds that one section on demand, rather than the whole
    -- note opening collapsed.
    vim.opt_local.foldlevel = 99
    -- Syntax highlighting via Neovim's bundled markdown treesitter. We dropped the
    -- nvim-treesitter plugin: its master branch is incompatible with nvim 0.12 and
    -- crashed on code-fence language injections (e.g. ```bash in gog-setup.md).
    pcall(vim.treesitter.start)
    -- Follow [[wikilinks]] with Ctrl-] (matches the gog-docs browser muscle memory).
    -- Buffer-local, so Ctrl-] stays as tag-jump in other filetypes. Jump back with Ctrl-o.
    vim.keymap.set("n", "<C-]>", "<cmd>Obsidian follow_link<cr>",
      { buffer = true, silent = true, desc = "Follow [[link]]" })
    -- Hop between links with ]o / [o. These are obsidian's own defaults; we lost them
    -- by disabling its default keymaps (to free <CR>), so re-add just these two.
    vim.keymap.set("n", "]o", function() require("obsidian.api").nav_link("next") end,
      { buffer = true, silent = true, desc = "Next link" })
    vim.keymap.set("n", "[o", function() require("obsidian.api").nav_link("prev") end,
      { buffer = true, silent = true, desc = "Previous link" })
    -- Follow a [[link]] in a vertical split (side-by-side) — the "open in new tab" feel.
    -- \v from a link opens the target in a vsplit. We avoid a \o* mapping: \o is the
    -- quick-switch key, so sharing that prefix would add timeoutlen lag to it.
    vim.keymap.set("n", "<leader>v", "<cmd>Obsidian follow_link vsplit<cr>",
      { buffer = true, silent = true, desc = "Follow [[link]] in vsplit" })
    -- Ctrl-W ] mirrors Vim's "jump to tag in a horizontal split", but for [[links]].
    -- Buffer-local, so it only shadows the builtin in markdown where we follow wikilinks.
    vim.keymap.set("n", "<C-w>]", "<cmd>Obsidian follow_link hsplit<cr>",
      { buffer = true, silent = true, desc = "Follow [[link]] in hsplit" })
  end,
})

-- Conceal on by default for the Claude channel file
vim.api.nvim_create_autocmd({ "BufRead", "BufNewFile" }, {
  pattern = "cc.md",
  callback = function()
    vim.opt_local.conceallevel = 2
    vim.opt_local.concealcursor = "nc"
    -- Typing @ inserts the character and fires insert-mode file-path completion
    -- (i_CTRL-X_CTRL-F), so @Areas/Cooking/... can be tab-completed inline. Paths are
    -- relative to nvim's cwd, so launch nvim from the vault root for them to resolve.
    vim.keymap.set("i", "@", "@<C-x><C-f>",
      { buffer = true, silent = true, desc = "@ + file-path completion" })
  end,
})
