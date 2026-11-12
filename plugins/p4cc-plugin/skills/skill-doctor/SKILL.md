---
name: skill-doctor
description: Audits plugin skills for version mismatches, frontmatter issues, allowed-tools gaps, catalog inconsistencies, and structural defects. Emits a prioritized findings report and offers to fix auto-correctable defects. Also invoked explicitly as /p4cc-plugin:skill-doctor.
version: 50
argument-hint: "[plugin] [skill]"
allowed-tools: [Bash, Read, Write, Edit, AskUserQuestion]
---

# Skill Check

Audits one or more plugin skills for defects and inconsistencies. Produces a findings report with severity, fix type, and mitigation plan. Optionally auto-fixes eligible defects.

```
REPO_ROOT    = resolved in Step 1 (P4CC_REPO → git root → walk-up → bounded search)
MARKETPLACE  = "name" of $REPO_ROOT/.claude-plugin/marketplace.json
CATALOG      = $REPO_ROOT/specs/catalog.json
CACHE_BASE   = ~/.claude/plugins/cache/$MARKETPLACE   (read-only)
GLOBAL_CATALOG = ~/.p4cc/catalog.json (plugin4cc) | ~/.p4cc/catalog-$MARKETPLACE.json
```

---

## Step 1 — Resolve the marketplace environment and read the catalog

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
- **`catalog_exists` is false** → this skill stays **read-only** and goes to **Step 1b** (bootstrap offer) instead of auditing.

From here on, `REPO_ROOT`, `MARKETPLACE`, `CATALOG`, `CACHE_BASE`, `GLOBAL_CATALOG`, `GLOBAL_CATALOG_WRITABLE` and `DOCS_LANGUAGE` (`docs_language`) are the values printed above.

**Write boundaries.** This skill writes only inside `REPO_ROOT` and the single file `GLOBAL_CATALOG` (under `~/.p4cc/`). It **never writes to the Claude Code cache**: `CACHE_BASE` is read-only, because the cache is managed by Claude Code (`/plugin`) and deleting or replacing a version it has registered as installed breaks the plugin. For `plugin4cc` these are exactly the paths it always used (`~/.p4cc/catalog.json`, `~/.claude/plugins/cache/plugin4cc`); for any other marketplace `GLOBAL_CATALOG` is `~/.p4cc/catalog-<marketplace>.json`. If `GLOBAL_CATALOG` exists and its `name` is not `MARKETPLACE`, `GLOBAL_CATALOG_WRITABLE` is `false` and it is never modified.

Read `CATALOG` into memory. Read the list of installed plugins from `CACHE_BASE`.

---

## Step 1b — Missing catalog: bootstrap (read-only until confirmed)

Reached only when `catalog_exists` is `false`. Until the user confirms, **nothing is written**. Start by reporting:

```
⚠️  specs/catalog.json not found in marketplace <MARKETPLACE> (<REPO_ROOT>).
    No audit is possible without it. Nothing was written.
```

Then offer to build the catalog from what is already in the repo:

1. Use **AskUserQuestion** to ask for the documentation language of this marketplace (`docs_language`): **English (`en`)**, **Spanish (`es`)** or other (free text). It is stored in the catalog and used by `doc-doctor`.
2. Run the bootstrap in **dry-run** mode and show the plan to the user (plugins found with their versions, skills per plugin, directories skipped, and the exact list of files it would write):

```bash
REPO_ROOT=<REPO_ROOT> MARKETPLACE=<MARKETPLACE> GLOBAL_CATALOG=<GLOBAL_CATALOG> \
GLOBAL_CATALOG_WRITABLE=<true|false> DOCS_LANGUAGE=<en|es|...> BOOT_MODE=dry-run python3 - <<'PY'
import copy, json, os, re, shutil, sys
from pathlib import Path

# Inputs (set by the skill): REPO_ROOT, MARKETPLACE, GLOBAL_CATALOG, GLOBAL_CATALOG_WRITABLE (true/false),
# BOOT_MODE = dry-run | apply, DOCS_LANGUAGE (e.g. en, es)
repo = Path(os.environ["REPO_ROOT"])
marketplace = os.environ["MARKETPLACE"]
gcat = Path(os.environ["GLOBAL_CATALOG"])
g_writable = os.environ.get("GLOBAL_CATALOG_WRITABLE", "true").lower() == "true"
mode = os.environ.get("BOOT_MODE", "dry-run")
lang = os.environ.get("DOCS_LANGUAGE", "en")
CATEGORIES = {"productivity", "development", "security", "testing", "devops", "documentation", "other"}

catalog_path = repo / "specs" / "catalog.json"
if catalog_path.exists():
    sys.exit(f"ERROR: {catalog_path} already exists — bootstrap only creates a missing catalog")

mp = json.load(open(repo / ".claude-plugin" / "marketplace.json"))
mp_entries = {p.get("name"): p for p in mp.get("plugins", []) if isinstance(p, dict)}

def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    return m.group(1) if m else ""

def fm_field(fm, key):
    m = re.search(rf"^{key}:\s*(.+)$", fm, re.M)
    if not m:
        return ""
    v = m.group(1).strip()
    return "" if v in (">", "|", ">-", "|-") else v.strip("\"'")

plugins, skipped, spec_files = [], [], []
for pdir in sorted((repo / "plugins").glob("*")):
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
    entry_mp = mp_entries.get(name, {})
    desc = meta.get("description") or entry_mp.get("description") or name
    cat = entry_mp.get("category") if entry_mp.get("category") in CATEGORIES else "other"
    skills = []
    for sk in sorted((pdir / "skills").glob("*/SKILL.md")):
        fm = frontmatter(sk.read_text(encoding="utf-8"))
        sname = fm_field(fm, "name") or sk.parent.name
        skills.append({"name": sname, "version": z,
                       "changelog": [{"version": z, "changes": "Bootstrap: imported from existing SKILL.md"}],
                       "_description": fm_field(fm, "description")})
    plugins.append({
        "name": name, "description": desc, "category": cat, "status": "beta", "version": version,
        "spec": f"specs/{name}.md", "path": f"plugins/{pdir.name}",
        "changelog": [{"version": version, "changes": "Bootstrap: plugin registered in catalog.json"}],
        "skills": skills})

L = {"es": dict(title="Especificación del plugin", status="Estado", version="Versión", overview="Descripción general",
                skills="Skills", skill="Skill", desc="Descripción", changelog="Historial de cambios", changes="Cambios",
                boot="Bootstrap: plugin registrado en catalog.json", none="_Sin skills._"),
     "en": dict(title="Plugin Spec", status="Status", version="Version", overview="Overview",
                skills="Skills", skill="Skill", desc="Description", changelog="Changelog", changes="Changes",
                boot="Bootstrap: plugin registered in catalog.json", none="_No skills._")}.get(lang) or None
if L is None:
    L = {"title": "Plugin Spec", "status": "Status", "version": "Version", "overview": "Overview", "skills": "Skills",
         "skill": "Skill", "desc": "Description", "changelog": "Changelog", "changes": "Changes",
         "boot": "Bootstrap: plugin registered in catalog.json", "none": "_No skills._"}

def spec_md(p):
    def cell(t):
        return t.replace("|", "\\|")
    rows = "\n".join("| `%s` | %s | %s |" % (s["name"], s["version"], cell(s["_description"])) for s in p["skills"]) \
        or L["none"]
    table = f"| {L['skill']} | {L['version']} | {L['desc']} |\n|-------|---------|-------------|\n{rows}" if p["skills"] else rows
    return (f"# {L['title']}: {p['name']}\n\n> **{L['status']}:** `{p['status']}` | **{L['version']}:** `{p['version']}`\n\n---\n\n"
            f"## {L['overview']}\n\n{p['description']}\n\n---\n\n## {L['skills']}\n\n{table}\n\n---\n\n"
            f"## {L['changelog']}\n\n| {L['version']} | {L['changes']} |\n|---------|---------|\n| {p['version']} | {L['boot']} |\n")

owner = mp.get("owner") if isinstance(mp.get("owner"), dict) else {"name": str(mp.get("owner", "unknown"))}
description = (mp.get("metadata") or {}).get("description") or mp.get("description") or marketplace
catalog = {"name": marketplace, "description": description, "owner": owner, "docs_language": lang,
           "plugins": copy.deepcopy(plugins)}
for p in catalog["plugins"]:
    for s in p["skills"]:
        s.pop("_description", None)

writes = [("specs/catalog.json", "create")]
for p in plugins:
    f = repo / "specs" / f"{p['name']}.md"
    writes.append((f"specs/{p['name']}.md", "skip (exists)" if f.exists() else "create"))
writes.append((str(gcat), ("create/replace" if g_writable else "SKIP — belongs to another marketplace")))

plan = {"mode": mode, "marketplace": marketplace, "docs_language": lang,
        "plugins": [{"name": p["name"], "version": p["version"], "skills": len(p["skills"]),
                     "skill_version_assigned": int(p["version"].split(".")[2])} for p in plugins],
        "skipped": skipped, "writes": writes,
        "note": "SKILL.md files are NOT modified by bootstrap; run skill-doctor afterwards to add any missing 'version:' frontmatter"}

if mode == "apply":
    (repo / "specs").mkdir(exist_ok=True)
    for p in plugins:                      # specs first, catalog LAST: a crash never leaves an orphan catalog
        f = repo / "specs" / f"{p['name']}.md"
        if not f.exists():
            f.write_text(spec_md(p), encoding="utf-8")
    catalog_path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if g_writable:
        gcat.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(catalog_path, gcat)
print(json.dumps(plan, indent=2, ensure_ascii=False))
PY
```

3. Use **AskUserQuestion** to ask for confirmation to apply it (`Apply` / `Cancel`). On cancel → stop, nothing written.
4. Run the same block with `BOOT_MODE=apply`. It writes `specs/<plugin>.md` for every plugin that lacks one (never overwriting), then `specs/catalog.json` last, then copies the catalog to `GLOBAL_CATALOG` only if `GLOBAL_CATALOG_WRITABLE` is true.
5. Re-run Step 1 and continue with the audit.

What the bootstrap creates, so you can explain it to the user:
- **Plugins**: one entry per `plugins/<dir>/.claude-plugin/plugin.json`, keeping the existing `X.Y.Z` version; directories without `plugin.json` are skipped and reported. `status` is `beta` and `category` is taken from `marketplace.json` (or `other`) — both are placeholders to review.
- **Skills**: one entry per `plugins/<dir>/skills/*/SKILL.md`, with `version` = the **Z of its plugin** (integer) and a changelog entry `Bootstrap: imported from existing SKILL.md`.
- **Specs**: a minimal `specs/<plugin>.md` per plugin, written in `docs_language` (`es` and `en` have localized headings).
- `SKILL.md` files are **not modified**. Skills without a `version:` line are reported by check **C1** below as an auto-fixable defect.

---

## Step 2 — Select scope

Use **AskUserQuestion** to ask the user what to audit:

- **All plugins — all skills** — full audit of everything installed
- **Specific plugin — all its skills** — show a sub-question to pick the plugin
- **Specific plugin:skill** — show plugin picker then skill picker

If "specific plugin" or "specific plugin:skill" is selected, present the available options from `CATALOG` as follow-up questions.

Build the **audit scope**: a list of `{plugin, skill}` pairs to check.

---

## Step 3 — Run checks

For each `{plugin, skill}` in scope, run the full battery of checks below. Collect every finding into a list.

Each finding has:
- `plugin`, `skill`
- `severity`: `CRITICAL` / `MAJOR` / `MINOR`
- `fix`: `[auto]` (can be corrected without human judgment) or `[manual]` (requires human review)
- `defect`: what is wrong
- `mitigation`: concrete action to fix it

### Check battery

#### C1 — SKILL.md version vs catalog  `CRITICAL · [auto]`
Read `$REPO_ROOT/plugins/<plugin>/skills/<skill>/SKILL.md` frontmatter `version`.
Read `catalog["skills"][skill]["version"]` (if the skill has no catalog entry, use the **Z of its plugin**).
- If they differ → defect.
- If the frontmatter has **no `version:` line** → defect too (auto-correctable: the value is the catalog version, i.e. the Z of the plugin).
```
Defect:    SKILL.md version: X ≠ catalog version: Y
Mitigate:  update SKILL.md frontmatter: version: X → Y

Defect:    SKILL.md has no version in its frontmatter
Mitigate:  insert "version: Y" before the closing --- of the frontmatter (Y = catalog version / plugin Z)
```

#### C2 — plugin.json version vs catalog  `CRITICAL · [auto]`
Read `$REPO_ROOT/plugins/<plugin>/.claude-plugin/plugin.json` → `version`.
Read catalog plugin entry → `version`.
If they differ → defect.
```
Defect:    plugin.json version: X ≠ catalog version: Y
Mitigate:  update plugin.json: "version": "X" → "Y"
```

#### C3 — Installed version differs from plugin.json  `MINOR · [manual]`
**Advisory and read-only.** The Claude Code cache is managed by Claude Code (`/plugin`); this skill never writes to it.
Read the installed version of the plugin from `~/.claude/plugins/installed_plugins.json` (entry `<plugin>@$MARKETPLACE`, field `version`); if there is no entry, fall back to the highest versioned directory under `$CACHE_BASE/<plugin>/`. Compare it with `plugin.json`.
- Installed is lower than `plugin.json` → an update is pending (normal right after a change).
- Installed is higher than `plugin.json` → the installed copy is newer than this repo.
- Not installed → nothing to report.
```
Defect:    installed vX, plugin.json at vY
Mitigate:  git push, then in Claude Code: /plugin → update the marketplace and <plugin>, then /reload-plugins
```

#### C4 — Missing required frontmatter fields  `CRITICAL · [manual]`
SKILL.md frontmatter must contain: `name`, `description`, `allowed-tools`. (A missing `version` is reported by **C1**, not here.)
Flag each missing field individually.
```
Defect:    missing frontmatter field: <field>
Mitigate:  add <field> to SKILL.md frontmatter
```

#### C5 — allowed-tools gaps  `MAJOR · [manual]`
Scan the SKILL.md body for **explicit tool invocation signals** only. Do NOT match generic prose words — only patterns that unambiguously reference the Claude Code tool by name.

| Signal in body | Required tool | Rationale |
|---|---|---|
| `AskUserQuestion` | `AskUserQuestion` | Class name, no ambiguity |
| ` ```bash` | `Bash` | Fenced bash block = Bash tool invocation |
| `Read tool` or `the Read tool` or `Use Read` | `Read` | Explicit tool reference |
| `Write tool` or `the Write tool` or `Use Write` | `Write` | Explicit tool reference |
| `Edit tool` or `the Edit tool` or `Use Edit` | `Edit` | Explicit tool reference |

**Do NOT flag** on:
- `Read ` (space) alone — matches "Read this file", "Read requirements from catalog" (prose)
- `Write ` (space) alone — matches "Write the subject", "Write the entire response" (prose)
- `Edit ` (space) alone — matches "Edit `field`" in table cells (prose)
- `Bash` alone — matches "bash command", "Bash script" (prose)

For each tool signalled in the body but absent from `allowed-tools` → defect.
```
Defect:    body uses <tool> but it is not in allowed-tools
Mitigate:  add <tool> to allowed-tools list in SKILL.md frontmatter
```

#### C6 — Plugin has dependencies but no install skill  `MAJOR · [manual]`
A plugin must have a skill named `install` if **any** of the following is true:
- `catalog["plugins"][plugin]["dependencies"]` is non-empty (plugin-level dependency)
- Any skill in the plugin has `catalog["skills"][skill]["dependencies"]` non-empty (skill-level dependency)

Check reported once per plugin, not per skill.

The `install` skill must verify **all dependency types**:
- `type: "tool"` — check via `which <name>` and compare version against constraint
- `type: "plugin"` — check via `ls $CACHE_BASE/<name>/` (installed if directory has at least one entry); install with `claude plugins install <name>`

The status table must include a `Type` column to distinguish tools from plugins.

```
Defect:    plugin has dependencies (plugin-level or skill-level) but no install skill
Mitigate:  create an install skill with /p4cc-plugin:skill-add
```

#### C7 — Description missing "Also invoked" suffix  `MINOR · [auto]`
SKILL.md description must end with `. Also invoked explicitly as /<plugin>:<skill>` (with optional args suffix).
```
Defect:    description missing standard invocation suffix
Mitigate:  append ". Also invoked explicitly as /<plugin>:<skill>." to description
```

#### C8 — Catalog changelog missing entry for current version  `MINOR · [auto]`
In `catalog["skills"][skill]["changelog"]`, the first entry `version` must equal `catalog["skills"][skill]["version"]`.
```
Defect:    no changelog entry for current skill version <V>
Mitigate:  insert {"version": V, "changes": "<describe>"} as first entry
```

#### C9 — skill-level dependencies in catalog not documented in SKILL.md  `MINOR · [manual]`
If `catalog["skills"][skill]["dependencies"]` is set, check that the SKILL.md body mentions the required tool(s) or plugin(s) explicitly (at least once).
```
Defect:    skill depends on <name> in catalog but body never references it
Mitigate:  add dependency verification step or note to SKILL.md body
```

---

## Step 4 — Emit findings report

If **no findings**: print `✅ No defects found in the audited scope.` and stop.

If findings exist, print:

```
══════════════════════════════════════════
  SKILL CHECK REPORT
  Scope: [all | <plugin> | <plugin>:<skill>]
  Audited: N plugins · M skills
══════════════════════════════════════════
```

Then print the findings table:

| # | plugin | skill | severity | fix | defect | mitigation plan |
|---|---|---|---|---|---|---|
| 1 | p4cc-core | skill-list | CRITICAL | [auto] | SKILL.md version 7 ≠ catalog version 8 | update SKILL.md frontmatter version: 7 → 8 |
| 2 | p4cc-ccvv | generate | MAJOR | [manual] | body uses AskUserQuestion but not in allowed-tools | add AskUserQuestion to allowed-tools |
| 3 | p4cc-converter | any-to-md | MINOR | [auto] | description missing invocation suffix | append ". Also invoked explicitly as /p4cc-converter:any-to-md." |

Sort by: severity (`CRITICAL` first, then `MAJOR`, then `MINOR`), then plugin ASC, then skill ASC.

Print summary footer:
```
Findings: N total · C critical · M major · m minor
Auto-fixable: A · Manual: B
```

---

## Step 5 — Offer fixes

Use **AskUserQuestion** to ask the user what to fix:

- **Fix all auto-fixable** — apply every `[auto]` fix automatically
- **Fix specific findings** — user selects by number (e.g. `1, 3, 5`)
- **Nothing — report only** — exit without changes

If "nothing" → print `Report saved. No changes applied.` and stop.

---

## Step 6 — Apply auto fixes

For each selected `[auto]` finding, apply the mitigation programmatically:

**C1 — SKILL.md version:**
```python
import re
skill_md = f"{REPO_ROOT}/plugins/{plugin}/skills/{skill}/SKILL.md"
text = open(skill_md, encoding="utf-8").read()
m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
fm = m.group(1)
if re.search(r"^version:", fm, re.M):
    fm = re.sub(r"^version:.*$", f"version: {catalog_version}", fm, count=1, flags=re.M)
else:                                   # no version line: insert it
    fm = fm + f"\nversion: {catalog_version}"
open(skill_md, "w", encoding="utf-8").write(f"---\n{fm}\n---\n" + text[m.end():])
```

**C2 — plugin.json version:**
```python
pj = json.load(open(pj_path))
pj["version"] = catalog_version
open(pj_path, 'w').write(json.dumps(pj, indent=2, ensure_ascii=False) + '\n')
```

**C7 — Description suffix:**
```bash
# Append suffix to description line in SKILL.md frontmatter
```

**C8 — Changelog entry:**
```python
skill_entry["changelog"].insert(0, {"version": new_Z, "changes": "version bump"})
open(catalog_path, 'w').write(json.dumps(catalog, indent=2, ensure_ascii=False) + '\n')
```

For `[manual]` findings that were selected → print:
```
⚠️  Finding #N is [manual] — cannot be auto-fixed.
    Defect:   <defect>
    Action:   <mitigation plan>
```

---

## Step 7 — Summary

```
══════════════════════════════════════════
  FIX SUMMARY
══════════════════════════════════════════
  Fixed (auto):   N findings
  Skipped (manual): M findings
  Unchanged:      K findings

  Modified files:
    plugins/<plugin>/skills/<skill>/SKILL.md
    plugins/<plugin>/.claude-plugin/plugin.json
    specs/catalog.json

══════════════════════════════════════════

Next steps:
  1. Review manual findings above
  2. git add + commit + push
  3. In Claude Code: `/plugin` → update the marketplace and `<plugin>` (the cache is managed by Claude Code, never by this skill), then `/reload-plugins`
```
