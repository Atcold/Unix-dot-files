#!/usr/bin/env python3
"""After an assistant writes a .tex file, tell it to re-read the file against the writing rules.

Claude Code and Codex call it as a PostToolUse hook with JSON on stdin; the OpenCode plugin
sends it the same JSON. Claude's Write and Edit name the file in tool_input.file_path;
Codex's apply_patch names each file in its patch text, in tool_input.command. A shell command
(tool Bash) names no file, so after one the script takes the .tex files under the working
folder that changed in the last few seconds.
"""
import json, os, re, sys, time

RECENT = 10  # seconds: a .tex file changed this recently was written by the shell command
DEPTH = 3    # folders below the working folder to look in

data = json.load(sys.stdin)
tool_input = data.get("tool_input") or {}
paths = [tool_input["file_path"]] if tool_input.get("file_path") else []
paths += re.findall(r"^\*\*\* (?:Add|Update) File: (.+)$", tool_input.get("command") or "", re.M)
if data.get("tool_name") == "Bash":
    root = data.get("cwd") or os.getcwd()
    now = time.time()
    for folder, dirs, files in os.walk(root):
        if folder[len(root):].count(os.sep) >= DEPTH:
            dirs[:] = []
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "build"]
        for f in files:
            p = os.path.join(folder, f)
            if f.endswith(".tex") and now - os.path.getmtime(p) < RECENT:
                paths.append(p)
paths = [p.strip() for p in paths if p.strip().endswith(".tex")]
if not paths:
    sys.exit(0)

# A list of three or more without the Oxford comma: ", B and C" with no comma before the conjunction.
pattern = re.compile(r",\s[^,;:.()\\]{1,50}[^,\s]\s(and|or)\s")
msg = []
for path in paths:
    msg.append(f"You just wrote {path}. Before you finish, re-read the whole file against ~/.claude/rules/writing.md and latex.md and fix every violation in the prose: Oxford commas, full sentences instead of fragments joined by colons or semicolons, positive statements instead of absences, every term explained where it first appears, sources cited with links, and no layout changes.")
    hits = []
    try:
        for n, line in enumerate(open(path, encoding="utf-8"), 1):
            text = "" if line.lstrip().startswith("\\bibitem") else line.split("%")[0]
            if pattern.search(text):
                hits.append(f"  {n}: {text.strip()[:140]}")
    except OSError:
        continue
    if hits:
        msg.append("Possible missing Oxford commas (check each; some are two-item pairs):")
        msg += hits
print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "\n".join(msg)}}))
