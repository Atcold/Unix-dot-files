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

  -- Tree-sitter parsers ONLY (no highlight plugin). Neovim 0.12 bundles markdown +
  -- markdown_inline but not language parsers, so ```bash / ```python code fences stay
  -- one flat colour: the markdown injection query resolves the fence language but has
  -- no parser to inject into. We use the plugin's `main` branch (the 0.11+ rewrite) —
  -- the old `master` branch is what broke on 0.12. It just drops the .so files on the
  -- runtimepath; highlighting is still driven by our own `vim.treesitter.start()` in
  -- the markdown FileType autocmd below. Add languages to the install list as needed.
  {
    "nvim-treesitter/nvim-treesitter",
    branch = "main",
    build = ":TSUpdate",
    lazy = false,
    config = function()
      require("nvim-treesitter").install({ "bash", "python" })
    end,
  },
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

-- Project notes open with their "## Log" section folded. Folding is on globally
-- (vim.g.markdown_folding) but notes start fully open (foldlevel = 99 above); here we
-- close just the one Log fold so the timestamped history sits out of the way while the
-- goal/status/next-action stay visible. Fires on BufWinEnter so a window (and its folds)
-- exists; <CR> on the heading reopens it. Pattern matches the vault's Projects/ dir.
vim.api.nvim_create_autocmd("BufWinEnter", {
  pattern = "*/Projects/*.md",
  callback = function(args)
    local lines = vim.api.nvim_buf_get_lines(args.buf, 0, -1, false)
    for lnum, line in ipairs(lines) do
      if line:match("^## Log%s*$") then
        -- zx recomputes folds (foldexpr is lazy), then close the fold at that line.
        vim.cmd("normal! zx")
        pcall(vim.cmd, lnum .. "foldclose")
        break
      end
    end
  end,
})

-- Welcome screen: launching bare `nvim` from any Obsidian vault root drops you on a
-- read-only cheat-sheet of the shortcuts instead of a blank [No Name] buffer.
-- The global \o… keys already work from any buffer, so they're live right here; the
-- buffer-local ones (Ctrl-], ]o…) are listed for reference and fire once you're in a note.
-- A vault is detected by the marker `.obsidian/` config dir at the cwd, so this works
-- for any vault, not just md-Wiki.
vim.api.nvim_create_autocmd("VimEnter", {
  callback = function()
    if vim.fn.argc() ~= 0 then return end                 -- a file was passed: don't intrude
    if vim.fn.isdirectory(vim.fn.getcwd() .. "/.obsidian") ~= 1 then return end  -- only at a vault root
    if vim.api.nvim_buf_get_name(0) ~= "" or vim.bo.modified then return end  -- only the empty startup buffer

    -- Content as typed rows so each kind gets its own highlight group (extmarks below).
    -- Groups are colourscheme-defined (Title/Function/String/Comment), so this tracks
    -- whatever :colorscheme is active rather than hard-coding colours.
    local INDENT, KEY_INDENT, KEY_W = "    ", "      ", 11
    -- Branded banner (à la Emacs Org-mode): "Nvim <version> · Obs-mode", with an
    -- underline of matching width.
    local v = vim.version()
    local title = ("Nvim %d.%d.%d · Obs-mode"):format(v.major, v.minor, v.patch)
    local items = {
      { kind = "title",   text = title },
      { kind = "rule",    text = ("─"):rep(vim.fn.strdisplaywidth(title)) },
      { kind = "blank" },
      { kind = "section", text = "Open & search" },
      { kind = "key", key = "\\oo",      desc = "Open note by name" },
      { kind = "key", key = "\\oO",      desc = "Open note by name in a new tab" },
      { kind = "key", key = "\\os",      desc = "Search vault contents (grep)" },
      { kind = "key", key = "\\oa",      desc = "Open current note in the Obsidian app" },
      { kind = "blank" },
      { kind = "section", text = "Inside a note" },
      { kind = "key", key = "<CR>",     desc = "Follow link · toggle checkbox · fold heading" },
      { kind = "key", key = "]o  [o",   desc = "Next · previous link" },
      { kind = "key", key = "Ctrl-]",   desc = "Follow [[link]]" },
      { kind = "key", key = "Ctrl-w ]", desc = "Follow link in a horizontal split" },
      { kind = "key", key = "\\v",      desc = "Follow link in a vertical split" },
      { kind = "key", key = "Ctrl-o",   desc = "Jump back" },
      { kind = "key", key = "gx",       desc = "Open URL under cursor in browser" },
      { kind = "blank" },
      { kind = "footer",  text = "\\ is the leader key  ·  q to quit" },
    }
    local line_hl = { title = "Title", rule = "Comment", section = "Function", footer = "Comment" }
    local lines, marks = { "" }, {}  -- leading blank for top padding
    for _, it in ipairs(items) do
      if it.kind == "blank" then
        table.insert(lines, "")
      elseif it.kind == "key" then
        local pad = string.rep(" ", math.max(1, KEY_W - #it.key))
        table.insert(lines, KEY_INDENT .. it.key .. pad .. it.desc)
        marks[#lines] = { col = #KEY_INDENT, ec = #KEY_INDENT + #it.key, hl = "String" }
      else
        table.insert(lines, INDENT .. it.text)
        marks[#lines] = { col = #INDENT, ec = -1, hl = line_hl[it.kind] }
      end
    end
    table.insert(lines, "")  -- trailing blank

    local buf = vim.api.nvim_create_buf(false, true)
    vim.api.nvim_buf_set_lines(buf, 0, -1, false, lines)
    local ns = vim.api.nvim_create_namespace("obsidian_welcome")
    for lnum, m in pairs(marks) do
      local row, ec = lnum - 1, m.ec == -1 and #lines[lnum] or m.ec
      vim.api.nvim_buf_set_extmark(buf, ns, row, m.col, { end_row = row, end_col = ec, hl_group = m.hl })
    end
    vim.bo[buf].modifiable = false
    vim.bo[buf].buftype = "nofile"
    vim.bo[buf].bufhidden = "wipe"
    vim.bo[buf].swapfile = false
    vim.bo[buf].filetype = "obsidian-welcome"
    vim.keymap.set("n", "q", "<cmd>qa<cr>", { buffer = buf, silent = true, desc = "Quit" })
    vim.api.nvim_set_current_buf(buf)
    vim.wo.number = false
    vim.wo.relativenumber = false
    vim.wo.cursorline = false
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
