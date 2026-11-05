# Claude settings

`CLAUDE.md` and `rules/` hold the global workflow used by Claude and Codex. Claude reads these through links in its application home. The entire `rules/` directory is linked, so adding a rule here makes it available through the same link. Codex reads the shared files as directed by [`AGENTS.md`](../Codex/AGENTS.md).

From the repository root, run `bash Claude/install.sh` to link the global instructions, the entire rules folder, and the status line into the Claude application home. Existing files are backed up under the user's Scratch directory. Run this on each Mac after checking out the same settings revision; shared application homes resolve the links through each Mac's local settings checkout.

Application homes can be shared through Dropbox using symlinks. Each machine keeps its own checkout of this repository and must pull updates to keep instructions and rules aligned.

`settings.example.json` contains portable preferences and the machine-identification SessionStart hook. Merge the desired fields into the existing runtime settings, preserving permissions and application-managed fields.

`install.sh` uses Bash for links and backups and requires `jq` to update JSON. It also updates the status-line command while preserving the other runtime settings. The usage scripts use macOS Keychain credentials. Application-generated fetchers may contain credentials and remain in the runtime home.

## Rotating the claude.ai session key

The session key for the usage tracker is stored in the macOS Keychain (never in files).
When the key is compromised or expires:

1. Log out of claude.ai in the browser to invalidate the old key
2. Log back in
3. Run `~/.claude/rotate-session-key.sh` and follow the prompts

The script reads the new `sessionKey` cookie value (DevTools → Application → Cookies → claude.ai) and updates the Keychain entry. The Swift fetcher (`fetch-claude-usage.swift`) picks it up automatically.
