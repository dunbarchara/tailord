#!/usr/bin/env python3
"""
PostToolUse hook — runs tsc or ruff after Claude edits a file.
Configured in .claude/settings.local.json (not tracked).
Runs on all file edits in frontend/ or backend/ — tsc is a full project
check so it catches cross-file type errors, not just the edited file.
"""
import json, subprocess, sys

d = json.load(sys.stdin)
f = d.get("tool_input", {}).get("file_path", "")
if not f:
    sys.exit(0)

root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()

if f.startswith(root + "/frontend/"):
    r = subprocess.run(
        ["npx", "tsc", "--noEmit"], cwd=root + "/frontend",
        capture_output=True, text=True
    )
    if r.returncode != 0:
        print(r.stdout[-800:] or r.stderr[-800:])

elif f.startswith(root + "/backend/") and f.endswith(".py"):
    r = subprocess.run(
        ["uv", "run", "ruff", "check", f], cwd=root + "/backend",
        capture_output=True, text=True
    )
    if r.returncode != 0:
        print(r.stdout or r.stderr)
