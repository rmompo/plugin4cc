---
name: doc-doctor
description: Audits documentation completeness and language for each plugin: verifies spec files, plugins/README.md listing, README.md skills tables, and English-only content against catalog ground truth. Reports findings and offers to generate or update missing content automatically. Also invoked explicitly as /p4cc-plugin:doc-doctor.
version: 47
argument-hint: "[plugin]"
allowed-tools: [Bash, Read, Write, Edit, AskUserQuestion]
---

# Doc Doctor

Audits and updates plugin documentation. Checks `specs/<plugin>.md`, `plugins/README.md`, `plugins/<plugin>/README.md`, and language compliance against `specs/catalog.json`. All content must be written in the marketplace's documentation language: `docs_language` in `specs/catalog.json` (default `en`).

```
REPO_ROOT      = resolved in Step 1 (P4CC_REPO → git root → walk-up → bounded search)
MARKETPLACE    = "name" of $REPO_ROOT/.claude-plugin/marketplace.json
CATALOG        = $REPO_ROOT/specs/catalog.json
MARKETPLACE_MD = $REPO_ROOT/plugins/README.md
DOCS_LANGUAGE  = "docs_language" in the catalog (default "en")
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
- **`catalog_exists` is false** → **STOP** and report it. Nothing is written. Point the user to `/p4cc-plugin:skill-doctor`, whose Step 1b offers a *bootstrap* that creates the catalog (after a dry-run and an explicit confirmation); then re-run this skill.

From here on, `REPO_ROOT`, `MARKETPLACE`, `CATALOG`, `CACHE_BASE`, `GLOBAL_CATALOG`, `GLOBAL_CATALOG_WRITABLE` and `DOCS_LANGUAGE` (`docs_language`) are the values printed above.

**Write boundaries.** This skill writes only inside `REPO_ROOT` and the single file `GLOBAL_CATALOG` (under `~/.p4cc/`). It **never writes to the Claude Code cache**: `CACHE_BASE` is read-only, because the cache is managed by Claude Code (`/plugin`) and deleting or replacing a version it has registered as installed breaks the plugin. For `plugin4cc` these are exactly the paths it always used (`~/.p4cc/catalog.json`, `~/.claude/plugins/cache/plugin4cc`); for any other marketplace `GLOBAL_CATALOG` is `~/.p4cc/catalog-<marketplace>.json`. If `GLOBAL_CATALOG` exists and its `name` is not `MARKETPLACE`, `GLOBAL_CATALOG_WRITABLE` is `false` and it is never modified.

Read `CATALOG` into memory.

---

## Step 2 — Select scope

If the skill was invoked with a `$ARGUMENTS` value, use it as the plugin filter and skip the question.

Otherwise, use **AskUserQuestion** to ask:

- **All plugins** — audit every plugin registered in catalog
- **Specific plugin** — pick from the plugin list in catalog

Build the **audit scope**: a list of plugin names to check.

---

## Step 3 — Run checks

For each plugin in scope, run all checks below. Collect every finding into a list.

Each finding has:
- `plugin`
- `check`: check ID (D1–D8)
- `severity`: `CRITICAL` / `MAJOR` / `MINOR`
- `fix`: `[auto]` or `[manual]`
- `defect`: what is wrong
- `detail`: specific missing element or value
- `mitigation`: concrete action to fix it

### Check battery

#### D1 — Spec file missing  `CRITICAL · [auto]`

Check whether `$REPO_ROOT/specs/<plugin>.md` exists.

```bash
test -f "$REPO_ROOT/specs/<plugin>.md"
```

If missing → defect. Auto-fix generates the full spec from catalog data.

```
Defect:    specs/<plugin>.md does not exist
Mitigate:  generate spec file from catalog entry
```

#### D2 — Spec missing required sections  `MAJOR · [auto]`

Read `specs/<plugin>.md`. Check for the presence of these sections (case-insensitive heading match):

| Required section | Pattern to match |
|-----------------|-----------------|
| Overview | `## Overview` |
| Changelog | `## Changelog` |

For each missing section → one finding.

```
Defect:    specs/<plugin>.md is missing required section: <section>
Mitigate:  add <section> section with template content
```

#### D3 — Spec missing section for a catalog skill  `MAJOR · [auto]`

For each skill listed in `catalog["skills"]` for this plugin, check whether the spec references it.

Accept either format:
- Explicit section: `## Skill: \`<skill>\`` or `## Skill: <skill>`
- Skills table row: a Markdown table row or list item containing the skill name

```bash
grep -i "<skill>" "$REPO_ROOT/specs/<plugin>.md"
```

If the skill name does not appear anywhere in the spec → defect.

```
Defect:    specs/<plugin>.md has no documentation for skill: <skill>
Mitigate:  add ## Skill: `<skill>` section with Purpose, Invocation, Non-Goals
```

#### D4 — Spec version header does not match catalog  `MINOR · [auto]`

Look for the version string in the spec status line (e.g., `**Version:** \`1.1.9\``).

Compare against `catalog["plugins"][plugin]["version"]`.

If they differ → defect.

```
Defect:    spec version header shows <A>, catalog is at <B>
Mitigate:  update version string in spec status line
```

#### D5 — Plugin not listed in plugins/README.md  `MAJOR · [auto]`

Read `$REPO_ROOT/plugins/README.md`.

Check whether a row exists for this plugin in the "Available plugins" table (match on plugin name in the first column).

If not found → defect. Auto-fix adds a new row.

```
Defect:    plugins/README.md has no row for plugin <plugin>
Mitigate:  add row: | [`<plugin>`](./<plugin>/README.md) | <status> | `<skills>` | — |
```

#### D6 — plugins/README.md row has incomplete skills list  `MINOR · [auto]`

Parse the plugins/README.md row for this plugin. Extract the skills listed in the "Skills" column.

Compare against all skills in `catalog["skills"]` for this plugin.

If any skill is missing from the row → defect.

```
Defect:    plugins/README.md row for <plugin> is missing skill(s): <skill1>, <skill2>
Mitigate:  update skills column to: `<skill1>`, `<skill2>`, ...
```

#### D7 — README.md missing or skills table incomplete  `MAJOR · [auto]`

Check `$REPO_ROOT/plugins/<plugin>/README.md`:

1. If file does not exist → defect (generate full README).
2. If file exists, check that every skill in `catalog["skills"]` appears in the README.
   - If any skill is absent → defect (add missing rows).

```
Defect:    plugins/<plugin>/README.md does not exist
Mitigate:  generate README.md from catalog data

Defect:    plugins/<plugin>/README.md is missing entry for skill: <skill>
Mitigate:  add row to skills table: | `<skill>` | `/<plugin>:<skill>` | <description> |
```

**Note:** D7 is always `[auto]` — the README content is derived deterministically from catalog data and SKILL.md descriptions.

#### D9 — Plugin dependencies not documented in README.md  `MAJOR · [auto]`

If the plugin has any `type: "plugin"` entries in its `dependencies` array, the `README.md` must document them.

Check whether `plugins/<plugin>/README.md` contains a `## Dependencies` section listing the required plugins.

```
Defect:    plugin has type:"plugin" dependencies but README.md has no ## Dependencies section
Mitigate:  add ## Dependencies section to README.md listing the required plugins with install instructions
```

Auto-fix generates a `## Dependencies` section inserted before `## Installation`:

```markdown
## Dependencies

This plugin requires the following plugins to be installed:

| Plugin | Install |
|--------|---------|
| `<plugin>` | `claude plugins install <plugin>` |
```

---

#### D8 — Documentation not in the declared language  `MAJOR · [auto]`

All plugin documentation must be written in `DOCS_LANGUAGE` (`docs_language` in `specs/catalog.json`, default `en`). A marketplace documented in Spanish declares `"docs_language": "es"`, and Spanish prose is then **correct** — never flag it. Check the following files:
- `specs/<plugin>.md`
- `plugins/<plugin>/README.md`

**If `DOCS_LANGUAGE` is `en`**, scan each file for:
1. `##` and `###` headings with non-ASCII characters (accented letters indicate non-English).
2. Common non-English stopwords in headings or in the Overview / description paragraphs (e.g. Spanish: `el`, `la`, `los`, `de`, `del`, `en`, `con`, `para`, `que`, `es`, `una`).
3. Any section that is visually identifiable as non-English prose.

```bash
grep -P '[^\x00-\x7F]' "$REPO_ROOT/specs/<plugin>.md"
grep -P '[^\x00-\x7F]' "$REPO_ROOT/plugins/<plugin>/README.md"
```

**If `DOCS_LANGUAGE` is anything else** (e.g. `es`), do **not** use the ASCII test — accents are expected. Flag only prose or headings that are clearly written in a *different* language than `DOCS_LANGUAGE` (typically English sections inside a Spanish-documented marketplace). For Spanish, English stopwords in headings or the Overview (`the`, `and`, `with`, `for`, `of`, `is`) are the signal. For any other language use your judgment of the prose language and report the finding as `[manual]`.

In every language, code blocks, identifiers, command names, file paths and technical terms are exempt.

```
Defect:    specs/<plugin>.md contains content not written in <DOCS_LANGUAGE> in section: <section>
Mitigate:  translate affected section to <DOCS_LANGUAGE>

Defect:    plugins/<plugin>/README.md contains content not written in <DOCS_LANGUAGE>
Mitigate:  rewrite affected content in <DOCS_LANGUAGE>
```

---

## Step 4 — Emit findings report

If **no findings**: print `✅ No documentation gaps found in the audited scope.` and stop.

If findings exist, print:

```
══════════════════════════════════════════
  DOC DOCTOR REPORT
  Scope: [all | <plugin>]
  Audited: N plugins · D9 checks each
══════════════════════════════════════════
```

Then print the findings table:

| # | plugin | check | severity | fix | defect | detail | mitigation plan |
|---|--------|-------|----------|-----|--------|--------|-----------------|
| 1 | p4cc-buddy | D1 | CRITICAL | [auto] | spec file missing | specs/p4cc-buddy.md | generate from catalog |
| 2 | p4cc-plugin | D3 | MAJOR | [auto] | skill not documented | skill-doctor | add ## Skill: `skill-doctor` section |
| 3 | p4cc-core | D7 | MAJOR | [auto] | README.md missing skill | skill-list | add row to skills table |
| 4 | p4cc-plugin | D8 | MAJOR | [auto] | content not in docs language (en) | specs/p4cc-plugin.md §Overview | translate to <DOCS_LANGUAGE> |

Sort by: severity (`CRITICAL` first, then `MAJOR`, then `MINOR`), then plugin ASC, then check ASC.

Print summary footer:
```
Findings: N total · C critical · M major · m minor
Auto-fixable: A · Manual: B
```

---

## Step 5 — Offer fixes

Use **AskUserQuestion** to ask what to do:

- **Fix all auto-fixable** — apply every `[auto]` fix automatically
- **Fix specific findings** — user selects by number (e.g. `1, 3, 5`)
- **Nothing — report only** — exit without changes

If "nothing" → print `Report saved. No changes applied.` and stop.

---

## Step 6 — Apply auto fixes

Apply each selected `[auto]` fix as follows.

### D1 — Generate full spec file

Generate `specs/<plugin>.md` using the canonical template, populating it with data from `catalog`. All content must be in `DOCS_LANGUAGE` (default English; translate the template headings when it is another language):

```markdown
# Plugin Spec: <plugin>

> **Status:** `<status>` | **Version:** `<version>`

## Overview

<plugin description from catalog — in English>

---

## Skill: `<skill>`

### Purpose
<skill purpose inferred from SKILL.md description — in DOCS_LANGUAGE>

### Invocation
/<plugin>:<skill> [args]

### Non-Goals
- <to be defined>

---

## Changelog

| Version | Changes |
|---------|---------|
<entries from catalog plugin changelog — in DOCS_LANGUAGE>
```

### D2 — Add missing top-level section

Use the Edit tool to insert the missing section at the correct position:

- **Overview**: insert after the status line
- **Changelog**: append at end, generated from `catalog["plugins"][plugin]["changelog"]`

### D3 — Add missing skill section

Use the Edit tool to insert before `## Changelog` (or append if absent):

```markdown
---

## Skill: `<skill>`

### Purpose
<description from catalog skill entry — in DOCS_LANGUAGE>

### Invocation
/<plugin>:<skill>

### Non-Goals
- <to be defined>
```

### D4 — Update spec version header

Use the Edit tool to replace the version string in the status line:

```
**Version:** `<old>` → **Version:** `<new>`
```

### D5 — Add plugin row to plugins/README.md

Use the Edit tool to insert a new row in the "Available plugins" table before the closing blank line:

```
| [`<plugin>`](./<plugin>/README.md) | <status> | `<skill1>`, `<skill2>`, ... | — |
```

### D6 — Update plugins/README.md skills column

Use the Edit tool to replace the row's skills column with the complete list from catalog:

```
`skill1`, `skill2`, `skill3`, ...
```

### D7 — Generate or update README.md

**If README.md does not exist**, use the Write tool to create it:

```markdown
# <plugin>

<description from catalog — in DOCS_LANGUAGE>

## Skills

| Skill | Invocation | Description |
|-------|-----------|-------------|
| `<skill>` | `/<plugin>:<skill>` | <first sentence of SKILL.md description> |

## Installation

```bash
claude plugins marketplace add <marketplace-source>
claude plugins install <plugin>
```
```

**If README.md exists but is missing skills**, use the Edit tool to insert the missing row(s) into the skills table. Read the skill description from the SKILL.md frontmatter (first sentence before ". Also invoked").

All README content must be in `DOCS_LANGUAGE`.

### D8 — Fix content in the wrong language

Use the Edit tool to translate or rewrite the identified section(s) to `DOCS_LANGUAGE`. Preserve all technical terms, code blocks, and Markdown structure — only the prose content is translated.

### D9 — Add plugin dependencies section to README.md

Use the Edit tool to insert a `## Dependencies` section before `## Installation` in `plugins/<plugin>/README.md`:

```markdown
## Dependencies

This plugin requires the following plugins to be installed:

| Plugin | Install |
|--------|---------|
| `<plugin>` | `claude plugins install <plugin>` |
```

List one row per `type: "plugin"` entry in the plugin's `dependencies` array.

---

## Step 7 — Summary

```
══════════════════════════════════════════
  DOC DOCTOR SUMMARY
══════════════════════════════════════════
  Fixed (auto):     N findings
  Skipped (manual): M findings
  Unchanged:        K findings

  Modified files:
    specs/<plugin>.md
    plugins/<plugin>/README.md
    plugins/README.md

══════════════════════════════════════════

Next steps:
  1. Review generated/updated content
  2. git add + commit + push
```
