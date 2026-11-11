# OpenCode settings

`writing-check.js` is an OpenCode plugin that runs the same two hooks as Claude Code and Codex. It adds the machine's name to the system prompt, and after OpenCode's `write`, `edit`, or `patch` tool changes a `.tex` file it runs [`Claude/hooks/writing-check.py`](../Claude/hooks/writing-check.py) and appends the script's reminder to the tool's output, where the model reads it.

OpenCode loads it from the `plugin` list in its configuration, `~/.config/opencode/opencode.json`, as `file://` followed by the absolute path of this file in the local checkout.
