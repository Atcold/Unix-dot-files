-- Neovim config — primarily for the cc.md Claude channel with live Markdown rendering.
-- The Obsidian-aware markdown environment lives in the `obs-mode` module (lua/obs-mode/);
-- everything below is bootstrap, personal plugins, and personal-vault conventions.

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

-- Plugins: personal/general ones here, the Obs-mode bundle's specs spread in after.
local specs = {
  -- Key hints: press <leader> (\) and a popup lists the available mappings
  { "folke/which-key.nvim", event = "VeryLazy", opts = { delay = 3000 } },  -- wait 3s before the help panel pops

  -- Colour schemes (flip live with :colorscheme <name>)
  { "folke/tokyonight.nvim" },
  { "catppuccin/nvim", name = "catppuccin" },
  { "Mofiqul/dracula.nvim" },
  { "EdenEast/nightfox.nvim" },
  { "tanvirtin/monokai.nvim" },
}
vim.list_extend(specs, require("obs-mode").specs)
require("lazy").setup(specs)

-- Default colour scheme; flip live with :colorscheme <name>.
pcall(vim.cmd.colorscheme, "catppuccin")

-- Obs-mode runtime: markdown buffer behaviour + welcome screen autocmds.
require("obs-mode").setup()

-- Project notes open with their "## Log" section folded. Folding is on globally
-- (vim.g.markdown_folding) but notes start fully open (foldlevel = 99 in markdown.lua);
-- here we close just the one Log fold so the timestamped history sits out of the way while
-- the goal/status/next-action stay visible. Fires on BufWinEnter so a window (and its
-- folds) exists; <CR> on the heading reopens it. Pattern matches the vault's Projects/ dir.
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
