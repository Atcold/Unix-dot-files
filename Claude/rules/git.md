# Git

- Never add Claude attribution: no `Co-Authored-By: Claude …` trailer, no `Claude-Session:` link, no ‘Generated with Claude Code’ line, in commits or PR descriptions. The commit is mine alone.
- Commit subject: one line, 50–72 characters, the substantive change only (no ‘sentence case fix’); a body only when the diff can’t explain a cross-cutting decision. Abbreviate long project names. Plain `-m "…"`, no heredoc.
- One concern per commit. Split unrelated changes.
- A finished code change ends documented (repo `CLAUDE.md`, the spec, or a note) and committed; don’t stop at a dirty tree and ask.
- But I am the tester: for anything I have to try (config, bindings, scripts, apps), apply it, restart what needs restarting, tell me what to try, and commit only after my OK. No self-checks of your own fix.
- Drafts I’m reviewing turn by turn stay uncommitted until I call them finished. Never push unless I ask.
- Fixing a commit already made: amend (and `push --force-with-lease` if pushed) instead of stacking a ‘fix’ commit. After a squash, same-session tweaks are amended in.
- No separate `git status` after `git add`: `git add <files> && git commit -m …`. Never chain `commit` and `push` into one hidden command.
- Tool repos hold tools only: none of my data, real paths, hosts or names; examples use placeholders. `git grep` for my identifiers before committing.
- Never commit binaries (PDFs, PNGs, renders, notebook output). Exception: images a lesson needs in learning-with-claude. Images for a GitHub issue are uploaded in the browser, never hosted in a repo.
- Assets are the exception: files from a maker that the project needs (a datasheet, a board drawing), committed as they come in an `assets/` folder. A file becomes an asset only after I agree to it.
