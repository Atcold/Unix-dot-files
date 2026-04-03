# Claude Settings Repo Instructions

## Rotating the claude.ai session key

The session key for the usage tracker is stored in the macOS Keychain (never in files).
When the key is compromised or expires:

1. Log out of claude.ai in the browser to invalidate the old key
2. Log back in
3. Run `~/.claude/rotate-session-key.sh` and follow the prompts

The script reads the new `sessionKey` cookie value (DevTools → Application → Cookies → claude.ai) and updates the Keychain entry. The Swift fetcher (`Claude/fetch-claude-usage.swift`) picks it up automatically.
