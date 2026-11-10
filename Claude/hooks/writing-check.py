#!/usr/bin/env python3
"""PostToolUse hook: after Claude writes a .tex file, tell it to re-read the file against the writing rules."""
import json, re, sys

data = json.load(sys.stdin)
path = (data.get("tool_input") or {}).get("file_path", "")
if not path.endswith(".tex"):
    sys.exit(0)

# A list of three or more without the Oxford comma: ", B and C" with no comma before the conjunction.
pattern = re.compile(r",\s[^,;:.()\\]{1,50}[^,\s]\s(and|or)\s")
hits = []
try:
    for n, line in enumerate(open(path, encoding="utf-8"), 1):
        text = line.split("%")[0] if not line.lstrip().startswith("\\bibitem") else ""
        if pattern.search(text):
            hits.append(f"  {n}: {text.strip()[:140]}")
except OSError:
    sys.exit(0)

msg = [f"You just wrote {path}. Before you finish, re-read the whole file against ~/.claude/rules/writing.md and latex.md and fix every violation in the prose: Oxford commas, full sentences instead of fragments joined by colons or semicolons, positive statements instead of absences, every term explained where it first appears, sources cited with links, and no layout changes."]
if hits:
    msg.append("Possible missing Oxford commas (check each; some are two-item pairs):")
    msg += hits
print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "\n".join(msg)}}))
