# Scripts

Standalone utility scripts. Portable across macOS and Linux.

## `spark.py`

Runs AlfSPARK end to end from any machine (macOS or Termux): powers the Kasa smart plug through TP-Link's cloud, starts the container that serves a model, opens this machine's ssh tunnel to it, and reports each fact on its own line.

  spark s                      plug, tailnet, service, tunnel, api
  spark on [--wait] | off | restart
  spark serve [<model> [server] | tunnel]    start a service, open the pipe, wait for the API; tunnel joins one already running
  spark unserve ...                          stop it; tunnel closes only this machine's pipe
  spark serving                what runs on the Spark
  spark models                 the model store, numbered, heaviest first
  spark model <n | org/name>   what the Hub records: quantization, parameters, base model, licence
  spark speed                  tokens per second from a live probe: first token, prefill, generation
  spark wattage                live chart of the plug's draw
  spark setup                  first run: names and the TP-Link login

`spark help <cmd>` explains any command. The config is `~/.config/spark/config.toml` (`model`, `hf`, and a `[models]` table of `[server, local, remote]` triples); the TP-Link login lives in the Keychain on macOS, in `~/.config/spark/credentials.toml` (mode 600) elsewhere. Runs with `uv run --script`, which fetches its one dependency; link it onto the `PATH` as `spark` with `ln -s ~/.settings/Scripts/spark.py ~/.local/bin/spark`.

## `wget-resume.sh`

Resumable `wget` with stall detection. Re-launches `wget` if the file size hasn't grown for ~30 s, so a silently-frozen download (server stops sending bytes but keeps the connection open) doesn't hang forever.

## `pdf-show`

Opens PDFs side by side on the screen next to the terminal:

    pdf-show a.pdf [b.pdf …]

By day the files open in Skim, which reloads itself on every rebuild. After sunset they open in Preview with View ▸ Use Dark Appearance for PDF, after every Preview document is closed, because Preview names windows by file name alone. Night falls by the time zone's own sunrise and sunset (a NOAA approximation; cities for New York and Rome). The script finds the screen beside the one holding the Terminal, lays the windows in a grid of columns at least ~720 px wide, and prints which app took the files.
