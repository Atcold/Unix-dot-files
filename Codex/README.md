# Codex settings

`AGENTS.md` supplies Codex’s global instructions through a link in its application home. It tells Codex to read [`Claude/CLAUDE.md`](../Claude/CLAUDE.md) and the shared files in [`Claude/rules/`](../Claude/rules/), as well as the applicable project instructions, notes, and memory. Edit the shared rule files to change the workflow for both assistants.

`hooks.json` gives Codex the same two hooks as Claude Code: at session start it names the machine, and after `apply_patch` writes a `.tex` file it runs [`Claude/hooks/writing-check.py`](../Claude/hooks/writing-check.py). Codex runs a new or changed hook only after it is trusted in `/hooks`.

From the repository root, run `bash Codex/install.sh` to link `AGENTS.md` and `hooks.json` into the Codex application home. Run `bash Claude/install.sh` to set up the shared Claude instructions and rules that the adapter reads. Existing runtime files are backed up under the user's Scratch directory.

Application homes can be shared through Dropbox using symlinks. Each machine keeps its own checkout of this repository and must pull updates to keep instructions and rules aligned.

`config.example.toml` contains portable preferences copied from the current setup. Merge these fields into the existing runtime configuration; application-managed plugin entries and machine paths remain in that configuration.
