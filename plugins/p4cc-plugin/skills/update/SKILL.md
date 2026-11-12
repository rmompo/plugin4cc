---
name: update
description: Updates plugin metadata (description, status, version bump) and propagates changes to the catalogs. Never touches the Claude Code cache. Also invoked explicitly as /p4cc-plugin:update with the plugin name.
version: 53
argument-hint: "<plugin>"
allowed-tools: [Bash, Read, Edit, Write, AskUserQuestion]
---

# Plugin Updater

Updates plugin metadata and propagates changes to the catalogs. It does not touch the Claude Code cache.

```
specs/catalog.json                                    ← PRIMARY — written first
   ↓
plugins/<plugin>/.claude-plugin/plugin.json        ← version if bumped
.claude-plugin/marketplace.json                       ← description/skills if changed
plugins/README.md                             ← description/status/skills if changed
README.md                                             ← status column if plugin status changed
```

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

Show the user `REPO_ROOT`, `MARKETPLACE`, `CATALOG`, the cache base (`CACHE_BASE`, read-only) and `GLOBAL_CATALOG` **before writing anything**, then act on the result:

- **Exit 0, `confirm_needed: false`** → continue.
- **`confirm_needed: true`** → print `notes` and ask with **AskUserQuestion** whether to continue with exactly these paths. Stop if the answer is no.
- **Exit 3 (`ambiguous`)** → ask with **AskUserQuestion** which candidate to use, then re-run the block with `P4CC_REPO=<choice>`. Never choose one silently.
- **Exit 2 (`error`)** → stop and show the error.
- **`catalog_exists` is false** → **STOP**. Tell the user that `specs/catalog.json` does not exist in marketplace `$MARKETPLACE` and that `/p4cc-plugin:skill-doctor` offers a *bootstrap* (its Step 1b) that builds the catalog from the plugins already in the repo, after a dry-run and an explicit confirmation. Run it, then re-run this skill. Never invent catalog entries by hand.

From here on, `REPO_ROOT`, `MARKETPLACE`, `CATALOG`, `CACHE_BASE`, `GLOBAL_CATALOG`, `GLOBAL_CATALOG_WRITABLE` and `DOCS_LANGUAGE` (`docs_language`) are the values printed above.

**Write boundaries.** This skill writes only inside `REPO_ROOT` and the single file `GLOBAL_CATALOG` (under `~/.p4cc/`). It **never writes to the Claude Code cache**: `CACHE_BASE` is read-only, because the cache is managed by Claude Code (`/plugin`) and deleting or replacing a version it has registered as installed breaks the plugin. For `plugin4cc` these are exactly the paths it always used (`~/.p4cc/catalog.json`, `~/.claude/plugins/cache/plugin4cc`); for any other marketplace `GLOBAL_CATALOG` is `~/.p4cc/catalog-<marketplace>.json`. If `GLOBAL_CATALOG` exists and its `name` is not `MARKETPLACE`, `GLOBAL_CATALOG_WRITABLE` is `false` and it is never modified.

---

## Step 1 — Read current state

```python
import json
catalog = json.load(open(f"{REPO_ROOT}/specs/catalog.json"))
plugin = next((p for p in catalog["plugins"] if p["name"] == plugin_name), None)
X, Y, Z = map(int, plugin["version"].split("."))
```

Show the user the current values before asking what to change.

---

## Step 2 — Collect changes

Use **AskUserQuestion** to collect what needs updating:

1. New description (leave blank to keep current)
2. New status (`proposal` / `accepted` / `beta` / `stable` / `production` / `deprecated`)
3. Version bump type (`none` / `patch X.Y+1.Z` / `major X+1.0.Z`) — Z is never reset manually
4. Changelog entry description (required if any change is made)

---

## Step 3 — Update catalog.json

Apply all collected changes:
- Update `description`, `status`, `version` as needed
- Prepend to `changelog`: `{"version": "X.Y.Z", "changes": "<description>"}`

---

## Step 3b — Sync catalog to the global catalog (`$GLOBAL_CATALOG`)

```python
import shutil, os
catalog_path = f"{REPO_ROOT}/specs/catalog.json"
if GLOBAL_CATALOG_WRITABLE:   # False → the file belongs to another marketplace: never touch it
    os.makedirs(os.path.dirname(GLOBAL_CATALOG), exist_ok=True)
    shutil.copy2(catalog_path, GLOBAL_CATALOG)
else:
    print(f"⚠️  {GLOBAL_CATALOG} belongs to another marketplace — left untouched")
```

---

## Step 4 — Update derived files

Apply updates to all files affected by the collected changes. Check each trigger independently:

### Claude Code files (always applicable)

- `plugins/<plugin>/.claude-plugin/plugin.json` → update `version` if bumped
- `.claude-plugin/marketplace.json` → update `description` if changed; update skill list in `source` entry if skills changed
- `plugins/README.md` → update `status` column if status changed; update `Skills` column if skills changed; update `Auto-setup` column if agent was added/removed

### Root documentation

- `README.md` (repo root) → update `status` column in the plugins table if plugin status changed. If missing, insert in alphabetical order following `create` Step 7b.

---

## Summary output

```
✅ Plugin updated: <plugin> v<old> → v<new>

Changes applied:
  <list of what changed>

Catalogs updated:
  specs/catalog.json  →  $GLOBAL_CATALOG (synced)
  [.claude-plugin/marketplace.json — if description/skills changed]
  [plugins/README.md — if description/status/skills changed]
  [README.md — if status changed]

Next steps:
  1. git add + commit + push
  2. In Claude Code: `/plugin` → update the marketplace and `<plugin>` (the cache is managed by Claude Code, never by this skill), then `/reload-plugins`
```
