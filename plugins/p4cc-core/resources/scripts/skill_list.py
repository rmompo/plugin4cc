#!/usr/bin/env python3
"""
alias: skill_list
version: 1.0
purpose: Lists the p4cc-* skills installed in the Claude Code cache (read-only)
plugin: p4cc-core
"""

"""
Usage:
    python3 skill_list.py [--json | --table] [--home DIR]

Default output: one line per skill, `STATE|ID|detail`, then `RESUMEN|<n> FAIL|<m> WARN`.
    ID      <plugin>:<skill>
    STATE   OK   the skill has no missing dependency (or it is install/check, whose `ready` is intentionally empty)
            WARN a declared dependency (tool or plugin) is missing
    detail  v<version> ready=<yes|no|n/a> enabled=<yes|no> — <description up to ". Also invoked">
--json   {plugin, skill, findings: [{estado, id, detalle, componente}], summary: {fail, warn}}
--table  the human presentation (Unicode table + footer), fed by the same findings

The skill version always comes from the catalog (the source of truth), never from the SKILL.md frontmatter.
Read-only: it never writes anything. Exit codes: 0 · 1 failures · 2 bad usage · 3 precondition not met
(no plugin cache found). Missing dependencies are WARN, so a normal listing exits 0.
"""

import argparse
import json
import os
import re
import shutil
import sys
import textwrap
from pathlib import Path

EXIT_OK, EXIT_FAIL, EXIT_USAGE, EXIT_PRECOND = 0, 1, 2, 3
EMOJI = "🟢🔴✅❌"


def dw(s):
    """Terminal display width: the status emojis take two columns."""
    return len(s) + sum(1 for c in s if c in EMOJI)


def vkey(v):
    return tuple(int(x) for x in re.findall(r"\d+", v))


def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    return m.group(1) if m else ""


def fm_get(fm, key):
    m = re.search(rf"^{key}:[ \t]*(.*)$", fm, re.M)
    return m.group(1).strip().strip("\"'") if m else ""


def load(home, marketplace="plugin4cc"):
    cache = home / ".claude" / "plugins" / "cache" / marketplace
    catalog = home / ".p4cc" / "catalog.json"
    if not catalog.is_file():
        catalog = home / ".claude" / "plugins" / "marketplaces" / marketplace / "specs" / "catalog.json"
    cat = json.load(open(catalog)) if catalog.is_file() else {"plugins": []}
    return cache, cat


def dep_ok(dep, cache):
    if dep.get("type") == "plugin":
        d = cache / dep["name"]
        return d.is_dir() and any(d.iterdir())
    return shutil.which(dep["name"]) is not None


def collect(home):
    cache, cat = load(home)
    if not cache.is_dir():
        return None, []
    rows = []
    for pdir in sorted(p for p in cache.iterdir() if p.is_dir() and p.name.startswith("p4cc-")):
        versions = [v.name for v in pdir.iterdir() if v.is_dir() and re.fullmatch(r"\d+\.\d+\.\d+", v.name)]
        if not versions:
            continue
        ver = max(versions, key=vkey)
        base = pdir / ver
        centry = next((p for p in cat["plugins"] if p["name"] == pdir.name), {})
        pdeps = centry.get("dependencies") or []
        for sdir in sorted(s for s in (base / "skills").iterdir() if s.is_dir()) if (base / "skills").is_dir() else []:
            md = sdir / "SKILL.md"
            fm = frontmatter(md.read_text(encoding="utf-8")) if md.is_file() else ""
            name = fm_get(fm, "name") or sdir.name
            sentry = next((s for s in centry.get("skills", []) if s["name"] == name), {})
            deps = sentry.get("dependencies") or pdeps
            circular = name in ("install", "check")
            ready = None if circular else all(dep_ok(d, cache) for d in deps)
            rows.append({"plugin": pdir.name, "plugin_version": ver, "skill": name, "version": sentry.get("version", "?"),
                         "enabled": md.is_file(), "ready": ready,
                         "description": re.split(r"\.\s+Also invoked", fm_get(fm, "description"))[0].rstrip(".")})
    return cat, rows


def findings(rows):
    out = []
    for r in rows:
        ready = "n/a" if r["ready"] is None else ("yes" if r["ready"] else "no")
        out.append({"estado": "WARN" if r["ready"] is False else "OK", "id": f"{r['plugin']}:{r['skill']}",
                    "componente": r["plugin"],
                    "detalle": f"v{r['version']} ready={ready} enabled={'yes' if r['enabled'] else 'no'} — {r['description']}".replace("|", "/")})
    return out


def table(rows):
    groups = {}
    for r in rows:
        groups.setdefault((r["plugin"], r["plugin_version"]), []).append(r)
    cells = [("plugin", [], 0), ("skill", [], 0), ("v", [], 0), ("ready", [], 0)]
    pl = [f"🟢 {p}" for p, _ in groups] + [f"(v{v})" for _, v in groups]
    sk = [f"{'🟢' if r['enabled'] else '🔴'} {r['skill']}" for r in rows]
    vs = [str(r["version"]) for r in rows]
    rd = ["✅", "❌"]
    widths = [max(dw(h), max([dw(c) for c in col] or [0])) + 2 for h, col in zip(("plugin", "skill", "v", "ready"), (pl, sk, vs, rd))]
    widths.append(62)

    def pad(c, w):
        return " " + c + " " * (w - 1 - dw(c))

    def ctr(c, w):
        left = (w - dw(c)) // 2
        return " " * left + c + " " * (w - dw(c) - left)

    def line(l, m, r):
        return l + m.join("─" * w for w in widths) + r

    out = [line("┌", "┬", "┐"), "│" + "│".join(ctr(h, w) for h, w in zip(("plugin", "skill", "v", "ready", "description"), widths)) + "│",
           line("├", "┼", "┤")]
    for gi, ((pname, pver), grp) in enumerate(groups.items()):
        phys = 0

        def plug_cell():
            return pad({0: f"{'🟢'} {pname}", 1: f"(v{pver})"}.get(phys, ""), widths[0])

        for si, r in enumerate(grp):
            if si > 0:
                out.append("│" + plug_cell() + "├" + "┼".join("─" * w for w in widths[1:]) + "┤")
                phys += 1
            ready = "" if r["ready"] is None else ("✅" if r["ready"] else "❌")
            desc = textwrap.wrap(r["description"], 60) or [""]
            for k, d in enumerate(desc):
                vals = [f"{'🟢' if r['enabled'] else '🔴'} {r['skill']}", str(r["version"]), ready, d] if k == 0 else ["", "", "", d]
                out.append("│" + plug_cell() + "│" + "│".join(pad(v, w) for v, w in zip(vals, widths[1:])) + "│")
                phys += 1
        out.append(line("├", "┼", "┤") if gi < len(groups) - 1 else line("└", "┴", "┘"))
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="skill_list")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--table", action="store_true")
    ap.add_argument("--home")
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return EXIT_USAGE if e.code not in (0, None) else EXIT_OK
    home = Path(args.home or os.environ.get("P4CC_HOME") or Path.home()).expanduser().resolve()
    cat, rows = collect(home)
    if cat is None:
        print(f"FAIL|precondition|no plugin cache at {home}/.claude/plugins/cache/plugin4cc")
        return EXIT_PRECOND
    fl = findings(rows)
    warns = sum(1 for f in fl if f["estado"] == "WARN")
    if args.json:
        print(json.dumps({"plugin": "p4cc-core", "skill": "skill-list", "findings": fl,
                          "summary": {"fail": 0, "warn": warns}}, indent=2, ensure_ascii=False))
    elif args.table:
        print("```text\n" + table(rows) + "\n```\n")
        plugins = len({r["plugin"] for r in rows})
        enabled = sum(1 for r in rows if r["enabled"])
        print(f"**{plugins} plugins · {len(rows)} skills · {enabled} enabled**")
    else:
        for f in fl:
            print(f"{f['estado']}|{f['id']}|{f['detalle']}")
        print(f"RESUMEN|0 FAIL|{warns} WARN")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
