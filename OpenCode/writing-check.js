// OpenCode plugin: the same two hooks Claude Code and Codex run.
// It names the machine in the system prompt, and after a tool writes a .tex file it runs
// ~/.claude/hooks/writing-check.py and appends its reminder to the tool's result.
import { execFileSync } from "node:child_process"

const HOME = process.env.HOME
const SCRIPT = `${HOME}/.claude/hooks/writing-check.py`

function run(cmd, args, input) {
  try { return execFileSync(cmd, args, { input, encoding: "utf8" }).trim() } catch { return "" }
}

const host = run("scutil", ["--get", "LocalHostName"]) || run("hostname", ["-s"])

export default {
  id: "local.writing-check",
  async setup(ctx) {
    await ctx.session.hook("context", (event) => {
      if (host) event.system.push({ type: "text", text: `This session runs on ${host}.` })
    })

    await ctx.tool.hook("execute.after", (event) => {
      if (event.status !== "completed") return
      const input = event.input || {}
      const shell = event.tool === "bash"
      const cwd = input.workdir || input.cwd
      if (shell && !cwd) return  // a shell command without its folder: nothing to scan
      const payload = JSON.stringify({
        tool_name: shell ? "Bash" : event.tool,
        cwd,
        tool_input: { file_path: input.path || input.filePath, command: input.patchText },
      })
      const out = run("python3", [SCRIPT], payload)
      if (!out) return
      const note = JSON.parse(out).hookSpecificOutput.additionalContext
      const result = event.result || {}
      if (Array.isArray(result.content)) result.content.push({ type: "text", text: note })
      else result.content = [{ type: "text", text: note }]
      event.result = result
    })
  },
}
