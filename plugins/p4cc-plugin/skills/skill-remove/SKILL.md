---
name: skill-remove
description: Removes a skill from a plugin. Deletes the SKILL.md, updates catalog.json (Z does not decrease), and syncs the CLI cache. Destructive — requires explicit confirmation. Also invoked explicitly as /p4cc-plugin:skill-remove with the plugin and skill name.
version: 42
argument-hint: "<plugin> <skill>"
allowed-tools: [Bash, Read, Edit, Write, AskUserQuestion]
---

# Skill Remover

Removes a skill from a plugin. **Destructive — the skill directory is deleted.**

Z does **not** decrease on removal — the counter is monotonic.

---

## Step 0 — Resolve the marketplace environment

Everything this skill touches is resolved **before anything is written**. The skill works with any marketplace, not only `plugin4cc`. Resolution order for the repo: `P4CC_REPO` environment variable → git root of the current directory → walk up from the current directory → bounded last-resort search (depth ≤ 6, never inside `~/.claude`, never an unbounded `find ~`). If the last resort finds several repos it asks; it never picks the first one silently.

```bash
python3 - <<'PY'
import json, os, subprocess, sys
from pathlib import Path

HOME = Path.home()
MP = ".claude-plugin/marketplace.json"

def out(d, code=0):
    print(json.dumps(d, indent=2, ensure_ascii=False)); sys.exit(code)

def has_mp(p):
    return (Path(p) / MP).is_file()

def git_root(cwd):
    try:
        return subprocess.check_output(["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
                                       stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return None

cwd = Path.cwd()
repo, via, notes = None, None, []
cwd_repo = git_root(cwd)
cwd_repo = cwd_repo if cwd_repo and has_mp(cwd_repo) else None

# 1. P4CC_REPO
env = os.environ.get("P4CC_REPO")
if env:
    if not has_mp(Path(env).expanduser()):
        out({"status": "error", "error": f"P4CC_REPO={env} does not contain {MP}"}, 2)
    repo, via = Path(env).expanduser().resolve(), "env P4CC_REPO"
    if cwd_repo and Path(cwd_repo).resolve() != repo:
        notes.append(f"P4CC_REPO ({repo}) differs from the marketplace repo of the current directory ({cwd_repo})")
# 2. git root of cwd
if not repo and cwd_repo:
    repo, via = Path(cwd_repo).resolve(), "git root of cwd"
# 3. walk up from cwd
if not repo:
    for d in [cwd, *cwd.parents]:
        if has_mp(d):
            repo, via = d.resolve(), "walk-up from cwd"
            break
# 4. last resort: BOUNDED find (depth 6, skipping Claude's own plugin clones/caches, .git, node_modules)
if not repo:
    res = subprocess.run(
        ["find", str(HOME), "-maxdepth", "6",
         "(", "-name", "node_modules", "-o", "-name", ".git", "-o", "-path", str(HOME / ".claude"), ")", "-prune",
         "-o", "-type", "f", "-path", "*/.claude-plugin/marketplace.json", "-print"],
        capture_output=True, text=True)
    cands = sorted({str(Path(l).parent.parent) for l in res.stdout.splitlines() if l.strip()})
    if len(cands) > 1:
        out({"status": "ambiguous", "candidates": cands,
             "action": "ask the user which repo to use; never pick the first one silently"}, 3)
    if not cands:
        out({"status": "error", "error": "no .claude-plugin/marketplace.json found. "
             "Run from inside the marketplace repo or set P4CC_REPO."}, 2)
    repo, via = Path(cands[0]), "find (last resort)"
    notes.append("repo located by the last-resort search")

try:
    mp = json.load(open(repo / MP))
except Exception as e:
    out({"status": "error", "error": f"cannot read {repo / MP}: {e}"}, 2)
marketplace = mp.get("name")
if not marketplace:
    out({"status": "error", "error": f"{repo / MP} has no 'name' field"}, 2)

catalog = repo / "specs" / "catalog.json"
catalog_exists = catalog.is_file()
docs_language, cat_name = "en", None
if catalog_exists:
    try:
        cj = json.load(open(catalog))
        docs_language = cj.get("docs_language", "en")
        cat_name = cj.get("name")
    except Exception as e:
        out({"status": "error", "error": f"cannot parse {catalog}: {e}"}, 2)
    if cat_name and cat_name != marketplace:
        notes.append(f"catalog name '{cat_name}' differs from marketplace name '{marketplace}'")

gdir = HOME / ".p4cc"
gcat = gdir / ("catalog.json" if marketplace == "plugin4cc" else f"catalog-{marketplace}.json")
writable = True
if gcat.exists():
    try:
        writable = json.load(open(gcat)).get("name") == marketplace
    except Exception:
        writable = False
    if not writable:
        notes.append(f"{gcat} belongs to another marketplace (or is unreadable): it will NOT be touched")

try:
    remote = subprocess.check_output(["git", "-C", str(repo), "remote", "get-url", "origin"],
                                     stderr=subprocess.DEVNULL, text=True).strip()
except Exception:
    remote = None

out({"status": "ok", "REPO_ROOT": str(repo), "MARKETPLACE": marketplace, "resolved_via": via,
     "CATALOG": str(catalog), "catalog_exists": catalog_exists, "docs_language": docs_language,
     "CACHE_BASE": str(HOME / ".claude" / "plugins" / "cache" / marketplace),
     "GLOBAL_CATALOG": str(gcat), "GLOBAL_CATALOG_WRITABLE": writable,
     "git_remote": remote, "confirm_needed": bool(notes), "notes": notes})
PY
```

Show the user `REPO_ROOT`, `MARKETPLACE`, `CATALOG`, the cache path (`CACHE_BASE/<plugin>/<version>/`) and `GLOBAL_CATALOG` **before writing anything**, then act on the result:

- **Exit 0, `confirm_needed: false`** → continue.
- **`confirm_needed: true`** → print `notes` and ask with **AskUserQuestion** whether to continue with exactly these paths. Stop if the answer is no.
- **Exit 3 (`ambiguous`)** → ask with **AskUserQuestion** which candidate to use, then re-run the block with `P4CC_REPO=<choice>`. Never choose one silently.
- **Exit 2 (`error`)** → stop and show the error.
- **`catalog_exists` is false** → **STOP**. Tell the user that `specs/catalog.json` does not exist in marketplace `$MARKETPLACE` and that `/p4cc-plugin:skill-doctor` offers a *bootstrap* (its Step 1b) that builds the catalog from the plugins already in the repo, after a dry-run and an explicit confirmation. Run it, then re-run this skill. Never invent catalog entries by hand.

From here on, `REPO_ROOT`, `MARKETPLACE`, `CATALOG`, `CACHE_BASE`, `GLOBAL_CATALOG`, `GLOBAL_CATALOG_WRITABLE` and `DOCS_LANGUAGE` (`docs_language`) are the values printed above.

**Write boundaries.** This skill writes only inside `REPO_ROOT`, the single file `GLOBAL_CATALOG` (under `~/.p4cc/`) and `CACHE_BASE`. For `plugin4cc` these are exactly the paths it always used (`~/.p4cc/catalog.json`, `~/.claude/plugins/cache/plugin4cc`); for any other marketplace `GLOBAL_CATALOG` is `~/.p4cc/catalog-<marketplace>.json`. If `GLOBAL_CATALOG` exists and its `name` is not `MARKETPLACE`, `GLOBAL_CATALOG_WRITABLE` is `false` and it is never modified.

---

## Step 1 — Read current state

```python
import json
catalog = json.load(open(f"{REPO_ROOT}/specs/catalog.json"))
plugin_entry = next(p for p in catalog["plugins"] if p["name"] == plugin_name)
skill_entry = next((s for s in plugin_entry["skills"] if s["name"] == skill_name), None)
```

If skill not found → report and exit.

---

## Step 2 — Confirm via AskUserQuestion

Use **AskUserQuestion**:
- question: `"¿Confirmas la eliminación del skill <skill> de <plugin>? Esta acción no se puede deshacer."`
- header: `"Confirmar"`
- options: `["Sí, eliminar", "Cancelar"]`

Only proceed if user confirms. On cancel → exit immediately.

---

## Step 3 — Delete skill directory

```bash
rm -rf REPO_ROOT/plugins/<plugin>/skills/<skill>/
```

---

## Step 4 — Update catalog.json

Z does NOT change. Only remove the skill entry and record a changelog:

```python
import json
catalog_path = f"{REPO_ROOT}/specs/catalog.json"
catalog = json.load(open(catalog_path))
plugin_entry = next(p for p in catalog["plugins"] if p["name"] == plugin_name)

# Remove skill
plugin_entry["skills"] = [s for s in plugin_entry["skills"] if s["name"] != skill_name]

# Record in plugin changelog (version unchanged)
current_version = plugin_entry["version"]
plugin_entry["changelog"].insert(0, {
    "version": current_version,
    "changes": f"Remove {skill_name} skill"
})

open(catalog_path, 'w').write(json.dumps(catalog, indent=2, ensure_ascii=False) + '\n')
```

---

## Step 4b — Sync catalog to the global catalog (`$GLOBAL_CATALOG`)

```python
import shutil, os
if GLOBAL_CATALOG_WRITABLE:   # False → the file belongs to another marketplace: never touch it
    os.makedirs(os.path.dirname(GLOBAL_CATALOG), exist_ok=True)
    shutil.copy2(catalog_path, GLOBAL_CATALOG)
else:
    print(f"⚠️  {GLOBAL_CATALOG} belongs to another marketplace — left untouched")
```

---

## Step 4c — Update README.md

Use the Edit tool to remove the row for `<skill>` from the skills table in `REPO_ROOT/plugins/<plugin>/README.md`.

Find the row matching the skill name and delete it. If no skills table exists or the skill is not listed, skip silently.

---

## Step 4d — Update marketplace files

### `plugins/README.md`

Find the row for `<plugin>` in the Available plugins table and remove `<skill>` from the **Skills** column. If it was the only skill, replace with `—`.

---

## Step 5 — Sync cache (no version bump)

```python
import shutil, os, json

plugin_dir = f"{REPO_ROOT}/plugins/{plugin_name}"
version = json.load(open(f"{plugin_dir}/.claude-plugin/plugin.json"))["version"]
cache_base = f"{CACHE_BASE}/{plugin_name}"
os.makedirs(cache_base, exist_ok=True)
for old in os.listdir(cache_base): shutil.rmtree(f"{cache_base}/{old}")
dst = f"{cache_base}/{version}"
shutil.copytree(plugin_dir, dst, ignore=shutil.ignore_patterns('.git'))
for item in os.listdir(plugin_dir):
    if item.startswith('.') and item != '.git':
        s, d = f"{plugin_dir}/{item}", f"{dst}/{item}"
        if os.path.isdir(s):
            if os.path.exists(d): shutil.rmtree(d)
            shutil.copytree(s, d)
```

---

## Summary output

```
✅ Skill removed: /<plugin>:<skill>

Plugin <plugin>: v<version> (Z unchanged — removal does not bump Z)

Deleted:
  plugins/<plugin>/skills/<skill>/

Updated:
  plugins/<plugin>/README.md

Marketplaces updated:
  specs/catalog.json  →  $GLOBAL_CATALOG (synced)
  plugins/README.md  (Skills column)

Cache synced: $CACHE_BASE/<plugin>/<version>/

Next steps:
  1. git add + commit + push
  2. claude plugins update <plugin>
```
