#!/usr/bin/env python3
"""After an assistant writes a .tex file, tell it to re-read the file against the writing rules.

Claude Code and Codex call it as a PostToolUse hook with JSON on stdin; the OpenCode plugin
sends it the same JSON. Claude's Write and Edit name the file in tool_input.file_path;
Codex's apply_patch names each file in its patch text, in tool_input.command. A shell command
(tool Bash) names no file, so after one the script takes the .tex files that changed in the last
minutes, under the working folder and under every folder the command names. Each version of a
file is reported once.
"""
import json, os, re, sys, time

RECENT = 600  # seconds: a .tex file changed this recently was written by the shell command
SEEN = os.path.expanduser("~/.cache/writing-check.json")  # the versions already reported
DEPTH = 3    # folders below the working folder to look in

data = json.load(sys.stdin)
tool_input = data.get("tool_input") or {}
paths = [tool_input["file_path"]] if tool_input.get("file_path") else []
paths += re.findall(r"^\*\*\* (?:Add|Update) File: (.+)$", tool_input.get("command") or "", re.M)
if data.get("tool_name") == "Bash":
    cwd = data.get("cwd") or os.getcwd()
    home = os.path.expanduser("~")
    roots = [cwd]
    # every folder the command names: cd ~/x, git -C /y, python3 ~/z/file.py
    for word in re.findall(r"(?:~|\$HOME|/)[^\s'\"`;&|<>()]*", tool_input.get("command") or ""):
        r = os.path.expanduser(word.replace("$HOME", "~", 1))
        r = r if os.path.isdir(r) else os.path.dirname(r)
        if os.path.isdir(r) and os.path.realpath(r) not in ("/", home, os.path.dirname(home)):
            roots.append(r)
    try:
        seen = json.load(open(SEEN))
    except (OSError, ValueError):
        seen = {}
    now = time.time()
    for root in dict.fromkeys(os.path.realpath(r) for r in roots):
        for folder, dirs, files in os.walk(root):
            if folder[len(root):].count(os.sep) >= DEPTH:
                dirs[:] = []
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "build"]
            for f in files:
                p = os.path.join(folder, f)
                try:
                    changed = os.path.getmtime(p) if f.endswith(".tex") else 0
                except OSError:
                    continue
                if now - changed < RECENT and seen.get(p) != changed:
                    paths.append(p)
                    seen[p] = changed
    try:
        os.makedirs(os.path.dirname(SEEN), exist_ok=True)
        json.dump({p: m for p, m in seen.items() if now - m < 86400}, open(SEEN, "w"))
    except OSError:
        pass
paths = list(dict.fromkeys(paths))
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
