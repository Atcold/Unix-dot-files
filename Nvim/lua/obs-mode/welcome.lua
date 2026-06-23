-- Obs-mode welcome screen: launching bare `nvim` from any Obsidian vault root drops you
-- on a read-only cheat-sheet of the shortcuts instead of a blank [No Name] buffer.
-- The global \o… keys already work from any buffer, so they're live right here; the
-- buffer-local ones (Ctrl-], ]o…) are listed for reference and fire once you're in a note.
-- A vault is detected by the marker `.obsidian/` config dir at the cwd, so this works
-- for any vault, not just md-Wiki.
local M = {}

-- Build and show the welcome buffer unconditionally — used on demand via \oh / :ObsHome
-- (the startup guards live in M.setup's VimEnter handler, not here).
function M.open()
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
    { kind = "footer",  text = "\\ is the leader key  ·  \\oh home  ·  q to quit" },
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
end

function M.setup()
  -- Auto-show only on a clean startup at a vault root; otherwise stay out of the way.
  vim.api.nvim_create_autocmd("VimEnter", {
    callback = function()
      if vim.fn.argc() ~= 0 then return end                 -- a file was passed: don't intrude
      if vim.fn.isdirectory(vim.fn.getcwd() .. "/.obsidian") ~= 1 then return end  -- only at a vault root
      if vim.api.nvim_buf_get_name(0) ~= "" or vim.bo.modified then return end  -- only the empty startup buffer
      M.open()
    end,
  })
  -- Re-open the home screen on demand from any note: \oh or :ObsHome.
  vim.keymap.set("n", "<leader>oh", M.open, { silent = true, desc = "Obsidian home (welcome screen)" })
  vim.api.nvim_create_user_command("ObsHome", M.open, { desc = "Open the Obs-mode welcome screen" })
end

return M
