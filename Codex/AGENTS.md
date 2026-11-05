# Use the existing Claude Code workflow

Before working, read `~/.claude/CLAUDE.md` and the existing `talking.md`, `writing.md`, `git.md`, `files.md`, and `terminal.md` in `~/.claude/rules/`. Read `latex.md` there when working with `.tex`, `.sty`, or `.bib` files. These files are the source of truth; interpret references to Claude as applying to this assistant too. Number questions only, as the user clarified.

Start in the existing PARA project home. Read its `note.md` and applicable `CLAUDE.md` files before work, including those inside linked repositories when entering them. Follow Claude's `@` file references by reading the referenced files.

Use existing project context in `~/.claude/projects/`: locate the directory matching the project home (physical path with separators encoded as hyphens), read its `memory/MEMORY.md` when present, and read relevant memory files as needed. Keep durable progress in the existing project note and maintain existing instructions where appropriate. Do not create a separate Codex rules, skills, or project-memory system.

Skills are linked to `~/.claude/skills/`. Follow compatible skills using available tools; Claude-only tool names, hooks, permissions, and slash commands require an available equivalent and are not automatically executable in Codex. Report a capability gap when it affects the task.

When a native Codex skill and a shared Claude skill cover the same document format, use the native Codex skill with its available tools. Use the shared Claude skills for the remaining tasks, following the original Claude rules in either case.
