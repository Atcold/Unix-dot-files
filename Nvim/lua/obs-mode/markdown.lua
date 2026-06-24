-- Obs-mode markdown buffer behaviour: soft wrap + spell off, fold defaults, treesitter
-- syntax highlighting, and the [[wikilink]] navigation keymaps. Registered as a markdown
-- FileType autocmd by M.setup().
local M = {}

function M.setup()
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
      -- \ov from a link opens the target in a vsplit. We avoid a \o* mapping: \o is the
      -- quick-switch key, so sharing that prefix would add timeoutlen lag to it.
      vim.keymap.set("n", "<leader>ov", "<cmd>Obsidian follow_link vsplit<cr>",
        { buffer = true, silent = true, desc = "Follow [[link]] in vsplit" })
      -- Ctrl-W ] mirrors Vim's "jump to tag in a horizontal split", but for [[links]].
      -- Buffer-local, so it only shadows the builtin in markdown where we follow wikilinks.
      vim.keymap.set("n", "<C-w>]", "<cmd>Obsidian follow_link hsplit<cr>",
        { buffer = true, silent = true, desc = "Follow [[link]] in hsplit" })
    end,
  })
end

return M
