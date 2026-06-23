-- Obs-mode: a curated bundle that turns Neovim into an Obsidian-aware markdown
-- environment. It pulls in render-markdown.nvim, blink.cmp, obsidian.nvim and
-- nvim-treesitter, each carrying battle-tested configs that fix bad upstream defaults,
-- plus the Obs-mode welcome screen and [[wikilink]] navigation keymaps.
--
-- M.specs  — the lazy.nvim plugin specs (spread into your lazy.setup list).
-- M.setup() — registers the runtime autocmds (markdown buffer behaviour + welcome screen).
local M = {}

-- The one personal value in the bundle: your vault's path. (Future: surface this through a
-- setup(opts) field so others can point it at their own vault.)
local vault_path = "/Users/atcold/Library/Mobile Documents/iCloud~md~obsidian/Documents/md-Wiki"

M.specs = {
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
          path = vault_path,
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

  -- Tree-sitter parsers ONLY (no highlight plugin). Neovim 0.12 bundles markdown +
  -- markdown_inline but not language parsers, so ```bash / ```python code fences stay
  -- one flat colour: the markdown injection query resolves the fence language but has
  -- no parser to inject into. We use the plugin's `main` branch (the 0.11+ rewrite) —
  -- the old `master` branch is what broke on 0.12. It just drops the .so files on the
  -- runtimepath; highlighting is still driven by our own `vim.treesitter.start()` in
  -- the markdown FileType autocmd (see markdown.lua). Add languages to the install list as needed.
  {
    "nvim-treesitter/nvim-treesitter",
    branch = "main",
    build = ":TSUpdate",
    lazy = false,
    config = function()
      require("nvim-treesitter").install({ "bash", "python" })
    end,
  },
}

function M.setup()
  require("obs-mode.markdown").setup()
  require("obs-mode.welcome").setup()
end

return M
