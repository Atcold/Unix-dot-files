# Global Claude Code Instructions

How I work with Claude is in `~/.claude/rules/`: `talking`, `writing`, `git`, `files`, `terminal`, and `latex` (loads only for `.tex`, `.sty`, `.bib`). Each rule lives in one place; this file holds only what those don't cover. A rule that applies across projects goes into the matching rule file, never into a project's memory.

## Google Workspace (Gmail, Calendar, Drive, …)
- Use the local `gog` CLI for all Gmail/Calendar/Google work, not the `mcp__*_Gmail__*` / `mcp__*_Google_Calendar__*` MCP tools.
- Run `gog` through `bash -ic 'gog …'` from non-interactive tools so `~/.bashrc` loads the file keyring credentials. Pass the account and client explicitly. For NYU, use `--client nyu` and the account recorded in project memory. Run `bash -ic 'gog auth list --plain'` to identify the configured account or check access before asking me to sign in.
- For a message from a known correspondent, check Google Chat as well as Gmail when the channel is unspecified.
