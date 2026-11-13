#!/usr/bin/env python3
"""
alias: check_engine
version: 1.0
purpose: Shared `check` / `install` engine of the p4cc plugins (identical copy in p4cc-core, p4cc-converter,
         p4cc-ccvv and p4cc-crawler; each plugin ships its own check_config.json next to it)
"""

"""
Usage:
    python3 check_engine.py check   [--json | --table] [--home DIR]
    python3 check_engine.py install [--dry-run] [--json] [--home DIR]

check    read-only. Verifies folders, the global catalog, the files the plugin ships, external tools (with
         version constraints), Python packages and optional components. Never installs anything: for every
         problem it reports the command the person has to run.
install  creates the folders and installs the global catalog copy (~/.p4cc/catalog.json). With --dry-run it
         resolves everything, writes NOTHING and prints the exact plan (DRY). It never installs tools.

Default output: one line per finding, `STATE|ID|detail`, then `RESUMEN|<n> FAIL|<m> WARN`.
STATE is OK, INFO, WARN or FAIL (DRY in `install --dry-run`). IDs are stable across versions
(folder-*, catalog-*, res-*, tool-*, pkg-*, ocr-lang-*, profile-*).
--json   {plugin, skill, findings: [{estado, id, detalle, componente}], summary: {fail, warn}}
--table  the human presentation (Markdown table + how to install what is missing), fed by the same findings
Exit codes: 0 no failures · 1 failures · 2 bad usage · 3 precondition not met.

Write boundaries: only under ~/.p4cc/ (never another marketplace's catalog). Never the Claude Code cache.
"""

import argparse
import importlib.metadata
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

EXIT_OK, EXIT_FAIL, EXIT_USAGE, EXIT_PRECOND = 0, 1, 2, 3
HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parent.parent            # <plugin>/resources/scripts/check_engine.py -> <plugin>
CFG = json.load(open(HERE / "check_config.json"))


def expand(p, home):
    return Path(str(p).replace("~", str(home), 1)) if str(p).startswith("~") else Path(p)


# ---------------------------------------------------------------- versions
def version_of(text):
    m = re.search(r"(\d+(?:\.\d+)+)", text or "")
    return m.group(1) if m else None


def vtuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v))


def satisfies(found, constraint):
    if not constraint or constraint.strip() == "*":
        return True
    f = vtuple(found)
    for tok in constraint.split():
        m = re.match(r"^(>=|<=|>|<|=)?(\d+(?:\.\d+)*)$", tok)
        if not m:
            return True
        op, want = m.group(1) or "=", vtuple(m.group(2))
        n = max(len(f), len(want))
        a, b = f + (0,) * (n - len(f)), want + (0,) * (n - len(want))
        ok = {">=": a >= b, "<=": a <= b, ">": a > b, "<": a < b, "=": a == b}[op]
        if not ok:
            return False
    return True


def run_version(cmd, args):
    try:
        r = subprocess.run([cmd] + args, capture_output=True, text=True, timeout=15)
        return version_of((r.stdout or "") + "\n" + (r.stderr or ""))
    except Exception:
        return None


def os_key():
    s = platform.system()
    if s == "Darwin":
        return "brew"
    if s == "Windows":
        return "winget"
    try:
        txt = open("/etc/os-release").read().lower()
        if re.search(r"debian|ubuntu", txt):
            return "apt"
        if re.search(r"fedora|rhel|centos|rocky|almalinux", txt):
            return "dnf"
    except OSError:
        pass
    return "apt"


def hint(install):
    if not install:
        return ""
    k = os_key()
    return install.get(k) or install.get("pip") or next(iter(install.values()))


# ---------------------------------------------------------------- catalog helpers
def marketplace_catalog(home):
    base = home / ".claude" / "plugins" / "marketplaces"
    for c in sorted(base.glob("*/specs/catalog.json")) if base.is_dir() else []:
        try:
            if json.load(open(c)).get("name") == CFG.get("marketplace", "plugin4cc"):
                return c
        except Exception:
            continue
    return None


def catalog_deps(home):
    """Dependency constraints from the global catalog (source of truth), falling back to the config."""
    out = {}
    for c in (home / ".p4cc" / "catalog.json", marketplace_catalog(home)):
        if c and Path(c).is_file():
            try:
                d = json.load(open(c))
                p = next((x for x in d.get("plugins", []) if x["name"] == CFG["plugin"]), None)
                for dep in (p or {}).get("dependencies", []) or []:
                    if dep.get("type") == "tool":
                        out[dep["name"]] = dep.get("version", "*")
                return out
            except Exception:
                continue
    return out


# ---------------------------------------------------------------- findings
def F(estado, fid, detalle, comp, **extra):
    d = {"estado": estado, "id": fid, "detalle": detalle, "componente": comp}
    d.update({k: v for k, v in extra.items() if v is not None})
    return d


def check(home):
    out, deps = [], catalog_deps(home)
    inst = f"/{CFG['plugin']}:install"
    # folders
    for p in CFG.get("folders", []):
        path = expand(p, home)
        out.append(F("OK", f"folder-{Path(p).name.lstrip(".")}", f"{p} exists", "folders") if path.is_dir()
                   else F("FAIL", f"folder-{Path(p).name.lstrip(".")}", f"{p} is missing — run {inst}", "folders", fix=inst))
    # global catalog
    gc = home / ".p4cc" / "catalog.json"
    if not gc.is_file():
        out.append(F("FAIL", "catalog-installed", f"~/.p4cc/catalog.json is missing — run {inst}", "catalog", fix=inst))
    else:
        try:
            ok = json.load(open(gc)).get("name") == CFG.get("marketplace", "plugin4cc")
            out.append(F("OK", "catalog-installed", "~/.p4cc/catalog.json is valid", "catalog") if ok else
                       F("FAIL", "catalog-installed", "~/.p4cc/catalog.json belongs to another marketplace", "catalog"))
        except Exception:
            out.append(F("FAIL", "catalog-installed", f"~/.p4cc/catalog.json is not valid JSON — run {inst}", "catalog", fix=inst))
        src = marketplace_catalog(home)
        if src and gc.read_bytes() != Path(src).read_bytes():
            out.append(F("WARN", "catalog-fresh", f"~/.p4cc/catalog.json differs from the marketplace copy — run {inst}", "catalog", fix=inst))
        elif src:
            out.append(F("OK", "catalog-fresh", "catalog copy is up to date", "catalog"))
    # shipped files
    for r in CFG.get("resources", []):
        ok = (PLUGIN_ROOT / r).is_file()
        out.append(F("OK", f"res-{Path(r).name}", f"{r} present", "resources") if ok else
                   F("FAIL", f"res-{Path(r).name}", f"{r} missing (broken plugin install) — /plugin → update the marketplace and {CFG['plugin']}", "resources"))
    # ccvv profiles
    prof = CFG.get("profiles")
    if prof:
        root = expand(prof["root"], home)
        dirs = sorted(d for d in root.iterdir() if d.is_dir()) if root.is_dir() else []
        if not dirs:
            out.append(F("INFO", "profile-none", "no profiles created yet", "profiles"))
        for d in dirs:
            for sub in prof["subdirs"]:
                out.append(F("OK", f"profile-{d.name}-{sub}", f"{d.name}/{sub}/ exists", "profiles") if (d / sub).is_dir() else
                           F("WARN", f"profile-{d.name}-{sub}", f"{d.name}/{sub}/ missing — repaired by /{CFG['plugin']}:profile-gather", "profiles"))
    # tools
    for t in CFG.get("tools", []):
        want = deps.get(t["id"], t.get("required", "*"))
        lvl = "FAIL" if t.get("level", "required") == "required" else "WARN"
        used = f" (used by {t['used_by']})" if t.get("used_by") else ""
        reqtxt = lambda w: ("required " + w) if t.get("level", "required") == "required" else "optional"
        if not shutil.which(t["cmd"]):
            out.append(F(lvl, f"tool-{t['id']}", f"missing, {reqtxt(want)}{used} — install: {hint(t.get('install'))}", "tools",
                         required=want, found="-", install=t.get("install")))
            continue
        v = run_version(t["cmd"], t.get("version_args", ["--version"]))
        if v and not satisfies(v, want):
            out.append(F(lvl, f"tool-{t['id']}", f"found {v}, required {want}{used} — upgrade: {hint(t.get('install'))}", "tools",
                         required=want, found=v, install=t.get("install")))
        else:
            out.append(F("OK", f"tool-{t['id']}", f"found {v or 'present'}, {reqtxt(want)}{used}", "tools", required=want, found=v or "present"))
    # python packages
    for p in CFG.get("python_packages", []):
        lvl = "FAIL" if p.get("level", "required") == "required" else "WARN"
        if importlib.util.find_spec(p["module"]) is None:
            out.append(F(lvl, f"pkg-{p['id']}", f"missing ({p.get('level', 'required')}, {p.get('used_by', '')}) — install: {hint(p.get('install'))}".replace(", )", ")"),
                         "python packages", required=p.get("level", "required"), found="-", install=p.get("install")))
        else:
            try:
                v = importlib.metadata.version(p.get("dist", p["id"]))
            except Exception:
                v = "present"
            out.append(F("OK", f"pkg-{p['id']}", f"found {v}", "python packages", required=p.get("level", "required"), found=v))
    # tesseract languages
    tl = CFG.get("tesseract_langs")
    if tl and shutil.which("tesseract"):
        want = (os.environ.get(tl["env"]) or tl["default"]).split("+")
        try:
            have = set(subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True, timeout=15).stdout.split()[1:])
        except Exception:
            have = set()
        for lang in want:
            out.append(F("OK", f"ocr-lang-{lang}", f"tesseract language '{lang}' installed", "ocr") if lang in have else
                       F("WARN", f"ocr-lang-{lang}", f"tesseract language '{lang}' missing — install: sudo apt install tesseract-ocr-{lang}", "ocr",
                         install={"apt": f"sudo apt install tesseract-ocr-{lang}"}))
    return out


# ---------------------------------------------------------------- output
def summary(findings):
    return (sum(1 for f in findings if f["estado"] == "FAIL"), sum(1 for f in findings if f["estado"] == "WARN"))


def emit(findings, args):
    fails, warns = summary(findings)
    if args.json:
        print(json.dumps({"plugin": CFG["plugin"], "skill": args.command,
                          "findings": [{k: v for k, v in f.items() if k in ("estado", "id", "detalle", "componente")} for f in findings],
                          "summary": {"fail": fails, "warn": warns}}, indent=2, ensure_ascii=False))
    elif getattr(args, "table", False):
        icon = {"OK": "✅", "FAIL": "❌", "WARN": "⚠️", "INFO": "ℹ️", "DRY": "…"}
        print(f"```\n══════════════════════════════════════════\n  {CFG['plugin']} CHECK\n══════════════════════════════════════════\n```\n")
        print("| Area | Item | Required | Found | Status |\n|------|------|----------|-------|--------|")
        for f in findings:
            print(f"| {f['componente']} | `{f['id']}` | {f.get('required', '')} | {f.get('found', '')} | {icon.get(f['estado'], '')} |")
        todo = [f for f in findings if f["estado"] in ("FAIL", "WARN")]
        if todo:
            print("\n### How to install / fix what is missing\n")
            for f in todo:
                print(f"- `{f['id']}`: {f['detalle']}")
                for k, cmd in (f.get("install") or {}).items():
                    print(f"  - {k}: `{cmd}`")
        print(f"\nRESUMEN: {fails} FAIL · {warns} WARN")
    else:
        for f in findings:
            print(f"{f['estado']}|{f['id']}|{f['detalle']}")
        print(f"RESUMEN|{fails} FAIL|{warns} WARN")
    return EXIT_FAIL if fails else EXIT_OK


# ---------------------------------------------------------------- install (plan + apply in ONE place)
def install(home, dry, args):
    p4cc = (home / ".p4cc").resolve()
    ops = []

    def inside(p):
        p = Path(p).resolve()
        if p != p4cc and p4cc not in p.parents:
            raise PermissionError(f"refusing to write outside ~/.p4cc: {p}")
        return p

    for p in CFG.get("folders", []):
        d = inside(expand(p, home))
        if not d.is_dir():
            ops.append(("create", d, "folder", None))
    prof = CFG.get("profiles")
    if prof:
        d = inside(expand(prof["root"], home))
        if not d.is_dir():
            ops.append(("create", d, "profiles root", None))
    notes = []
    src = marketplace_catalog(home)
    if src:
        dst = inside(home / ".p4cc" / "catalog.json")
        if dst.exists():
            try:
                owner_ok = json.load(open(dst)).get("name") == CFG.get("marketplace", "plugin4cc")
            except Exception:
                owner_ok = True          # unreadable: it is our own (plugin4cc) file slot, replace it
            if not owner_ok:
                notes.append("~/.p4cc/catalog.json belongs to another marketplace: left untouched")
            elif dst.read_bytes() != Path(src).read_bytes():
                ops.append(("modify", dst, "catalog copy", Path(src)))
        else:
            ops.append(("create", dst, "catalog copy", Path(src)))
    else:
        notes.append("marketplace catalog not found — add the marketplace first: claude plugins marketplace add rmompo/plugin4cc")
    mode = "DRY" if dry else "OK"
    if not dry:
        for kind, path, what, srcf in ops:
            if what == "catalog copy":
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(srcf, path)
            else:
                path.mkdir(parents=True, exist_ok=True)
    if args.json:
        print(json.dumps({"plugin": CFG["plugin"], "command": "install", "mode": "dry-run" if dry else "apply",
                          "ops": [{"op": k, "path": str(p), "detail": w} for k, p, w, _ in ops], "notes": notes,
                          "summary": {"mode": mode, "ops": len(ops)}}, indent=2, ensure_ascii=False))
    else:
        for k, p, w, _ in ops:
            print(f"{mode}|{k}|{p} ({w})")
        for n in notes:
            print(f"WARN|note|{n}")
        if not ops:
            print("INFO|install|everything is already in place")
        print(f"RESUMEN|{mode}|{len(ops)} operations")
    return EXIT_OK


def main(argv=None):
    ap = argparse.ArgumentParser(prog="check_engine")
    ap.add_argument("command", choices=["check", "install"])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--table", action="store_true")
    ap.add_argument("--dry-run", action="store_true", dest="dry_run")
    ap.add_argument("--home")
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return EXIT_USAGE if e.code not in (0, None) else EXIT_OK
    if args.dry_run and args.command != "install":
        print("usage error: --dry-run only applies to install (check is always read-only)", file=sys.stderr)
        return EXIT_USAGE
    home = Path(args.home or os.environ.get("P4CC_HOME") or Path.home()).expanduser().resolve()
    if not PLUGIN_ROOT.is_dir():
        print("FAIL|precondition|cannot locate the plugin root")
        return EXIT_PRECOND
    try:
        if args.command == "check":
            return emit(check(home), args)
        return install(home, args.dry_run, args)
    except PermissionError as e:
        print(f"FAIL|precondition|{e}")
        return EXIT_PRECOND


if __name__ == "__main__":
    sys.exit(main())
