# cucina

Search GialloZafferano’s recipes and cook from one card per step. The full-width title sits above metadata and the finished-dish photo; ingredients and notes span the full width below. Browser pages use opaque black text on white. Turn pages with screen taps, mouse clicks, or keyboard arrows.

| Device | What runs there |
|---|---|
| Always-on Termux host | Python service on port 8082, recipe index, extractor, photo proxy, cache, notes, and tablet selection |
| Mac | `cucina` terminal picker, using the host’s API; e-ink’s terminal, PDF, and editor services stay on the Mac |
| Phone or tablet browser | `/` searches and opens cooking cards directly; `/screen` receives recipes selected in the terminal |

```sh
python3 install.py --url http://recipe-server:8082
cucina --help               # commands, devices, files, and navigation
cucina palline coco          # fuzzy title search, using fzf
cucina web                  # search and cook in this browser
cucina tablet               # open the tablet’s listening page
```

The terminal uses a wide search and a narrow coloured preview. ‘Mostra qui’ opens cooking cards locally; ‘Invia al tablet’ updates `/screen`. Both actions leave the preview open; Esc returns to search. The first cooking card includes servings, times, difficulty, calories, ingredients, notes, and links to search and source. Following cards show the steps and photos.

On the server, run `python3 install.py --host 0.0.0.0 --boot`, then `cucina up`. Python 3.10+ and its standard library are sufficient; `fzf` is needed only for the terminal picker. Termux:Boot starts the service after a reboot. `cucina status`, `down`, and `restart` manage the local service; `cucina refresh` updates the running index. Access it over the private network, including Tailscale.

`~/.config/cucina/config.json` holds client `url`, server `host`, and `port`; `CUCINA_URL` overrides the client URL. Notes, tablet selection, and logs persist in `~/.local/share/cucina/`. The index, recipes, and proxied photos live in `~/.cache/cucina/`. The installer links these folders into `Dropbox/Apps/cucina/` on Macs; Termux keeps its own copies.

The service refreshes the sitemap daily and caches recipes for seven days, using saved data when the source is unreachable. Search labels come from recipe addresses; cooking cards use original titles. Photos are fetched and cached by the server so the browser loads them from the same host.

The source is `Scripts/cucina/` in the settings repository. Deploy updated files there on the server, or pull the repository. HTML files are re-read on every request and need a browser reload; Python changes need `cucina restart`. `recipes.py` is the extractor shared with e-ink, which can select another copy with `EINK_RECIPE_CORE`.
