// OpenCode plugin: the same two hooks Claude Code and Codex run.
// It names the machine in the system prompt, and after OpenCode writes a .tex file
// it runs ~/.claude/hooks/writing-check.py and appends its reminder to the tool output.
export const WritingCheck = async ({ $ }) => {
  const host = (await $`scutil --get LocalHostName`.nothrow().text()).trim()
  const script = `${process.env.HOME}/.claude/hooks/writing-check.py`
  return {
    "experimental.chat.system.transform": async (_input, output) => {
      if (host) output.system.push(`This session runs on ${host}.`)
    },
    "tool.execute.after": async (input, output) => {
      if (!["write", "edit", "patch"].includes(input.tool)) return
      const args = input.args || {}
      const payload = JSON.stringify({ tool_input: { file_path: args.filePath, command: args.patchText } })
      const result = (await $`python3 ${script} < ${new Response(payload)}`.nothrow().text()).trim()
      if (!result) return
      output.output += "\n\n" + JSON.parse(result).hookSpecificOutput.additionalContext
    },
  }
}
