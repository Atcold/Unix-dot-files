# Global Claude Code Instructions

How I work with Claude is in `~/.claude/rules/`: `talking`, `writing`, `git`, `files`, `terminal`, and `latex` (loads only for `.tex`, `.sty`, `.bib`). Each rule lives in one place; this file holds only what those don't cover. A rule that applies across projects goes into the matching rule file, never into a project's memory.

## Google Workspace (Gmail, Calendar, Drive, …)
- Use the local `gog` CLI for all Gmail/Calendar/Google work, not the `mcp__*_Gmail__*` / `mcp__*_Google_Calendar__*` MCP tools.
- Run `gog` from my interactive Bash setup. From a non-interactive tool, use `bash -lic 'gog …'` so the startup files load the file keyring. For NYU, use the account recorded in project memory. Check access this way before asking me to sign in.
