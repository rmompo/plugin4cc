#!/usr/bin/env python3
"""
alias: p4cc_ops
version: 1.0
purpose: Deterministic engine behind the p4cc-plugin skills (create, update, remove, skill-add,
         skill-update, skill-remove, skill-doctor, doc-doctor). One code path for dry-run and apply.
plugin: p4cc-plugin
"""

"""
Usage:
    python3 p4cc_ops.py <command> [options]

Commands:
    env            resolve repo / marketplace / catalog / global catalog (read-only)
    skill-update   bump a skill (Z+1) and record the change
    skill-add      add a skill to an existing plugin
    skill-remove   remove a skill from a plugin (Z unchanged)
    update         update plugin metadata (description, status, version bump)
    remove         remove a plugin completely
    create         scaffold a new plugin
    doctor         audit skills (C1..C10), optionally fix [auto] defects
    doc-audit      audit documentation (D1..D9), optionally fix [auto] defects

Options shared by every command:
    --repo PATH     marketplace repo (same as P4CC_REPO; the flag wins when both are given)
    --home DIR      home directory used for ~/.p4cc and ~/.claude (same as P4CC_HOME; default: $HOME)
    --dry-run       resolve and validate everything, write NOTHING, print the exact plan (DRY)
    --json          machine-readable output
    --allow-dirty   skip the "uncommitted changes in the files to modify" check
    --yes           skip confirmations that would remain

Output (default): one line per item, `STATE|ID|detail`, then a final `RESUMEN|...` line.
STATE is one of OK, INFO, WARN, FAIL, DRY.
Exit codes: 0 no failures · 1 failures found · 2 bad usage · 3 precondition not met.

Write boundaries: only inside REPO_ROOT, the single file GLOBAL_CATALOG under ~/.p4cc/ (never another
marketplace's) and <REPO_ROOT>/.p4cc/bak/. NEVER the Claude Code cache. Nothing is ever installed.
"""

import argparse
import copy
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

EXIT_OK, EXIT_FAIL, EXIT_USAGE, EXIT_PRECOND = 0, 1, 2, 3
MP = ".claude-plugin/marketplace.json"


class Usage(Exception):
    pass


class Precondition(Exception):
    def __init__(self, msg, payload=None):
        super().__init__(msg)
        self.payload = payload or {}


def dumps(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


# --------------------------------------------------------------------------------------------------
# Environment (Step 0)
# --------------------------------------------------------------------------------------------------
class Env:
    pass


def _git_root(cwd):
    try:
        return subprocess.check_output(["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
                                       stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return None


def resolve_env(repo_arg=None, home_arg=None):
    home = Path(home_arg or os.environ.get("P4CC_HOME") or Path.home()).expanduser().resolve()
    cwd = Path.cwd()
    has_mp = lambda p: (Path(p) / MP).is_file()
    cwd_repo = _git_root(cwd)
    cwd_repo = cwd_repo if cwd_repo and has_mp(cwd_repo) else None
    repo, via, notes = None, None, []

    explicit = repo_arg or os.environ.get("P4CC_REPO")
    if explicit:
        src = "--repo" if repo_arg else "env P4CC_REPO"
        if not has_mp(Path(explicit).expanduser()):
            raise Precondition(f"{src}={explicit} does not contain {MP}")
        repo, via = Path(explicit).expanduser().resolve(), src
        if cwd_repo and Path(cwd_repo).resolve() != repo:
            notes.append(f"{src} ({repo}) differs from the marketplace repo of the current directory ({cwd_repo})")
    if not repo and cwd_repo:
        repo, via = Path(cwd_repo).resolve(), "git root of cwd"
    if not repo:
        for d in [cwd, *cwd.parents]:
            if has_mp(d):
                repo, via = d.resolve(), "walk-up from cwd"
                break
    if not repo:
        res = subprocess.run(
            ["find", str(home), "-maxdepth", "6", "(", "-name", "node_modules", "-o", "-name", ".git", "-o",
             "-path", str(home / ".claude"), ")", "-prune", "-o", "-type", "f", "-path",
             "*/.claude-plugin/marketplace.json", "-print"], capture_output=True, text=True)
        cands = sorted({str(Path(l).parent.parent) for l in res.stdout.splitlines() if l.strip()})
        if len(cands) > 1:
            raise Precondition("several marketplace repos found; pass --repo", {"status": "ambiguous", "candidates": cands})
        if not cands:
            raise Precondition("no .claude-plugin/marketplace.json found; run inside the marketplace repo or pass --repo")
        repo, via = Path(cands[0]), "find (last resort)"
        notes.append("repo located by the last-resort search")

    try:
        mp = json.load(open(repo / MP))
    except Exception as e:
        raise Precondition(f"cannot read {repo / MP}: {e}")
    if not mp.get("name"):
        raise Precondition(f"{repo / MP} has no 'name' field")

    e = Env()
    e.home, e.repo, e.via, e.mp, e.marketplace = home, repo, via, mp, mp["name"]
    e.catalog_path = repo / "specs" / "catalog.json"
    e.catalog_exists = e.catalog_path.is_file()
    e.docs_language, cat_name = "en", None
    if e.catalog_exists:
        try:
            cj = json.load(open(e.catalog_path))
        except Exception as ex:
            raise Precondition(f"cannot parse {e.catalog_path}: {ex}")
        e.docs_language, cat_name = cj.get("docs_language", "en"), cj.get("name")
        if cat_name and cat_name != e.marketplace:
            notes.append(f"catalog name '{cat_name}' differs from marketplace name '{e.marketplace}'")
    e.cache_base = home / ".claude" / "plugins" / "cache" / e.marketplace          # read-only
    e.global_catalog = home / ".p4cc" / ("catalog.json" if e.marketplace == "plugin4cc" else f"catalog-{e.marketplace}.json")
    e.global_writable = True
    if e.global_catalog.exists():
        try:
            e.global_writable = json.load(open(e.global_catalog)).get("name") == e.marketplace
        except Exception:
            e.global_writable = False
        if not e.global_writable:
            notes.append(f"{e.global_catalog} belongs to another marketplace (or is unreadable): it will NOT be touched")
    try:
        e.remote = subprocess.check_output(["git", "-C", str(repo), "remote", "get-url", "origin"],
                                           stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        e.remote = None
    e.notes = notes
    return e


def env_dict(e):
    return {"status": "ok", "REPO_ROOT": str(e.repo), "MARKETPLACE": e.marketplace, "resolved_via": e.via,
            "CATALOG": str(e.catalog_path), "catalog_exists": e.catalog_exists, "docs_language": e.docs_language,
            "CACHE_BASE": str(e.cache_base), "GLOBAL_CATALOG": str(e.global_catalog),
            "GLOBAL_CATALOG_WRITABLE": e.global_writable, "git_remote": e.remote,
            "confirm_needed": bool(e.notes), "notes": e.notes}


def require_catalog(e):
    if not e.catalog_exists:
        raise Precondition(f"specs/catalog.json does not exist in marketplace '{e.marketplace}'. "
                           "Run /p4cc-plugin:skill-doctor: its bootstrap builds it from the existing plugins.")
    return json.load(open(e.catalog_path))


# --------------------------------------------------------------------------------------------------
# Plan: the ONE place that decides whether anything is written
# --------------------------------------------------------------------------------------------------
class Plan:
    def __init__(self, env, dry, backup=False, check_dirty=False, allow_dirty=False):
        self.env, self.dry, self.backup = env, dry, backup
        self.check_dirty, self.allow_dirty = check_dirty, allow_dirty
        self.ops, self.warnings, self.bak_dir = [], [], None
        self._stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")

    # ---- boundaries
    def _rel(self, path):
        p = Path(path).resolve()
        repo = self.env.repo.resolve()
        if self.env.cache_base.resolve() in p.parents or p == self.env.cache_base.resolve():
            raise Precondition(f"refusing to write to the Claude Code cache: {p}")
        if p == self.env.global_catalog.resolve():
            if not self.env.global_writable:
                return None                       # silently skipped: belongs to another marketplace
            return str(p)
        if p == repo or repo in p.parents:
            return str(p.relative_to(repo))
        raise Precondition(f"refusing to write outside the allowed locations: {p}")

    def _add(self, kind, path, detail="", data=None):
        rel = self._rel(path)
        if rel is None:
            self.warnings.append(f"{self.env.global_catalog} belongs to another marketplace — left untouched")
            return
        self.ops.append({"op": kind, "path": rel, "abs": str(Path(path).resolve()), "detail": detail, "data": data})

    # ---- operations (recorded, never executed here)
    def write_bytes(self, path, data, detail=""):
        p = Path(path)
        if p.exists() and p.read_bytes() == data:
            return
        self._add("modify" if p.exists() else "create", p, detail, data)

    def write_text(self, path, text, detail=""):
        self.write_bytes(path, text.encode("utf-8"), detail)

    def write_json(self, path, obj, detail=""):
        self.write_text(path, dumps(obj), detail)

    def delete(self, path, detail=""):
        if Path(path).exists():
            self._add("delete", path, detail)

    def sync_global_catalog(self, catalog_obj):
        self.write_json(self.env.global_catalog, catalog_obj, "global catalog copy")

    # ---- the decision point
    def _dirty_files(self):
        rels = [o["path"] for o in self.ops if o["op"] in ("modify", "delete") and not os.path.isabs(o["path"])]
        if not rels:
            return []
        try:
            out = subprocess.check_output(["git", "-C", str(self.env.repo), "status", "--porcelain", "--"] + rels,
                                          stderr=subprocess.DEVNULL, text=True)
        except Exception:
            return []
        return [l[3:] for l in out.splitlines() if l and not l.startswith("??")]

    def _bak_target(self):
        return self.env.repo / ".p4cc" / "bak" / self._stamp

    def _bak_ignored(self):
        probe = ".p4cc/bak/x"
        try:
            return subprocess.run(["git", "-C", str(self.env.repo), "check-ignore", "-q", probe],
                                  stderr=subprocess.DEVNULL).returncode == 0
        except Exception:
            return True

    def run(self):
        """Validate, back up, and (unless dry-run) apply. Returns a result dict."""
        dirty = []
        if self.check_dirty and not self.allow_dirty:
            dirty = self._dirty_files()
        touched = [o for o in self.ops if o["op"] in ("modify", "delete") and Path(o["abs"]).exists()
                   and not os.path.isabs(o["path"])]
        res = {"repo": str(self.env.repo), "mode": "DRY" if self.dry else "OK", "ops": [{k: o[k] for k in ("op", "path", "detail")} for o in self.ops],
               "backup": None, "warnings": list(self.warnings), "dirty": dirty}
        if self.backup and touched:
            res["backup"] = str(self._bak_target())
            if not self._bak_ignored():
                res["warnings"].append(".p4cc/bak/ is not ignored by git: add '.p4cc/' to .gitignore or .git/info/exclude")
        if dirty:
            raise Precondition("uncommitted changes in files that would be modified: " + ", ".join(dirty)
                               + " (commit/stash them or pass --allow-dirty)", {"result": res})
        if self.dry:
            return res
        try:
            if res["backup"]:
                self._make_backup(touched)
            for o in self.ops:
                p = Path(o["abs"])
                if o["op"] == "delete":
                    shutil.rmtree(p) if p.is_dir() else p.unlink()
                else:
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_bytes(o["data"])
        except Exception as ex:
            hint = ""
            if res["backup"]:
                hint = f' Restore with: cp -a "{res["backup"]}/files/." "{self.env.repo}/"'
            raise Precondition(f"apply failed: {ex}.{hint}", {"result": res})
        return res

    def _make_backup(self, touched):
        root = self._bak_target()
        files = root / "files"
        files.mkdir(parents=True, exist_ok=True)
        os.chmod(root, 0o700)
        manifest = {"created": dt.datetime.now().isoformat(timespec="seconds"), "repo": str(self.env.repo),
                    "paths": [o["path"] for o in touched]}
        for o in touched:
            src, dst = Path(o["abs"]), files / o["path"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
        for dirpath, dirnames, filenames in os.walk(root):
            os.chmod(dirpath, 0o700)
            for fn in filenames:
                os.chmod(os.path.join(dirpath, fn), 0o600)
        mf = root / "manifest.json"
        mf.write_text(dumps(manifest), encoding="utf-8")
        os.chmod(mf, 0o600)


# --------------------------------------------------------------------------------------------------
# Output helpers
# --------------------------------------------------------------------------------------------------
def emit_write_result(cmd, res, args, extra=None):
    mode = res["mode"]
    n = len(res["ops"])
    counts = {k: sum(1 for o in res["ops"] if o["op"] == k) for k in ("create", "modify", "delete")}
    if args.json:
        out = {"command": cmd, "mode": "dry-run" if mode == "DRY" else "apply", "ops": res["ops"],
               "backup": res["backup"], "warnings": res["warnings"],
               "summary": {"mode": mode, "ops": n, **counts}}
        out.update(extra or {})
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return
    for o in res["ops"]:
        print(f"{mode}|{o['op']}|{o['path']}" + (f" ({o['detail']})" if o["detail"] else ""))
    if res["backup"]:
        print(f"{mode}|backup|{res['backup']}/ (files copied with mode 0600; restore: cp -a \"{res['backup']}/files/.\" \"{res['repo']}/\")")
    for w in res["warnings"]:
        print(f"WARN|note|{w}")
    for k, v in (extra or {}).items():
        print(f"INFO|{k}|{v}")
    print(f"RESUMEN|{mode}|{n} operations (create {counts['create']}, modify {counts['modify']}, delete {counts['delete']})")


def emit_findings(findings, args, header=None):
    fails = sum(1 for f in findings if f["estado"] == "FAIL")
    warns = sum(1 for f in findings if f["estado"] == "WARN")
    if args.json:
        out = dict(header or {})
        out["findings"] = [{k: v for k, v in f.items() if v is not None} for f in findings]
        out["summary"] = {"fail": fails, "warn": warns}
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        for f in findings:
            comp = f"{f['componente']}: " if f.get("componente") else ""
            print(f"{f['estado']}|{f['id']}|{comp}{f['detalle']}")
        print(f"RESUMEN|{fails} FAIL|{warns} WARN")
    return EXIT_FAIL if fails else EXIT_OK


# --------------------------------------------------------------------------------------------------
# File helpers (frontmatter, markdown tables)
# --------------------------------------------------------------------------------------------------
FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)


def split_fm(text):
    m = FM_RE.match(text)
    return (m.group(1), text[m.end():]) if m else (None, text)


def fm_get(fm, key):
    m = re.search(rf"^{re.escape(key)}:[ \t]*(.*)$", fm or "", re.M)
    return m.group(1).strip() if m else None


def set_fm_version(text, version):
    fm, body = split_fm(text)
    if fm is None:
        raise Usage("SKILL.md has no frontmatter")
    if re.search(r"^version:[ \t]*\d+[ \t]*$", fm, re.M):
        fm = re.sub(r"^version:[ \t]*\d+[ \t]*$", f"version: {version}", fm, count=1, flags=re.M)
    else:
        fm = fm + f"\nversion: {version}"          # inserted before the closing ---
    return f"---\n{fm}\n---\n" + body


def first_sentence(desc):
    return re.split(r"\.\s+Also invoked", desc or "")[0].rstrip(".").strip()


def title_of(name):
    return name.replace("-", " ").title()


def md_table_block(lines, header_pred):
    """Return (start_idx_of_header, last_row_idx) of the first table whose header line satisfies header_pred."""
    for i, l in enumerate(lines):
        if l.lstrip().startswith("|") and header_pred(l):
            j = i
            while j + 1 < len(lines) and lines[j + 1].lstrip().startswith("|"):
                j += 1
            return i, j
    return None


def split_row(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def join_row(cells):
    return "| " + " | ".join(cells) + " |"


def plugin_row_idx(lines, plugin):
    pat = re.compile(r"^\|\s*\[`" + re.escape(plugin) + r"`\]")
    for i, l in enumerate(lines):
        if pat.match(l):
            return i
    return None


def readme_skill_cells(cell):
    return re.findall(r"`([^`]+)`", cell)


def table_headers(lines, i):
    """Header cells of the markdown table that contains line i (None if it cannot be found)."""
    j = i
    while j >= 0 and lines[j].lstrip().startswith("|"):
        j -= 1
    h = j + 1
    if h + 1 < len(lines) and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[h + 1]):
        return split_row(lines[h])
    return None


def col_index(headers, *names):
    for k, h in enumerate(headers or []):
        if any(n in h.lower() for n in names):
            return k
    return None


def plugins_readme_edit(text, plugin, add_skill=None, remove_skill=None, status=None):
    """Edits the Status / Skills columns of the plugin's row, located by HEADER NAME (never by position)."""
    lines = text.split("\n")
    i = plugin_row_idx(lines, plugin)
    if i is None:
        return text
    heads = table_headers(lines, i)
    cells = split_row(lines[i])
    sc, kc = col_index(heads, "status", "estado"), col_index(heads, "skills")
    if status is not None and sc is not None and sc < len(cells):
        cells[sc] = status
    if (add_skill or remove_skill) and kc is not None and kc < len(cells):
        sk = readme_skill_cells(cells[kc])
        if add_skill and add_skill not in sk:
            sk.append(add_skill)
        if remove_skill and remove_skill in sk:
            sk.remove(remove_skill)
        cells[kc] = ", ".join(f"`{x}`" for x in sk) if sk else "—"
    lines[i] = join_row(cells)
    return "\n".join(lines)


def plugins_readme_add_row(text, plugin, status, skills):
    lines = text.split("\n")
    if plugin_row_idx(lines, plugin) is not None:
        return text
    blk = md_table_block(lines, lambda l: "plugin" in l.lower() and ("status" in l.lower() or "skills" in l.lower()))
    if not blk:
        return None
    start, end = blk
    heads = split_row(lines[start])
    cells = []
    for k, h in enumerate(heads):
        hl = h.lower()
        cells.append(f"[`{plugin}`](./{plugin}/README.md)" if k == 0 else status if ("status" in hl or "estado" in hl)
                     else (", ".join(f"`{x}`" for x in skills) or "—") if "skills" in hl else "—")
    pos = end + 1
    for k in range(start + 2, end + 1):
        m = re.match(r"^\|\s*\[`([^`]+)`\]", lines[k])
        if m and m.group(1) > plugin:
            pos = k
            break
    lines.insert(pos, join_row(cells))
    return "\n".join(lines)


def root_readme_row_idx(lines, plugin):
    pat = re.compile(r"^\|\s*`" + re.escape(plugin) + r"`\s*\|")
    for i, l in enumerate(lines):
        if pat.match(l):
            return i
    return None


def root_readme_edit(text, plugin, status=None, add_row=None):
    lines = text.split("\n")
    i = root_readme_row_idx(lines, plugin)
    if i is not None:
        if status is not None:
            cells = split_row(lines[i])
            if len(cells) >= 3:
                cells[-2] = f"`{status}`"
                lines[i] = join_row(cells)
        return "\n".join(lines)
    if not add_row:
        return text
    blk = md_table_block(lines, lambda l: "Plugin" in l and "Spec" in l)
    if not blk:
        return None
    start, end = blk
    pos = end + 1
    for k in range(start + 2, end + 1):
        m = re.match(r"^\|\s*`([^`]+)`", lines[k])
        if m and m.group(1) > plugin:
            pos = k
            break
    lines.insert(pos, add_row)
    return "\n".join(lines)


def plugin_readme_add_skill(text, plugin, skill, desc, source):
    if re.search(rf"`{re.escape(skill)}`", text):
        return text
    lines = text.split("\n")
    row = f"| `{skill}` | `/{plugin}:{skill}` | {desc} |"
    blk = md_table_block(lines, lambda l: "Skill" in l and ("Invocation" in l or "Description" in l))
    if blk:
        lines.insert(blk[1] + 1, row)
        return "\n".join(lines)
    section = f"\n## Skills\n\n| Skill | Invocation | Description |\n|-------|-----------|-------------|\n{row}\n"
    idx = next((i for i, l in enumerate(lines) if l.startswith("## Installation")), None)
    if idx is None:
        return text.rstrip("\n") + "\n" + section
    lines[idx:idx] = section.strip("\n").split("\n") + [""]
    return "\n".join(lines)


def plugin_readme_remove_skill(text, skill):
    pat = re.compile(r"^\|\s*`" + re.escape(skill) + r"`\s*\|")
    return "\n".join(l for l in text.split("\n") if not pat.match(l))


def marketplace_source(env):
    r = env.remote or ""
    m = re.search(r"github\.com[:/]+([^/]+/[^/]+?)(?:\.git)?/?$", r)
    return m.group(1) if m else (r or "<marketplace-source>")


# --------------------------------------------------------------------------------------------------
# Localized labels for generated documentation
# --------------------------------------------------------------------------------------------------
LABELS = {
    "en": dict(spec="Plugin Spec", status="Status", version="Version", overview="Overview", skill="Skill",
               purpose="Purpose", invocation="Invocation", nongoals="Non-Goals", changelog="Changelog",
               changes="Changes", todo="TODO: describe", deps="Dependencies", skills="Skills",
               installation="Installation", initial="Initial release", what="What it does",
               deps_intro="This plugin requires the following plugins to be installed:", install="Install"),
    "es": dict(spec="Especificación del plugin", status="Estado", version="Versión", overview="Descripción general",
               skill="Skill", purpose="Propósito", invocation="Invocación", nongoals="Fuera de alcance",
               changelog="Historial de cambios", changes="Cambios", todo="TODO: describir", deps="Dependencias",
               skills="Skills", installation="Instalación", initial="Versión inicial", what="Qué hace",
               deps_intro="Este plugin requiere que estén instalados los siguientes plugins:", install="Instalar"),
}


def labels(lang):
    return LABELS.get(lang, LABELS["en"])


def skill_desc_from_disk(env, plugin_entry, skill):
    p = env.repo / plugin_entry["path"] / "skills" / skill / "SKILL.md"
    if p.is_file():
        fm, _ = split_fm(p.read_text(encoding="utf-8"))
        return first_sentence((fm_get(fm, "description") or "").strip("\"'"))
    return ""


def spec_skill_section(L, plugin, skill, purpose):
    return (f"## {L['skill']}: `{skill}`\n\n### {L['purpose']}\n{purpose or L['todo']}\n\n### {L['invocation']}\n"
            f"```\n/{plugin}:{skill} [args]\n```\n\n### {L['nongoals']}\n- {L['todo']}\n\n---\n")


def spec_text(env, entry):
    L = labels(env.docs_language)
    parts = [f"# {L['spec']}: {entry['name']}\n\n> **{L['status']}:** `{entry['status']}` | **{L['version']}:** `{entry['version']}`\n\n---\n",
             f"## {L['overview']}\n\n{entry['description']}\n\n---\n"]
    for s in entry.get("skills", []):
        parts.append(spec_skill_section(L, entry["name"], s["name"], skill_desc_from_disk(env, entry, s["name"])))
    rows = "\n".join(f"| {c['version']} | {c['changes']} |" for c in entry.get("changelog", []))
    parts.append(f"## {L['changelog']}\n\n| {L['version']} | {L['changes']} |\n|---------|---------|\n{rows}\n")
    return "\n".join(parts)


def deps_section(L, entry):
    plugs = [d["name"] for d in entry.get("dependencies", []) or [] if d.get("type") == "plugin"]
    if not plugs:
        return ""
    rows = "\n".join(f"| `{p}` | `claude plugins install {p}` |" for p in plugs)
    return f"## {L['deps']}\n\n{L['deps_intro']}\n\n| Plugin | {L['install']} |\n|--------|--------|\n{rows}\n\n"


def readme_text(env, entry):
    L = labels(env.docs_language)
    rows = "\n".join(f"| `{s['name']}` | `/{entry['name']}:{s['name']}` | {skill_desc_from_disk(env, entry, s['name'])} |"
                     for s in entry.get("skills", []))
    return (f"# {entry['name']}\n\n{entry['description']}\n\n## {L['skills']}\n\n| Skill | Invocation | {L['what']} |\n"
            f"|-------|-----------|--------------|\n{rows}\n\n{deps_section(L, entry)}## {L['installation']}\n\n"
            f"```bash\nclaude plugins marketplace add {marketplace_source(env)}\nclaude plugins install {entry['name']}\n```\n")


# --------------------------------------------------------------------------------------------------
# Write commands
# --------------------------------------------------------------------------------------------------
def find_plugin(cat, name):
    p = next((x for x in cat["plugins"] if x["name"] == name), None)
    if not p:
        raise Usage(f"plugin '{name}' not found in the catalog")
    return p


def find_skill(plugin, name):
    s = next((x for x in plugin.get("skills", []) if x["name"] == name), None)
    if not s:
        raise Usage(f"skill '{name}' not found in plugin '{plugin['name']}'")
    return s


def bump_z(plugin):
    x, y, z = map(int, plugin["version"].split("."))
    return z + 1, f"{x}.{y}.{z + 1}"


def plugin_json_path(env, plugin):
    return env.repo / plugin["path"] / ".claude-plugin" / "plugin.json"


def set_plugin_json_version(plan, env, plugin, version):
    pj = plugin_json_path(env, plugin)
    if pj.is_file():
        d = json.load(open(pj))
        d["version"] = version
        plan.write_json(pj, d, f"version {plugin['version']} -> {version}" if plugin["version"] != version else "")


def cmd_skill_update(env, args):
    if not args.change:
        raise Usage("skill-update needs --change \"<one-line description>\"")
    cat = require_catalog(env)
    plugin = find_plugin(cat, args.plugin)
    skill = find_skill(plugin, args.skill)
    new_z, new_version = bump_z(plugin)
    old_sv, old_pv = skill["version"], plugin["version"]
    skill_md = env.repo / plugin["path"] / "skills" / skill["name"] / "SKILL.md"
    if not skill_md.is_file():
        raise Precondition(f"{skill_md} not found")
    plan = Plan(env, args.dry_run)
    plan.write_text(skill_md, set_fm_version(skill_md.read_text(encoding="utf-8"), new_z), f"version {old_sv} -> {new_z}")
    skill["version"] = new_z
    skill.setdefault("changelog", []).insert(0, {"version": new_z, "changes": args.change})
    plugin["version"] = new_version
    plugin["changelog"].insert(0, {"version": new_version, "changes": f"{skill['name']}: {args.change}"})
    plan.write_json(env.catalog_path, cat, f"{plugin['name']} {old_pv} -> {new_version}")
    set_plugin_json_version(plan, env, {**plugin, "version": old_pv}, new_version)
    plan.sync_global_catalog(cat)
    res = plan.run()
    emit_write_result("skill-update", res, args, {"plugin": plugin["name"], "skill": skill["name"],
                      "skill_version": f"{old_sv} -> {new_z}", "plugin_version": f"{old_pv} -> {new_version}"})
    return EXIT_OK


def cmd_skill_add(env, args):
    if not args.description:
        raise Usage("skill-add needs --description \"<one line>\"")
    cat = require_catalog(env)
    plugin = find_plugin(cat, args.plugin)
    if any(s["name"] == args.skill for s in plugin.get("skills", [])):
        raise Usage(f"skill '{args.skill}' already exists in '{plugin['name']}'")
    new_z, new_version = bump_z(plugin)
    old_pv = plugin["version"]
    tools = args.allowed_tools or "Bash, Read, Edit, Write"
    skill_md = env.repo / plugin["path"] / "skills" / args.skill / "SKILL.md"
    if skill_md.exists():
        raise Precondition(f"{skill_md} already exists")
    hint = f'argument-hint: "{args.argument_hint}"\n' if args.argument_hint else ""
    body = (f"---\nname: {args.skill}\ndescription: {args.description.rstrip('.')}. Also invoked explicitly as "
            f"/{plugin['name']}:{args.skill} with optional args.\nversion: {new_z}\n{hint}allowed-tools: [{tools}]\n---\n\n"
            f"# {title_of(args.skill)}\n\n{args.description}\n\n---\n\n## TODO: define skill steps here\n")
    plan = Plan(env, args.dry_run)
    plan.write_text(skill_md, body, f"version {new_z}")
    plugin.setdefault("skills", []).append({"name": args.skill, "version": new_z,
                                            "changelog": [{"version": new_z, "changes": "Initial release"}]})
    plugin["version"] = new_version
    plugin["changelog"].insert(0, {"version": new_version, "changes": f"Add {args.skill} skill"})
    plan.write_json(env.catalog_path, cat, f"{plugin['name']} {old_pv} -> {new_version}")
    set_plugin_json_version(plan, env, {**plugin, "version": old_pv}, new_version)
    plan.sync_global_catalog(cat)
    readme = env.repo / plugin["path"] / "README.md"
    if readme.is_file():
        plan.write_text(readme, plugin_readme_add_skill(readme.read_text(encoding="utf-8"), plugin["name"], args.skill,
                                                        args.description.rstrip("."), marketplace_source(env)), "skills table")
    else:
        plan.write_text(readme, readme_text(env, plugin), "README created")
    pr = env.repo / "plugins" / "README.md"
    if pr.is_file():
        plan.write_text(pr, plugins_readme_edit(pr.read_text(encoding="utf-8"), plugin["name"], add_skill=args.skill), "Skills column")
    res = plan.run()
    emit_write_result("skill-add", res, args, {"plugin": plugin["name"], "skill": args.skill,
                      "skill_version": new_z, "plugin_version": f"{old_pv} -> {new_version}"})
    return EXIT_OK


def cmd_skill_remove(env, args):
    cat = require_catalog(env)
    plugin = find_plugin(cat, args.plugin)
    skill = find_skill(plugin, args.skill)
    if args.soft or args.restore:
        return logical_skill(env, args, cat, plugin, skill)
    if not args.yes and not args.dry_run:
        raise Usage("skill-remove is destructive: pass --yes (the skill asks the user first) or use --dry-run")
    plan = Plan(env, args.dry_run, backup=True, check_dirty=True, allow_dirty=args.allow_dirty)
    plan.delete(env.repo / plugin["path"] / "skills" / args.skill, "skill directory")
    plugin["skills"] = [s for s in plugin["skills"] if s["name"] != args.skill]
    plugin["changelog"].insert(0, {"version": plugin["version"], "changes": f"Remove {args.skill} skill"})
    plan.write_json(env.catalog_path, cat, f"Z unchanged ({plugin['version']})")
    plan.sync_global_catalog(cat)
    readme = env.repo / plugin["path"] / "README.md"
    if readme.is_file():
        plan.write_text(readme, plugin_readme_remove_skill(readme.read_text(encoding="utf-8"), args.skill), "skills table")
    pr = env.repo / "plugins" / "README.md"
    if pr.is_file():
        plan.write_text(pr, plugins_readme_edit(pr.read_text(encoding="utf-8"), plugin["name"], remove_skill=args.skill), "Skills column")
    res = plan.run()
    emit_write_result("skill-remove", res, args, {"plugin": plugin["name"], "skill": args.skill, "plugin_version": plugin["version"]})
    return EXIT_OK


def logical_skill(env, args, cat, plugin, skill):
    """--soft marks the skill as retired in the catalog (no file is deleted); --restore undoes it."""
    if args.soft and args.restore:
        raise Usage("--soft and --restore are mutually exclusive")
    if args.soft and skill.get("retired"):
        raise Usage(f"skill '{skill['name']}' is already retired")
    if args.restore and not skill.get("retired"):
        raise Usage(f"skill '{skill['name']}' is not retired")
    plan = Plan(env, args.dry_run, backup=True, check_dirty=True, allow_dirty=args.allow_dirty)
    if args.soft:
        skill["retired"] = {"at": dt.date.today().isoformat()}
        msg = f"Retire {skill['name']} skill (soft remove; files kept)"
    else:
        skill.pop("retired", None)
        msg = f"Restore {skill['name']} skill"
    plugin["changelog"].insert(0, {"version": plugin["version"], "changes": msg})
    plan.write_json(env.catalog_path, cat, f"Z unchanged ({plugin['version']}); no files deleted")
    plan.sync_global_catalog(cat)
    res = plan.run()
    emit_write_result("skill-remove", res, args, {"plugin": plugin["name"], "skill": skill["name"],
                      "mode_detail": "soft remove" if args.soft else "restore"})
    return EXIT_OK


def logical_plugin(env, args, cat, plugin):
    """--soft marks the plugin as deprecated/retired in the catalog (no file is deleted); --restore undoes it."""
    if args.soft and args.restore:
        raise Usage("--soft and --restore are mutually exclusive")
    if args.soft and plugin.get("retired"):
        raise Usage(f"plugin '{plugin['name']}' is already retired")
    if args.restore and not plugin.get("retired"):
        raise Usage(f"plugin '{plugin['name']}' is not retired")
    plan = Plan(env, args.dry_run, backup=True, check_dirty=True, allow_dirty=args.allow_dirty)
    if args.soft:
        plugin["retired"] = {"from_status": plugin["status"], "at": dt.date.today().isoformat()}
        plugin["status"] = "deprecated"
        msg = "Retire plugin (soft remove; files kept)"
    else:
        plugin["status"] = plugin["retired"].get("from_status", "beta")
        plugin.pop("retired", None)
        msg = "Restore plugin"
    plugin["changelog"].insert(0, {"version": plugin["version"], "changes": msg})
    plan.write_json(env.catalog_path, cat, f"status -> {plugin['status']}; no files deleted")
    plan.sync_global_catalog(cat)
    pr = env.repo / "plugins" / "README.md"
    if pr.is_file():
        plan.write_text(pr, plugins_readme_edit(pr.read_text(encoding="utf-8"), plugin["name"], status=plugin["status"]), "status column")
    res = plan.run()
    emit_write_result("remove", res, args, {"plugin": plugin["name"], "mode_detail": "soft remove" if args.soft else "restore"})
    return EXIT_OK


def cmd_update(env, args):
    cat = require_catalog(env)
    plugin = find_plugin(cat, args.plugin)
    changed = args.description is not None or args.status is not None or args.bump != "none"
    if not changed:
        raise Usage("update needs at least one of --description, --status, --bump x|y")
    if not args.change:
        raise Usage("update needs --change \"<changelog entry>\" when anything changes")
    old_pv = plugin["version"]
    x, y, z = map(int, old_pv.split("."))
    new_version = old_pv
    if args.bump == "y":
        new_version = f"{x}.{y + 1}.{z}"
    elif args.bump == "x":
        new_version = f"{x + 1}.0.{z}"
    plan = Plan(env, args.dry_run, backup=True, check_dirty=True, allow_dirty=args.allow_dirty)
    if args.description is not None:
        plugin["description"] = args.description
    if args.status is not None:
        plugin["status"] = args.status
    if new_version != old_pv:
        plugin["version"] = new_version
    plugin["changelog"].insert(0, {"version": plugin["version"], "changes": args.change})
    plan.write_json(env.catalog_path, cat, f"{plugin['name']} {old_pv} -> {plugin['version']}")
    plan.sync_global_catalog(cat)
    if new_version != old_pv:
        set_plugin_json_version(plan, env, {**plugin, "version": old_pv}, new_version)
    mp_path = env.repo / MP
    if args.description is not None:
        mp = json.load(open(mp_path))
        for e in mp.get("plugins", []):
            if e.get("name") == plugin["name"]:
                e["description"] = args.description
        plan.write_json(mp_path, mp, "description")
    if args.status is not None:
        pr = env.repo / "plugins" / "README.md"
        if pr.is_file():
            plan.write_text(pr, plugins_readme_edit(pr.read_text(encoding="utf-8"), plugin["name"], status=args.status), "status column")
        rr = env.repo / "README.md"
        if rr.is_file():
            t = root_readme_edit(rr.read_text(encoding="utf-8"), plugin["name"], status=args.status)
            if t is not None:
                plan.write_text(rr, t, "status column")
    res = plan.run()
    emit_write_result("update", res, args, {"plugin": plugin["name"], "plugin_version": f"{old_pv} -> {plugin['version']}"})
    return EXIT_OK


def cmd_remove(env, args):
    cat = require_catalog(env)
    plugin = find_plugin(cat, args.plugin)
    if args.soft or args.restore:
        return logical_plugin(env, args, cat, plugin)
    if not args.yes and not args.dry_run:
        raise Usage("remove is destructive and irreversible: pass --yes (the skill asks the user first) or use --dry-run")
    plan = Plan(env, args.dry_run, backup=True, check_dirty=True, allow_dirty=args.allow_dirty)
    plan.delete(env.repo / plugin["path"], "plugin directory")
    plan.delete(env.repo / (plugin.get("spec") or f"specs/{plugin['name']}.md"), "plugin spec")
    cat["plugins"] = [p for p in cat["plugins"] if p["name"] != plugin["name"]]
    plan.write_json(env.catalog_path, cat, "entry removed")
    plan.sync_global_catalog(cat)
    mp_path = env.repo / MP
    mp = json.load(open(mp_path))
    mp["plugins"] = [e for e in mp.get("plugins", []) if e.get("name") != plugin["name"]]
    plan.write_json(mp_path, mp, "entry removed")
    pr = env.repo / "plugins" / "README.md"
    if pr.is_file():
        lines = pr.read_text(encoding="utf-8").split("\n")
        i = plugin_row_idx(lines, plugin["name"])
        if i is not None:
            del lines[i]
            plan.write_text(pr, "\n".join(lines), "row removed")
    res = plan.run()
    emit_write_result("remove", res, args, {"plugin": plugin["name"]})
    return EXIT_OK


def cmd_create(env, args):
    cat = require_catalog(env)
    name = args.plugin
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name):
        raise Usage("plugin name must be kebab-case")
    if any(p["name"] == name for p in cat["plugins"]):
        raise Usage(f"plugin '{name}' already exists")
    if not args.description:
        raise Usage("create needs --description \"<one line>\"")
    skills = []
    for s in args.skill or []:
        sname, _, purpose = s.partition(":")
        skills.append((sname.strip(), purpose.strip() or "TODO"))
    deps = []
    for d in args.dep_tool or []:
        m = re.match(r"^([A-Za-z0-9_.+-]+)\s*(.*)$", d)
        deps.append({"type": "tool", "name": m.group(1), "version": m.group(2).strip() or "*"})
    for d in args.dep_plugin or []:
        deps.append({"type": "plugin", "name": d})
    if deps and not any(s[0] == "install" for s in skills):
        skills.insert(0, ("install", "Verifies the plugin dependencies and reports how to install what is missing"))
    z = len(skills)
    version = f"1.0.{z}"
    pdir = env.repo / "plugins" / name
    if pdir.exists():
        raise Precondition(f"{pdir} already exists")
    entry = {"name": name, "description": args.description, "category": args.category, "status": args.status,
             "version": version, "spec": f"specs/{name}.md", "path": f"plugins/{name}"}
    if args.scope:
        entry["scopes"] = args.scope
    if deps:
        entry["dependencies"] = deps
    entry["changelog"] = [{"version": version, "changes": "Initial release"}]
    entry["skills"] = [{"name": s, "version": i + 1, "changelog": [{"version": i + 1, "changes": "Initial release"}]}
                       for i, (s, _) in enumerate(skills)]
    author = env.mp.get("owner") if isinstance(env.mp.get("owner"), dict) else {"name": "unknown"}
    pj = {"name": name, "version": version, "description": args.description, "author": author}
    if args.scope:
        pj["scopes"] = args.scope
    plan = Plan(env, args.dry_run)
    plan.write_json(pdir / ".claude-plugin" / "plugin.json", pj)
    for i, (s, purpose) in enumerate(skills):
        if s == "install" and deps:
            body = ("Reads the `dependencies` array of this plugin from `catalog.json`, checks each one (`which <name>` + version for tools, "
                    "`ls <cache>/<name>/` for plugins), prints a status table and shows install instructions for every missing dependency. Idempotent.")
        else:
            body = purpose
        md = (f"---\nname: {s}\ndescription: {body.split('. ')[0].rstrip('.')}. Also invoked explicitly as /{name}:{s} with optional args.\n"
              f"version: {i + 1}\nargument-hint: \"[optional args]\"\nallowed-tools: [Bash, Read, Edit, Write]\n---\n\n# {title_of(s)}\n\n"
              f"{body}\n\n---\n\n## TODO: define skill steps here\n")
        plan.write_text(pdir / "skills" / s / "SKILL.md", md)
    plan.write_text(pdir / "README.md", readme_text(env, entry))
    plan.write_text(env.repo / entry["spec"], spec_text(env, entry))
    cat["plugins"].append(entry)
    plan.write_json(env.catalog_path, cat, f"plugin added at {version}")
    plan.sync_global_catalog(cat)
    mp_path = env.repo / MP
    mp = json.load(open(mp_path))
    keys = set().union(*[set(e) for e in mp.get("plugins", [])]) if mp.get("plugins") else {"name", "source", "description"}
    mp_entry = {"name": name, "description": args.description}
    if "author" in keys:
        mp_entry["author"] = {"name": author.get("name", "unknown")}
    if "category" in keys:
        mp_entry["category"] = args.category
    mp_entry["source"] = f"./plugins/{name}"
    if "homepage" in keys and env.remote:
        mp_entry["homepage"] = re.sub(r"\.git$", "", env.remote) + f"/tree/main/plugins/{name}"
    mp.setdefault("plugins", []).append(mp_entry)
    plan.write_json(mp_path, mp, "entry added")
    pr = env.repo / "plugins" / "README.md"
    if pr.is_file():
        t = plugins_readme_add_row(pr.read_text(encoding="utf-8"), name, args.status, [s for s, _ in skills])
        if t is not None:
            plan.write_text(pr, t, "row added")
    else:
        plan.warnings.append("plugins/README.md does not exist: not created")
    rr = env.repo / "README.md"
    if rr.is_file():
        t = root_readme_edit(rr.read_text(encoding="utf-8"), name,
                             add_row=f"| `{name}` | {args.description} | `{args.status}` | [spec](./specs/{name}.md) |")
        if t is not None:
            plan.write_text(rr, t, "row added")
    res = plan.run()
    emit_write_result("create", res, args, {"plugin": name, "version": version})
    return EXIT_OK


def cmd_env(env, args):
    d = env_dict(env)
    if args.json:
        print(json.dumps(d, indent=2, ensure_ascii=False))
    else:
        for k, v in d.items():
            if k != "notes":
                print(f"INFO|{k}|{v}")
        for n in d["notes"]:
            print(f"WARN|note|{n}")
        print("RESUMEN|0 FAIL|%d WARN" % len(d["notes"]))
    return EXIT_OK


# --------------------------------------------------------------------------------------------------
# Shared pieces for the diagnostic commands
# --------------------------------------------------------------------------------------------------
SEV_STATE = {"CRITICAL": "FAIL", "MAJOR": "FAIL", "MINOR": "WARN"}
SEV_ORDER = {"CRITICAL": 0, "MAJOR": 1, "MINOR": 2}


def mk(sev, cid, plugin, skill, detail, fix, **extra):
    comp = f"{plugin}:{skill}" if skill else plugin
    d = {"estado": SEV_STATE[sev], "id": cid, "componente": comp, "detalle": detail,
         "severity": sev, "fix": fix, "plugin": plugin, "skill": skill}
    d.update(extra)
    return d


def sort_and_number(findings):
    findings.sort(key=lambda f: (SEV_ORDER[f["severity"]], f["plugin"], f["skill"] or "", f["id"]))
    for i, f in enumerate(findings, 1):
        f["n"] = i
    return findings


def decorate(findings):
    """Add '#n' and the fix type to the human detail line (the id stays stable)."""
    out = []
    for f in findings:
        g = dict(f)
        g["detalle"] = f"#{f['n']} {f['detalle']} [{f['fix']}]"
        out.append(g)
    return out


class Files:
    """In-memory view of the files a fix run modifies; written once through the Plan."""
    def __init__(self):
        self.text, self.orig = {}, {}

    def get(self, path):
        path = str(path)
        if path not in self.text:
            self.orig[path] = self.text[path] = Path(path).read_text(encoding="utf-8")
        return self.text[path]

    def set(self, path, text):
        self.get(path)
        self.text[str(path)] = text

    def flush(self, plan, detail=""):
        for p, t in self.text.items():
            if t != self.orig[p]:
                plan.write_text(p, t, detail)


def parse_tools(raw):
    return [t.strip() for t in (raw or "").strip("[]").split(",") if t.strip()]


def installed_version(env, plugin):
    f = env.home / ".claude" / "plugins" / "installed_plugins.json"
    try:
        d = json.load(open(f))
        ent = d.get("plugins", d).get(f"{plugin}@{env.marketplace}")
        if ent:
            ent = ent[0] if isinstance(ent, list) else ent
            return ent.get("version")
    except Exception:
        pass
    base = env.cache_base / plugin
    if base.is_dir():
        vs = [p.name for p in base.iterdir() if re.fullmatch(r"\d+\.\d+\.\d+", p.name)]
        if vs:
            return sorted(vs, key=lambda v: tuple(map(int, v.split("."))))[-1]
    return None


def _git(env, *a):
    try:
        return subprocess.check_output(["git", "-C", str(env.repo)] + list(a), stderr=subprocess.DEVNULL, text=True)
    except Exception:
        return None


def scope_lists(cat, args):
    plugins = cat["plugins"]
    if args.plugin:
        names = {p["name"] for p in plugins}
        for n in args.plugin:
            if n not in names:
                raise Usage(f"plugin '{n}' not found in the catalog")
        plugins = [p for p in plugins if p["name"] in args.plugin]
    skills = args.skill or []
    if skills:
        have = {s["name"] for p in plugins for s in p.get("skills", [])}
        for s in skills:
            if s not in have:
                raise Usage(f"skill '{s}' not found in the selected plugins")
    return plugins, skills


# --------------------------------------------------------------------------------------------------
# skill-doctor: C1..C10
# --------------------------------------------------------------------------------------------------
def detect_conventions(env, cat):
    """C4's allowed-tools and C7's 'Also invoked' suffix are plugin4cc conventions: they are only enforced when
    at least half of the marketplace's skills already follow them (so arkana-like marketplaces are not rewritten)."""
    total = with_tools = with_suffix = 0
    for p in cat["plugins"]:
        for s in p.get("skills", []):
            md = env.repo / p["path"] / "skills" / s["name"] / "SKILL.md"
            if not md.is_file():
                continue
            fm, _ = split_fm(md.read_text(encoding="utf-8"))
            if fm is None:
                continue
            total += 1
            with_tools += fm_get(fm, "allowed-tools") not in (None, "")
            with_suffix += "Also invoked explicitly as" in (fm_get(fm, "description") or "")
    if not total:
        return True, True
    return with_tools * 2 >= total, with_suffix * 2 >= total


def audit_skills(env, cat, plugins, only_skills):
    F = []
    need_tools, need_suffix = detect_conventions(env, cat)
    for plugin in plugins:
        pname = plugin["name"]
        pj = plugin_json_path(env, plugin)
        pj_version = None
        try:
            pj_version = json.load(open(pj)).get("version")
        except Exception:
            pass
        if pj_version != plugin["version"]:
            F.append(mk("CRITICAL", "C2", pname, None, f"plugin.json version {pj_version} != catalog version {plugin['version']}", "auto"))
        inst = installed_version(env, pname)
        if inst and pj_version and inst != pj_version:
            rel = "lower" if tuple(map(int, inst.split("."))) < tuple(map(int, pj_version.split("."))) else "higher"
            F.append(mk("MINOR", "C3", pname, None, f"installed {inst} is {rel} than plugin.json {pj_version} "
                        "(advisory; push, then /plugin update — this skill never writes the cache)", "manual"))
        has_deps = bool(plugin.get("dependencies")) or any(s.get("dependencies") for s in plugin.get("skills", []))
        if has_deps and not any(s["name"] == "install" for s in plugin.get("skills", [])):
            F.append(mk("MAJOR", "C6", pname, None, "plugin has dependencies but no install skill", "manual"))
        # C10: content changed without a version bump (compared with origin/main)
        if _git(env, "rev-parse", "--verify", "-q", "origin/main") is not None:
            changed = (_git(env, "diff", "--name-only", "origin/main", "--", plugin["path"]) or "").split()
            old = _git(env, "show", f"origin/main:{plugin['path']}/.claude-plugin/plugin.json")
            if changed and old:
                try:
                    if json.loads(old).get("version") == pj_version:
                        F.append(mk("MAJOR", "C10", pname, None, f"{len(changed)} file(s) changed vs origin/main but version is still {pj_version}", "manual"))
                except Exception:
                    pass
        for skill in plugin.get("skills", []):
            sname = skill["name"]
            if only_skills and sname not in only_skills:
                continue
            md = env.repo / plugin["path"] / "skills" / sname / "SKILL.md"
            if not md.is_file():
                F.append(mk("CRITICAL", "C1", pname, sname, "SKILL.md not found", "manual"))
                continue
            text = md.read_text(encoding="utf-8")
            fm, body = split_fm(text)
            if fm is None:
                F.append(mk("CRITICAL", "C4", pname, sname, "SKILL.md has no frontmatter", "manual"))
                continue
            v = fm_get(fm, "version")
            if v is None:
                F.append(mk("CRITICAL", "C1", pname, sname, f"SKILL.md has no version (catalog: {skill['version']})", "auto"))
            elif not re.fullmatch(r"\d+", v) or int(v) != skill["version"]:
                F.append(mk("CRITICAL", "C1", pname, sname, f"SKILL.md version {v} != catalog version {skill['version']}", "auto"))
            for field in ("name", "description") + (("allowed-tools",) if need_tools else ()):
                if fm_get(fm, field) in (None, ""):
                    F.append(mk("CRITICAL", "C4", pname, sname, f"missing frontmatter field: {field}", "manual"))
            tools = parse_tools(fm_get(fm, "allowed-tools"))
            need = []
            if "AskUserQuestion" in body:
                need.append("AskUserQuestion")
            if "```bash" in body:
                need.append("Bash")
            for t in ("Read", "Write", "Edit"):
                if re.search(rf"(?:the )?{t} tool\b|\bUse {t}\b", body):
                    need.append(t)
            for t in need:
                if tools and t not in tools:
                    F.append(mk("MAJOR", "C5", pname, sname, f"body uses {t} but it is not in allowed-tools", "manual"))
            desc = (fm_get(fm, "description") or "")
            if need_suffix and "Also invoked explicitly as" not in desc:
                F.append(mk("MINOR", "C7", pname, sname, "description missing the 'Also invoked explicitly as' suffix", "auto"))
            cl = skill.get("changelog") or []
            if not cl or cl[0].get("version") != skill["version"]:
                F.append(mk("MINOR", "C8", pname, sname, f"no changelog entry for current version {skill['version']}", "auto"))
            for d in skill.get("dependencies", []) or []:
                if d.get("name") and d["name"] not in body:
                    F.append(mk("MINOR", "C9", pname, sname, f"catalog dependency '{d['name']}' is never mentioned in the body", "manual"))
    return sort_and_number(F)


def apply_skill_fixes(env, cat, selected, plan):
    files, cat_changed, applied = Files(), False, []
    for f in selected:
        plugin = next(p for p in cat["plugins"] if p["name"] == f["plugin"])
        skill = next((s for s in plugin.get("skills", []) if s["name"] == f["skill"]), None) if f["skill"] else None
        if f["id"] == "C1":
            md = env.repo / plugin["path"] / "skills" / skill["name"] / "SKILL.md"
            files.set(md, set_fm_version(files.get(md), skill["version"]))
        elif f["id"] == "C2":
            pjp = plugin_json_path(env, plugin)
            d = json.load(open(pjp))
            d["version"] = plugin["version"]
            plan.write_json(pjp, d, f"version -> {plugin['version']}")
        elif f["id"] == "C7":
            md = env.repo / plugin["path"] / "skills" / skill["name"] / "SKILL.md"
            t = files.get(md)
            fm, body = split_fm(t)
            d = (fm_get(fm, "description") or "").rstrip(".")
            new = f"{d}. Also invoked explicitly as /{plugin['name']}:{skill['name']}."
            fm2 = re.sub(r"^description:[ \t]*.*$", lambda m: "description: " + new, fm, count=1, flags=re.M)
            files.set(md, f"---\n{fm2}\n---\n" + body)
        elif f["id"] == "C8":
            skill.setdefault("changelog", []).insert(0, {"version": skill["version"], "changes": "version bump"})
            cat_changed = True
        else:
            continue
        applied.append(f)
    files.flush(plan, "fix")
    if cat_changed:
        plan.write_json(env.catalog_path, cat, "changelog entry")
        plan.sync_global_catalog(cat)
    return applied


def parse_fix_arg(raw, findings):
    if raw is None:
        return []
    if raw == "auto":
        return [f for f in findings if f["fix"] == "auto"]
    try:
        nums = {int(x) for x in raw.split(",") if x.strip()}
    except ValueError:
        raise Usage("--fix takes 'auto' or a comma-separated list of finding numbers")
    bad = nums - {f["n"] for f in findings}
    if bad:
        raise Usage(f"--fix: no finding(s) numbered {sorted(bad)}")
    return [f for f in findings if f["n"] in nums]


def run_diagnostic(env, args, audit, apply_fixes, header_extra=None):
    cat = require_catalog(env)
    plugins, only_skills = scope_lists(cat, args)
    findings = audit(env, cat, plugins, only_skills)
    selected = parse_fix_arg(args.fix, findings)
    header = {"plugin": (args.plugin[0] if args.plugin and len(args.plugin) == 1 else (args.plugin or None)),
              "skill": (args.skill[0] if args.skill and len(args.skill) == 1 else (args.skill or None))}
    header.update(header_extra or {})
    res, fixed = None, []
    if args.fix is not None:
        plan = Plan(env, args.dry_run, backup=True, check_dirty=True, allow_dirty=args.allow_dirty)
        fixed = apply_fixes(env, cat, [f for f in selected if f["fix"] == "auto"], plan)
        res = plan.run()
    remaining = [f for f in findings if f not in fixed]
    skipped = [f for f in selected if f["fix"] != "auto"]
    extras = []
    if not remaining:
        extras.append({"estado": "OK", "id": "audit", "componente": None,
                       "detalle": f"{len(plugins)} plugin(s) audited, no defects"})
    for f in skipped:
        extras.append({"estado": "WARN", "id": "fix-skipped", "componente": None,
                       "detalle": f"#{f['n']} {f['id']} is [manual] and was not fixed"})
    for f in fixed:
        extras.append({"estado": res["mode"], "id": "fix", "componente": None,
                       "detalle": f"#{f['n']} {f['id']} {f['componente']}: {f['detalle']}"})
    rows = (extras[:1] if not remaining else []) + remaining + (extras[1:] if not remaining else extras)
    code = EXIT_FAIL if any(f["estado"] == "FAIL" for f in rows) else EXIT_OK
    if args.json:
        if res:
            header["fix"] = {"mode": "dry-run" if res["mode"] == "DRY" else "apply", "ops": res["ops"],
                             "backup": res["backup"], "applied": [f["n"] for f in fixed]}
        emit_findings(rows, args, header)
    else:
        for f in rows:
            if f in remaining:
                d = decorate([f])[0]
                print(f"{d['estado']}|{d['id']}|{d['componente']}: {d['detalle']}")
            else:
                print(f"{f['estado']}|{f['id']}|{f['detalle']}")
        if res:
            for o in res["ops"]:
                print(f"{res['mode']}|{o['op']}|{o['path']}" + (f" ({o['detail']})" if o["detail"] else ""))
            if res["backup"]:
                print(f"{res['mode']}|backup|{res['backup']}/ (mode 0600; restore: cp -a \"{res['backup']}/files/.\" \"{res['repo']}/\")")
            for w in res["warnings"]:
                print(f"WARN|note|{w}")
        print(f"RESUMEN|{sum(1 for f in rows if f['estado'] == 'FAIL')} FAIL|{sum(1 for f in rows if f['estado'] == 'WARN')} WARN")
    return code


def cmd_doctor(env, args):
    return run_diagnostic(env, args, audit_skills, apply_skill_fixes)


# --------------------------------------------------------------------------------------------------
# doc-doctor: D1..D9
# --------------------------------------------------------------------------------------------------
EN_STOP = {"the", "and", "with", "for", "of", "is", "to", "from", "that"}
ES_STOP = {"el", "la", "los", "las", "de", "del", "en", "con", "para", "que", "es", "una", "un", "y"}


def headings(text):
    """## / ### headings outside fenced code blocks (code samples are exempt from the language check)."""
    text = re.sub(r"^```.*?^```[ \t]*$", "", text, flags=re.S | re.M)
    return [l for l in text.split("\n") if re.match(r"^#{2,3}\s", l)]


def audit_docs(env, cat, plugins, only_skills):
    F = []
    L = labels(env.docs_language)
    en = labels("en")
    pr_path = env.repo / "plugins" / "README.md"
    pr_lines = pr_path.read_text(encoding="utf-8").split("\n") if pr_path.is_file() else None
    for plugin in plugins:
        name = plugin["name"]
        skills = [s["name"] for s in plugin.get("skills", [])]
        spec = env.repo / (plugin.get("spec") or f"specs/{name}.md")
        if not spec.is_file():
            F.append(mk("CRITICAL", "D1", name, None, f"{spec.relative_to(env.repo)} does not exist", "auto"))
            stext = None
        else:
            stext = spec.read_text(encoding="utf-8")
            for key in ("overview", "changelog"):
                if not re.search(rf"^##\s+(?:{re.escape(en[key])}|{re.escape(L[key])})\b", stext, re.M | re.I):
                    F.append(mk("MAJOR", "D2", name, None, f"spec is missing required section: {L[key]}", "auto", section=key))
            for s in skills:
                if s.lower() not in stext.lower():
                    F.append(mk("MAJOR", "D3", name, s, "spec has no documentation for this skill", "auto"))
            m = re.search(r"\*\*(?:Version|Versión):\*\*\s*`([^`]+)`", stext)
            if m and m.group(1) != plugin["version"]:
                F.append(mk("MINOR", "D4", name, None, f"spec version header shows {m.group(1)}, catalog is at {plugin['version']}", "auto"))
        if pr_lines is None:
            F.append({"estado": "INFO", "id": "D5", "componente": name, "detalle": "plugins/README.md does not exist (D5/D6 skipped)",
                      "severity": "MINOR", "fix": "-", "plugin": name, "skill": None})
        else:
            i = plugin_row_idx(pr_lines, name)
            if i is None:
                F.append(mk("MAJOR", "D5", name, None, "plugins/README.md has no row for this plugin", "auto"))
            else:
                kc = col_index(table_headers(pr_lines, i), "skills")
                cells = split_row(pr_lines[i])
                if kc is not None and kc < len(cells):
                    listed = set(readme_skill_cells(cells[kc]))
                    miss = [s for s in skills if s not in listed]
                    if miss:
                        F.append(mk("MINOR", "D6", name, None, "plugins/README.md row is missing skill(s): " + ", ".join(miss), "auto"))
        rd = env.repo / plugin["path"] / "README.md"
        rtext = rd.read_text(encoding="utf-8") if rd.is_file() else None
        if rtext is None:
            F.append(mk("MAJOR", "D7", name, None, f"{plugin['path']}/README.md does not exist", "auto"))
        else:
            for s in skills:
                if f"`{s}`" not in rtext and f"/{name}:{s}" not in rtext:
                    F.append(mk("MAJOR", "D7", name, s, "README.md has no entry for this skill", "auto"))
            if any(d.get("type") == "plugin" for d in plugin.get("dependencies", []) or []) and \
                    not re.search(rf"^##\s+(?:{en['deps']}|{L['deps']})\b", rtext, re.M | re.I):
                F.append(mk("MAJOR", "D9", name, None, "plugin dependencies are not documented in README.md", "auto"))
        # D8: documentation language (heuristic, never auto-fixable)
        for label, text in (("spec", stext), ("README.md", rtext)):
            if not text:
                continue
            hs = headings(text)
            words = {w.lower() for h in hs for w in re.findall(r"[A-Za-zÀ-ÿ]+", h)}
            accented = any(re.search(r"[À-ÖØ-öø-ÿ]", h) for h in hs)
            if env.docs_language == "en":
                bad = accented or (bool(words & (ES_STOP - EN_STOP)) and not words & EN_STOP)
            elif env.docs_language == "es":
                bad = bool(words & (EN_STOP - ES_STOP)) and not words & ES_STOP
            else:
                bad = False
            if bad:
                F.append(mk("MAJOR", "D8", name, None, f"{label} headings do not look written in '{env.docs_language}'", "manual"))
    return sort_and_number(F)


def apply_doc_fixes(env, cat, selected, plan):
    files, applied, L, en = Files(), [], labels(env.docs_language), labels("en")
    for f in selected:
        plugin = next(p for p in cat["plugins"] if p["name"] == f["plugin"])
        name, spec = plugin["name"], env.repo / (plugin.get("spec") or f"specs/{plugin['name']}.md")
        rd = env.repo / plugin["path"] / "README.md"
        pr = env.repo / "plugins" / "README.md"
        i = f["id"]
        if i == "D1":
            plan.write_text(spec, spec_text(env, plugin), "spec generated from the catalog")
        elif i == "D2":
            t = files.get(spec)
            if f["section"] == "overview":
                t = re.sub(r"(\n---\n)", f"\\1\n## {L['overview']}\n\n{plugin['description']}\n\n---\n", t, count=1) \
                    if "\n---\n" in t else t.rstrip("\n") + f"\n\n## {L['overview']}\n\n{plugin['description']}\n"
            else:
                rows = "\n".join(f"| {c['version']} | {c['changes']} |" for c in plugin.get("changelog", []))
                t = t.rstrip("\n") + f"\n\n## {L['changelog']}\n\n| {L['version']} | {L['changes']} |\n|---------|---------|\n{rows}\n"
            files.set(spec, t)
        elif i == "D3":
            t = files.get(spec)
            sec = spec_skill_section(L, name, f["skill"], skill_desc_from_disk(env, plugin, f["skill"]))
            m = re.search(rf"^##\s+(?:{re.escape(en['changelog'])}|{re.escape(L['changelog'])})\b", t, re.M | re.I)
            t = t[:m.start()] + sec + "\n" + t[m.start():] if m else t.rstrip("\n") + "\n\n" + sec
            files.set(spec, t)
        elif i == "D4":
            t = files.get(spec)
            files.set(spec, re.sub(r"(\*\*(?:Version|Versión):\*\*\s*`)[^`]+(`)", lambda m: m.group(1) + plugin["version"] + m.group(2), t, count=1))
        elif i == "D5":
            t = plugins_readme_add_row(files.get(pr), name, plugin["status"], [s["name"] for s in plugin.get("skills", [])])
            if t is not None:
                files.set(pr, t)
        elif i == "D6":
            files.set(pr, plugins_readme_edit(files.get(pr), name, add_skill=None))
            lines = files.get(pr).split("\n")
            k = plugin_row_idx(lines, name)
            kc = col_index(table_headers(lines, k), "skills")
            cells = split_row(lines[k])
            if kc is not None and kc < len(cells):
                cells[kc] = ", ".join(f"`{s['name']}`" for s in plugin.get("skills", [])) or "—"
                lines[k] = join_row(cells)
                files.set(pr, "\n".join(lines))
        elif i == "D7":
            if not rd.is_file():
                plan.write_text(rd, readme_text(env, plugin), "README generated from the catalog")
            else:
                t = files.get(rd)
                t = plugin_readme_add_skill(t, name, f["skill"], skill_desc_from_disk(env, plugin, f["skill"]), marketplace_source(env))
                files.set(rd, t)
        elif i == "D9":
            t = files.get(rd)
            sec = deps_section(L, plugin)
            m = re.search(rf"^##\s+(?:{en['installation']}|{L['installation']})\b", t, re.M | re.I)
            t = t[:m.start()] + sec + t[m.start():] if m else t.rstrip("\n") + "\n\n" + sec
            files.set(rd, t)
        else:
            continue
        applied.append(f)
    files.flush(plan, "fix")
    return applied


def cmd_doc_audit(env, args):
    return run_diagnostic(env, args, audit_docs, apply_doc_fixes, {"docs_language": env.docs_language})


# --------------------------------------------------------------------------------------------------
# bootstrap: build specs/catalog.json from an existing marketplace
# --------------------------------------------------------------------------------------------------
CATEGORIES = {"productivity", "development", "security", "testing", "devops", "documentation", "other"}


def cmd_bootstrap(env, args):
    if env.catalog_exists:
        raise Precondition(f"{env.catalog_path} already exists: bootstrap only creates a missing catalog")
    lang = args.docs_language or "en"
    env.docs_language = lang
    mp_entries = {p.get("name"): p for p in env.mp.get("plugins", []) if isinstance(p, dict)}
    plugins, skipped = [], []
    for pdir in sorted((env.repo / "plugins").glob("*")):
        pj = pdir / ".claude-plugin" / "plugin.json"
        if not pj.is_file():
            if pdir.is_dir():
                skipped.append(f"plugins/{pdir.name} (no .claude-plugin/plugin.json — not a plugin)")
            continue
        meta = json.load(open(pj))
        name = meta.get("name") or pdir.name
        version = str(meta.get("version", "0.0.0"))
        if not re.fullmatch(r"\d+\.\d+\.\d+", version):
            skipped.append(f"plugins/{pdir.name} (version '{version}' is not X.Y.Z)")
            continue
        z = int(version.split(".")[2])
        mpe = mp_entries.get(name, {})
        skills = []
        for sk in sorted((pdir / "skills").glob("*/SKILL.md")):
            fm, _ = split_fm(sk.read_text(encoding="utf-8"))
            skills.append({"name": (fm_get(fm, "name") or sk.parent.name), "version": z,
                           "changelog": [{"version": z, "changes": "Bootstrap: imported from existing SKILL.md"}]})
        plugins.append({"name": name, "description": meta.get("description") or mpe.get("description") or name,
                        "category": mpe.get("category") if mpe.get("category") in CATEGORIES else "other",
                        "status": "beta", "version": version, "spec": f"specs/{name}.md", "path": f"plugins/{pdir.name}",
                        "changelog": [{"version": version, "changes": "Bootstrap: plugin registered in catalog.json"}],
                        "skills": skills})
    owner = env.mp.get("owner") if isinstance(env.mp.get("owner"), dict) else {"name": str(env.mp.get("owner", "unknown"))}
    cat = {"name": env.marketplace, "description": (env.mp.get("metadata") or {}).get("description") or env.mp.get("description") or env.marketplace,
           "owner": owner, "docs_language": lang, "plugins": plugins}
    plan = Plan(env, args.dry_run)
    for p in plugins:
        spec = env.repo / p["spec"]
        if not spec.exists():
            plan.write_text(spec, spec_text(env, p))
    plan.write_json(env.catalog_path, cat, "catalog created")
    plan.sync_global_catalog(cat)
    res = plan.run()
    emit_write_result("bootstrap", res, args, {"plugins": len(plugins), "skipped": "; ".join(skipped) or "none",
                                               "note": "SKILL.md files are not modified; run doctor --fix auto to add missing versions"})
    return EXIT_OK


# --------------------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------------------
def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repo")
    common.add_argument("--home")
    common.add_argument("--dry-run", action="store_true", dest="dry_run")
    common.add_argument("--json", action="store_true")
    common.add_argument("--allow-dirty", action="store_true", dest="allow_dirty")
    common.add_argument("--yes", action="store_true")
    ap = argparse.ArgumentParser(prog="p4cc_ops", description=__doc__.split('"""')[0])
    sub = ap.add_subparsers(dest="command", required=True)

    sub.add_parser("env", parents=[common])
    p = sub.add_parser("skill-update", parents=[common]); p.add_argument("plugin"); p.add_argument("skill"); p.add_argument("--change")
    p = sub.add_parser("skill-add", parents=[common]); p.add_argument("plugin"); p.add_argument("skill")
    p.add_argument("--description"); p.add_argument("--argument-hint", dest="argument_hint"); p.add_argument("--allowed-tools", dest="allowed_tools")
    p = sub.add_parser("skill-remove", parents=[common]); p.add_argument("plugin"); p.add_argument("skill")
    p.add_argument("--soft", action="store_true"); p.add_argument("--restore", action="store_true")
    p = sub.add_parser("update", parents=[common]); p.add_argument("plugin"); p.add_argument("--description"); p.add_argument("--status", choices=["proposal", "accepted", "beta", "stable", "production", "deprecated"])
    p.add_argument("--bump", choices=["none", "y", "x"], default="none"); p.add_argument("--change")
    p = sub.add_parser("remove", parents=[common]); p.add_argument("plugin")
    p.add_argument("--soft", action="store_true"); p.add_argument("--restore", action="store_true")
    p = sub.add_parser("create", parents=[common]); p.add_argument("plugin"); p.add_argument("--description")
    p.add_argument("--category", default="productivity", choices=sorted(CATEGORIES)); p.add_argument("--status", default="beta", choices=["proposal", "accepted", "beta", "stable", "production", "deprecated"])
    p.add_argument("--scope", action="append", choices=["global", "local", "local-gitignore"]); p.add_argument("--dep-tool", action="append", dest="dep_tool")
    p.add_argument("--dep-plugin", action="append", dest="dep_plugin"); p.add_argument("--skill", action="append")
    for c in ("doctor", "doc-audit"):
        p = sub.add_parser(c, parents=[common])
        p.add_argument("--plugin", action="append"); p.add_argument("--skill", action="append")
        p.add_argument("--report-only", action="store_true", dest="report_only")
        p.add_argument("--fix", default=None, metavar="auto|N,M,...")
    p = sub.add_parser("bootstrap", parents=[common]); p.add_argument("--docs-language", dest="docs_language", default="en")
    return ap


COMMANDS = {"env": cmd_env, "skill-update": cmd_skill_update, "skill-add": cmd_skill_add, "skill-remove": cmd_skill_remove,
            "update": cmd_update, "remove": cmd_remove, "create": cmd_create, "doctor": cmd_doctor,
            "doc-audit": cmd_doc_audit, "bootstrap": cmd_bootstrap}


def main(argv=None):
    ap = build_parser()
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return EXIT_USAGE if e.code not in (0, None) else EXIT_OK
    if getattr(args, "report_only", False) and getattr(args, "fix", None) is not None:
        print("usage error: --report-only and --fix are mutually exclusive", file=sys.stderr)
        return EXIT_USAGE
    try:
        env = resolve_env(args.repo, args.home)
        return COMMANDS[args.command](env, args)
    except Usage as e:
        print(f"FAIL|usage|{e}" if not args.json else json.dumps({"error": "usage", "detail": str(e)}), file=sys.stderr if not args.json else sys.stdout)
        return EXIT_USAGE
    except Precondition as e:
        if args.json:
            print(json.dumps({"error": "precondition", "detail": str(e), **e.payload}, indent=2, ensure_ascii=False, default=str))
        else:
            print(f"FAIL|precondition|{e}")
            for c in e.payload.get("candidates", []):
                print(f"INFO|candidate|{c}")
        return EXIT_PRECOND


if __name__ == "__main__":
    sys.exit(main())
