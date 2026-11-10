# Claude settings

`CLAUDE.md` and `rules/` hold the global workflow used by Claude and Codex. Claude reads these through links in its application home. The entire `rules/` directory is linked, so adding a rule here makes it available through the same link. Codex reads the shared files as directed by [`AGENTS.md`](../Codex/AGENTS.md).

From the repository root, run `bash Claude/install.sh` to link the global instructions, the entire rules folder, and the status line into the Claude application home. Existing files are backed up under the user's Scratch directory. Run this on each Mac after checking out the same settings revision; shared application homes resolve the links through each Mac's local settings checkout.

Application homes can be shared through Dropbox using symlinks. Each machine keeps its own checkout of this repository and must pull updates to keep instructions and rules aligned.

`settings.base.json` holds the settings I own: attribution, model, effort, the status line, and the hooks. `install.sh` merges it into `~/.claude/settings.json`, where its keys win and every key the app writes, such as permissions, theme, and voice, stays as it is. A hook is changed here and installed by rerunning `install.sh`.

`install.sh` uses Bash for links and backups and requires `jq` to update JSON. It updates the status-line command while preserving the other runtime settings.

The status line reads five-hour and weekly account usage from Claude Code’s [status-line input](https://code.claude.com/docs/en/statusline#rate-limit-usage), including the percentage consumed and reset time. Usage becomes available after the session’s first API response. Colours, quota boxes, the elapsed-time marker, and the local reset time are rendered in Bash from that input.

The weekly block appears beside the five-hour block when the percentage consumed exceeds the elapsed share of the seven-day window. The comparison uses the supplied percentage before rounding the boxes. Its local reset weekday and time distinguish it from the five-hour block, which retains its reset time.
