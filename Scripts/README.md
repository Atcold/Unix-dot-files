# Scripts

Standalone utility scripts. Portable across macOS and Linux.

## `wget-resume.sh`

Resumable `wget` with stall detection. Re-launches `wget` if the file size hasn't grown for ~30 s, so a silently-frozen download (server stops sending bytes but keeps the connection open) doesn't hang forever.
