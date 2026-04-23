#!/usr/bin/env python3
"""
Pre-commit hook — blocks PII-like patterns in staged planning/ files.
Complements gitleaks (which catches credentials); this catches conceptually
sensitive content: real emails, phone numbers, .internal URLs.
planning/private/ is gitignored and excluded from this check.
"""
import re, subprocess, sys

staged = subprocess.check_output(
    ["git", "diff", "--cached", "--name-only"], text=True
).splitlines()

files = [
    f for f in staged
    if f.startswith("planning/") and not f.startswith("planning/private/")
]
if not files:
    sys.exit(0)

content = ""
for f in files:
    try:
        content += subprocess.check_output(["git", "show", f":{f}"], text=True)
    except subprocess.CalledProcessError:
        pass

patterns = [
    (r"[a-zA-Z0-9._%+-]+@(?!example\.com)[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "non-example.com email"),
    (r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b", "phone number"),
    (r"\b[\w-]+\.internal\b", ".internal URL"),
]

fail = False
for pattern, label in patterns:
    if re.search(pattern, content):
        print(f"planning-content-scan: {label} detected in planning/", file=sys.stderr)
        fail = True

sys.exit(1 if fail else 0)
