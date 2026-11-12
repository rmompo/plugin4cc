---
name: create
description: Scaffolds a new plugin with all required files and registers it in every catalog. Also invoked explicitly as /p4cc-plugin:create with the plugin name and optional skill names.
version: 45
argument-hint: "<plugin> [skill1 skill2 ...]"
allowed-tools: [Bash, Read, Edit, Write, AskUserQuestion]
---

# Plugin Creator

Scaffolds a complete new plugin and registers it in all catalogs and the Claude Code cache.

```
specs/catalog.json                              ← PRIMARY — written first
   ↓
plugins/<plugin>/.claude-plugin/plugin.json     ← minimal plugin metadata
.claude-plugin/marketplace.json                 ← Claude Code marketplace index
plugins/README.md                               ← human-readable plugin index
specs/<plugin>.md                               ← plugin spec file
$CACHE_BASE/                     ← Claude Code cache
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

Show the user `REPO_ROOT`, `MARKETPLACE`, `CATALOG`, the cache path (`CACHE_BASE/<plugin>/<version>/`) and `GLOBAL_CATALOG` **before writing anything**, then act on the result:

- **Exit 0, `confirm_needed: false`** → continue.
- **`confirm_needed: true`** → print `notes` and ask with **AskUserQuestion** whether to continue with exactly these paths. Stop if the answer is no.
- **Exit 3 (`ambiguous`)** → ask with **AskUserQuestion** which candidate to use, then re-run the block with `P4CC_REPO=<choice>`. Never choose one silently.
- **Exit 2 (`error`)** → stop and show the error.
- **`catalog_exists` is false** → **STOP**. Tell the user that `specs/catalog.json` does not exist in marketplace `$MARKETPLACE` and that `/p4cc-plugin:skill-doctor` offers a *bootstrap* (its Step 1b) that builds the catalog from the plugins already in the repo, after a dry-run and an explicit confirmation. Run it, then re-run this skill. Never invent catalog entries by hand.

From here on, `REPO_ROOT`, `MARKETPLACE`, `CATALOG`, `CACHE_BASE`, `GLOBAL_CATALOG`, `GLOBAL_CATALOG_WRITABLE` and `DOCS_LANGUAGE` (`docs_language`) are the values printed above.

**Write boundaries.** This skill writes only inside `REPO_ROOT`, the single file `GLOBAL_CATALOG` (under `~/.p4cc/`) and `CACHE_BASE`. For `plugin4cc` these are exactly the paths it always used (`~/.p4cc/catalog.json`, `~/.claude/plugins/cache/plugin4cc`); for any other marketplace `GLOBAL_CATALOG` is `~/.p4cc/catalog-<marketplace>.json`. If `GLOBAL_CATALOG` exists and its `name` is not `MARKETPLACE`, `GLOBAL_CATALOG_WRITABLE` is `false` and it is never modified.

---

## Step 1 — Collect info

If not provided as arguments, use **AskUserQuestion** to collect:

1. Plugin name (kebab-case; follow the prefix the marketplace already uses, e.g. `p4cc-<descriptor>` in plugin4cc, `arkana-<descriptor>` in arkana)
2. Plugin description (one line)
3. Category (default: `productivity`)
4. Initial status (default: `beta`)
5. Scopes (optional — select from `global`, `local`, `local-gitignore`, or none)
6. Dependencies (optional):
   - **Tool dependencies** — binary name + version constraint. Operators: `=x.y.z`, `>=x.y.z`, `>x.y.z`, `<=x.y.z`, `<x.y.z`, `>=x.y.z <a.b.c`, `*`. Example: `pandoc >=2.0.0`, `python3 >=3.10.0`
   - **Plugin dependencies** — other plugins of this marketplace this plugin relies on. Example: `p4cc-converter`. No version — always latest.
7. Skill name(s) and brief purpose of each (optional — can add later with `skill-add`)
### Naming conventions

**Plugin:** `p4cc-{container}` — domain or category grouping related skills.

**Skill:** `[subject-]{action}` — action is mandatory, subject is optional.

**Invocation:** `/p4cc-{container}:[subject-]{action}`

### Install skill convention

**If the plugin declares `dependencies`**, always scaffold a `install` skill as the first skill (Z=1). The `install` skill must:

1. Read the full `dependencies` array from `catalog.json` for this plugin
2. For each dependency, check by type:
   - `type: "tool"` → run `which <name> && <name> --version 2>&1 | head -1`, then compare version against constraint
   - `type: "plugin"` → run `ls $CACHE_BASE/<name>/` — installed if directory has at least one entry
3. Print a unified Markdown table with a `Type` column:
   ```markdown
   | Type | Dependency | Required | Found | Status |
   |------|------------|----------|-------|--------|
   | tool | pandoc     | >=2.0.0  | 3.1.3 | ✅     |
   | plugin | p4cc-core  | —        | ✅    | ✅     |
   ```
   Status: ✅ if present (and version satisfied for tools), ❌ if missing
4. For each ❌, show install instructions:
   - `type: "tool"` — `apt`/`brew` (Bash) and `winget`/`choco` (PowerShell)
   - `type: "plugin"` — `claude plugins install <name>`
5. Be idempotent — safe to re-run at any time

---

## Step 2 — Assign versions

- Plugin starts at `1.0.0` (no skills) or `1.0.<N>` (N skills provided)
- First skill → Z=1, second → Z=2, etc.

---

## Step 3 — Create plugin files

Create `REPO_ROOT/plugins/<plugin>/`:

```
<plugin>/
├── .claude-plugin/
│   └── plugin.json
├── skills/
│   └── <skill>/
│       └── SKILL.md
└── README.md
```

If the plugin needs a session-start agent (auto-setup behavior), also create:
```
├── agents/
│   └── <plugin>.md
└── settings.json     ← {"agent": "<plugin>"}
```

**`.claude-plugin/plugin.json`** (minimal — all metadata lives in catalog.json):
```json
{
  "name": "<plugin>",
  "version": "1.0.<Z>",
  "description": "<one-line description>",
  "author": {
    "name": "rmompo",
    "email": "rmompo@gmail.com"
  },
  "scopes": ["<scope1>", "<scope2>"]   ← omit if no persistent storage needed
}
```

**`skills/<skill>/SKILL.md`**:
```markdown
---
name: <skill>
description: <what it does>. Also invoked explicitly as /<plugin>:<skill> with optional args.
version: <Z>
argument-hint: "[optional args]"
allowed-tools: [Bash, Read, Edit, Write]
---

# <Skill Title>

<Brief description.>

---

## TODO: define skill steps here
```

**`README.md`**:
```markdown
# <plugin>

<One paragraph description.>

## Skills

| Skill | Invocation | What it does |
|-------|-----------|--------------|
| `<skill>` | `/<plugin>:<skill>` | <description> |

## Installation

\`\`\`bash
claude plugins marketplace add <marketplace-source>
claude plugins install <plugin>
\`\`\`
```

---

## Step 4 — Create spec file

Create `REPO_ROOT/specs/<plugin>.md`:

```markdown
# Plugin Spec: <plugin>

> **Status:** `beta` | **Version:** `1.0.<Z>`

## Overview

<Description.>

---

## Skill: `<skill>`

### Purpose
<What it does.>

### Invocation
\`\`\`
/<plugin>:<skill> [args]
\`\`\`

### Non-Goals
- <What it does NOT do>

---

## Changelog

| Version | Changes |
|---------|---------|
| 1.0.<Z> | Initial release |
```

---

## Step 5 — Update catalog.json

Add plugin entry:

```json
{
  "name": "<plugin>",
  "description": "<description>",
  "category": "<category>",
  "status": "<status>",
  "version": "1.0.<Z>",
  "spec": "specs/<plugin>.md",
  "path": "plugins/<plugin>",
  "scopes": ["<scope1>"],              ← omit if no persistent storage needed
  "dependencies": [                    ← omit if no dependencies needed
    {"type": "tool",   "name": "<binary>",  "version": "<constraint>"},
    {"type": "plugin", "name": "<plugin>"}
  ],
  "changelog": [
    {"version": "1.0.<Z>", "changes": "Initial release"}
  ],
  "skills": [
    {
      "name": "<skill>",
      "version": <Z>,
      "changelog": [{"version": <Z>, "changes": "Initial release"}]
    }
  ]
}
```

---

## Step 5b — Sync catalog to the global catalog (`$GLOBAL_CATALOG`)

```python
import shutil, os
if GLOBAL_CATALOG_WRITABLE:   # False → the file belongs to another marketplace: never touch it
    os.makedirs(os.path.dirname(GLOBAL_CATALOG), exist_ok=True)
    shutil.copy2(f"{REPO_ROOT}/specs/catalog.json", GLOBAL_CATALOG)
else:
    print(f"⚠️  {GLOBAL_CATALOG} belongs to another marketplace — left untouched")
```

---

## Step 7 — Update marketplace files

### 7.1 — `plugins/README.md`

Add row to the "Available plugins" table in alphabetical order:

```
| [`<plugin>`](./<plugin>/README.md) | <status> | `<skill1>`, `<skill2>` | <auto-setup> |
```

- `<status>`: from Step 1 (e.g. `beta`)
- Skills: comma-separated list of all implemented skills (exclude proposal)
- `<auto-setup>`: `✅ via agent` if the plugin has `settings.json` + `agents/<plugin>.md`; otherwise `—`

### 7.2 — `.claude-plugin/marketplace.json`

Add entry to the `"plugins"` array:

```json
{
  "name": "<plugin>",
  "description": "<description>",
  "author": {"name": "<owner.name from marketplace.json>"},
  "category": "<category>",
  "source": "./plugins/<plugin>",
  "homepage": "<git remote url without .git>/tree/main/plugins/<plugin>"
}
```

The homepage comes from `git_remote` (Step 0); omit the field if there is no remote. `<marketplace-source>` in READMEs is the `owner/repo` of that remote.

> If a marketplace has no `plugins/README.md` or no root `README.md`, skip the corresponding step and say so in the summary — never create them implicitly.

---

## Step 7b — Update root README.md

Insert a row for the new plugin **in alphabetical order** in the plugins table of `REPO_ROOT/README.md` (columns `Plugin | Description | Status | Spec`):

```markdown
| `<plugin>` | <one-line description> | `<status>` | [spec](./specs/<plugin>.md) |
```

---

## Step 8 — Sync cache

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
✅ Plugin created: <plugin> v1.0.<Z>

Files created:
  plugins/<plugin>/.claude-plugin/plugin.json
  plugins/<plugin>/skills/<skill>/SKILL.md
  plugins/<plugin>/README.md
  specs/<plugin>.md

Marketplaces updated:
  specs/catalog.json  →  $GLOBAL_CATALOG (synced)
  .claude-plugin/marketplace.json
  plugins/README.md
  README.md  (plugins table — alphabetical)

Cache synced: $CACHE_BASE/<plugin>/1.0.<Z>/

Next steps:
  1. Fill in skill logic in skills/<skill>/SKILL.md
  2. git add + commit + push
  3. claude plugins install <plugin>
```
