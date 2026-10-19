# Scripts

Standalone utility scripts. Portable across macOS and Linux.

## `spark.py`

Powers a machine on a Kasa smart plug (AlfSPARK, by default) on and off from anywhere: the plug is switched through TP-Link's cloud, the machine is reached over the tailnet. `spark status`, `on [--wait]`, `off` (clean shutdown over `ssh` first, then the plug), `restart`, `setup`. macOS only: the TP-Link login lives in the Keychain. Runs with `uv run --script`, which fetches its one dependency; link it onto the `PATH` as `spark` with `ln -s ~/.settings/Scripts/spark.py ~/.local/bin/spark`.

## `wget-resume.sh`

Resumable `wget` with stall detection. Re-launches `wget` if the file size hasn't grown for ~30 s, so a silently-frozen download (server stops sending bytes but keeps the connection open) doesn't hang forever.
