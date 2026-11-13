#!/usr/bin/env python3
"""
alias: install_statusline
version: 1.0
purpose: Installs the p4cc statusline script and activates it in ~/.claude/settings.json (dry-run capable)
plugin: p4cc-statusline
"""

"""
Usage:
    python3 install.py [--dry-run] [--json] [--yes] [--home DIR]

Does exactly what the p4cc-statusline:install skill describes:
  1. copies <plugin>/statusline/statusline-command.sh to ~/.claude/statusline-command.sh and makes it executable
  2. adds or updates the "statusLine" block in ~/.claude/settings.json (a minimal patch: every other key and the
     file's indentation are preserved)

--dry-run  resolve everything, write NOTHING, print the exact plan (DRY lines) and end with RESUMEN|DRY|...
--yes      overwrite a *different* existing statusLine value (without it the install stops with exit 3 so the
           skill can ask the person first)
--home DIR replaces ~ (same as P4CC_HOME)
--json     machine-readable output

Output: `STATE|ID|detail` lines and a final `RESUMEN|<OK|DRY>|<n> operations`. STATE is OK, DRY, INFO or WARN.
Exit codes: 0 · 1 failure · 2 bad usage · 3 precondition not met (script missing, settings.json invalid, or a
different statusLine value exists and --yes was not given).

Write scope: this skill's purpose is to configure the user's Claude Code, so — unlike the other p4cc skills — it
writes the two files above under ~/.claude/ (never the plugin cache). Before modifying an existing file it keeps
a copy next to it, `<file>.p4cc-bak-<timestamp>` (mode 0600), and prints where.
"""

import argparse
import datetime as dt
import json
import os
import re
import shutil
import sys
from pathlib import Path

EXIT_OK, EXIT_FAIL, EXIT_USAGE, EXIT_PRECOND = 0, 1, 2, 3
DESIRED = {"type": "command", "command": "bash ~/.claude/statusline-command.sh"}
SRC = Path(__file__).resolve().parent / "statusline-command.sh"


def detect_indent(text):
    m = re.search(r"^(\s+)\"", text, re.M)
    return len(m.group(1).replace("\t", "    ")) if m else 2


def main(argv=None):
    ap = argparse.ArgumentParser(prog="install.py")
    ap.add_argument("--dry-run", action="store_true", dest="dry")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--home")
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return EXIT_USAGE if e.code not in (0, None) else EXIT_OK
    home = Path(a.home or os.environ.get("P4CC_HOME") or Path.home()).expanduser().resolve()
    claude = home / ".claude"
    dst, settings = claude / "statusline-command.sh", claude / "settings.json"
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    if not SRC.is_file():
        print(f"FAIL|precondition|statusline script not found at {SRC}")
        return EXIT_PRECOND

    ops, info = [], []           # ops: (kind, path, detail, payload)
    # ---- 1. the script
    src_bytes = SRC.read_bytes()
    if not dst.exists():
        ops.append(("create", dst, "statusline script", src_bytes))
    elif dst.read_bytes() != src_bytes:
        ops.append(("backup", dst, f"previous script kept as {dst.name}.p4cc-bak-{stamp}", None))
        ops.append(("modify", dst, "statusline script updated", src_bytes))
    elif not os.access(dst, os.X_OK):
        ops.append(("modify", dst, "mark executable", src_bytes))
    # ---- 2. settings.json
    data, indent, raw = {}, 2, ""
    if settings.exists():
        raw = settings.read_text(encoding="utf-8")
        try:
            data = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError as e:
            print(f"FAIL|precondition|{settings} is not valid JSON ({e}); fix it first")
            return EXIT_PRECOND
        indent = detect_indent(raw)
    cur = data.get("statusLine")
    if cur == DESIRED:
        info.append("settings.json already has this statusLine")
    else:
        if cur not in (None, {}) and not a.yes:
            print(f"FAIL|precondition|{settings} already has a different statusLine ({json.dumps(cur)}); "
                  "ask the person and re-run with --yes to overwrite it")
            return EXIT_PRECOND
        new = dict(data)
        new["statusLine"] = DESIRED
        text = json.dumps(new, indent=indent, ensure_ascii=False) + "\n"
        if settings.exists():
            ops.append(("backup", settings, f"previous settings kept as {settings.name}.p4cc-bak-{stamp}", None))
        ops.append(("modify" if settings.exists() else "create", settings,
                    "statusLine overwritten" if cur not in (None, {}) else "statusLine activated", text.encode("utf-8")))

    mode = "DRY" if a.dry else "OK"
    if not a.dry:
        for kind, path, detail, payload in ops:
            if kind == "backup":
                bak = path.with_name(f"{path.name}.p4cc-bak-{stamp}")
                shutil.copy2(path, bak)
                os.chmod(bak, 0o600)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(payload)
                if path == dst:
                    os.chmod(path, 0o755)
    real = [o for o in ops]
    if a.json:
        print(json.dumps({"plugin": "p4cc-statusline", "command": "install", "mode": "dry-run" if a.dry else "apply",
                          "ops": [{"op": k, "path": str(p), "detail": d} for k, p, d, _ in real], "info": info,
                          "summary": {"mode": mode, "ops": len(real)}}, indent=2, ensure_ascii=False))
    else:
        for k, p, d, _ in real:
            print(f"{mode}|{k}|{p} ({d})")
        for i in info:
            print(f"INFO|install|{i}")
        if not real:
            print("INFO|install|everything is already in place")
        print(f"RESUMEN|{mode}|{len(real)} operations")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
