---
name: create
description: Scaffolds a new plugin with all required files and registers it in every catalog. Also invoked explicitly as /p4cc-plugin:create with the plugin name and optional skill names.
version: 59
argument-hint: "<plugin> [skill1 skill2 ...] [--description \"<text>\"] [--category c] [--status s] [--scope s] [--dep-tool \"name >=x\"] [--dep-plugin p] [--dry-run] [--json] [--repo PATH] [--home DIR]"
allowed-tools: [Bash, AskUserQuestion]
---

# Plugin Creator

Scaffolds a complete new plugin and registers it in the catalogs. It does not touch the Claude Code cache.

```
specs/catalog.json                              ← PRIMARY — written first
   ↓
plugins/<plugin>/.claude-plugin/plugin.json     ← minimal plugin metadata
.claude-plugin/marketplace.json                 ← Claude Code marketplace index
plugins/README.md · README.md                   ← human-readable indexes (rows added alphabetically; skipped if absent)
specs/<plugin>.md                               ← plugin spec file
```

---

## Engine

All the logic lives in one script shared by the p4cc-plugin skills, so a dry-run and a real run execute **the same code** (a single function decides whether anything is written):

```bash
# <Base directory for this skill> is shown when the skill is loaded; the engine is two levels up
ENGINE="<Base directory for this skill>/../../resources/scripts/p4cc_ops.py"
[ -f "$ENGINE" ] || ENGINE="$(ls -d ~/.claude/plugins/cache/*/p4cc-plugin/*/ 2>/dev/null | sort -V | tail -1)resources/scripts/p4cc_ops.py"
python3 "$ENGINE" create <plugin> --description "…" [options]
```

The engine resolves the marketplace itself, in this order: `--repo PATH` → `P4CC_REPO` → git root of the current directory → walk up to `.claude-plugin/marketplace.json` → a bounded last-resort search (never an unbounded `find ~`; several hits → exit 3 listing the candidates, never "the first one"). `--home DIR` (or `P4CC_HOME`) replaces `~` for `~/.p4cc/`.

**Write boundaries.** Only inside the repo, the single global catalog file of *this* marketplace under `~/.p4cc/` (`catalog.json` for plugin4cc, `catalog-<marketplace>.json` otherwise; another marketplace's file is never touched) and `<repo>/.p4cc/bak/`. **Never the Claude Code cache** (managed by `/plugin`). Nothing is ever installed.

---

## Step 1 — Collect info

If not provided as arguments and the invocation is interactive, use **AskUserQuestion** to collect:

1. Plugin name (kebab-case; follow the prefix the marketplace already uses, e.g. `p4cc-<descriptor>` in plugin4cc, `arkana-<descriptor>` in arkana)
2. Plugin description (one line)
3. Category (default: `productivity`) and initial status (default: `beta`)
4. Scopes (optional — `global`, `local`, `local-gitignore`)
5. Dependencies (optional): **tool** dependencies as `name constraint` (operators `=x.y.z`, `>=x.y.z`, `>x.y.z`, `<=x.y.z`, `<x.y.z`, `>=x.y.z <a.b.c`, `*`; e.g. `pandoc >=2.0.0`, `python3 >=3.10.0`) and **plugin** dependencies (other plugins of this marketplace, no version)
6. Skill names with a brief purpose each (optional — can be added later with `skill-add`)

With `--yes` or `--json` never ask: a missing `--description` is exit 2.

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

## Step 2 — Run the engine

```bash
python3 "$ENGINE" create <plugin> --description "<text>" [--category <c>] [--status <s>] [--scope <s>]... \
  [--dep-tool "<name> <constraint>"]... [--dep-plugin <plugin>]... [--skill "<name>:<purpose>"]... [--dry-run] [--json] [--repo PATH] [--home DIR]
```

Versions: the plugin starts at `1.0.<N>` for N skills; the first skill is Z=1, the second Z=2… When dependencies are declared and no `install` skill is given, the engine scaffolds `install` as the first skill. `marketplace.json` entries copy the keys the marketplace already uses (`author`, `category`, `homepage`…). A missing `plugins/README.md` or root `README.md` is skipped with a note, never created implicitly.

### Options

| Option | Meaning |
|--------|---------|
| `--repo PATH` | Marketplace repo (same as `P4CC_REPO`; the flag wins when both are given) |
| `--home DIR` | Home directory used for `~/.p4cc/` (same as `P4CC_HOME`; default `$HOME`) |
| `--dry-run` | Resolve and validate everything, **write nothing**, print the exact plan (`DRY\|create\|modify\|delete\|<path>`) and end with `RESUMEN\|DRY\|…` instead of `RESUMEN\|OK\|…` |
| `--json` | Machine-readable output (valid JSON) |


### Output and exit codes

One line per item, `STATE|ID|detail` (`STATE` ∈ `OK`, `INFO`, `WARN`, `FAIL`, `DRY`), then a final `RESUMEN|…` line. Exit codes: **0** no failures · **1** failures found · **2** bad usage · **3** precondition not met (no repo, no catalog, ambiguous repo, uncommitted changes).

---

## Step 3 — Report

Show the engine output as is. Next steps: fill in the skill logic in `skills/<skill>/SKILL.md`, `git add` + commit + push, then `/plugin` → update the marketplace and install `<plugin>`.
