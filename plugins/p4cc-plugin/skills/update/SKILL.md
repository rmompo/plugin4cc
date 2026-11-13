---
name: update
description: Updates plugin metadata (description, status, version bump) and propagates changes to the catalogs. Never touches the Claude Code cache. Also invoked explicitly as /p4cc-plugin:update with the plugin name.
version: 57
argument-hint: "<plugin> [--description \"<text>\"] [--status <s>] [--bump none|y|x] [--change \"<text>\"] [--dry-run] [--json] [--repo PATH] [--home DIR] [--allow-dirty]"
allowed-tools: [Bash, AskUserQuestion]
---

# Plugin Updater

Updates plugin metadata and propagates changes to the catalogs. It does not touch the Claude Code cache.

```
specs/catalog.json                       ← PRIMARY — written first
   ↓
plugins/<plugin>/.claude-plugin/plugin.json   ← version if bumped
.claude-plugin/marketplace.json               ← description if changed
plugins/README.md · README.md                 ← status column if status changed (located by header name)
```

---

## Engine

All the logic lives in one script shared by the p4cc-plugin skills, so a dry-run and a real run execute **the same code** (a single function decides whether anything is written):

```bash
# <Base directory for this skill> is shown when the skill is loaded; the engine is two levels up
ENGINE="<Base directory for this skill>/../../resources/scripts/p4cc_ops.py"
[ -f "$ENGINE" ] || ENGINE="$(ls -d ~/.claude/plugins/cache/*/p4cc-plugin/*/ 2>/dev/null | sort -V | tail -1)resources/scripts/p4cc_ops.py"
python3 "$ENGINE" update <plugin> [--description "…"] [--status …] [--bump none|y|x] --change "…" [options]
```

The engine resolves the marketplace itself, in this order: `--repo PATH` → `P4CC_REPO` → git root of the current directory → walk up to `.claude-plugin/marketplace.json` → a bounded last-resort search (never an unbounded `find ~`; several hits → exit 3 listing the candidates, never "the first one"). `--home DIR` (or `P4CC_HOME`) replaces `~` for `~/.p4cc/`.

**Write boundaries.** Only inside the repo, the single global catalog file of *this* marketplace under `~/.p4cc/` (`catalog.json` for plugin4cc, `catalog-<marketplace>.json` otherwise; another marketplace's file is never touched) and `<repo>/.p4cc/bak/`. **Never the Claude Code cache** (managed by `/plugin`). Nothing is ever installed.

---

## Step 1 — Collect the changes

Show the current values (`python3 "$ENGINE" env` plus the catalog entry) and, when changes are not given as options and the invocation is interactive, ask with **AskUserQuestion**: (1) new description (blank keeps the current one), (2) new status (`proposal` / `accepted` / `beta` / `stable` / `production` / `deprecated`), (3) bump type (`none` / `y` = `X.Y+1.Z` / `x` = `X+1.0.Z` — Z is never reset by hand), (4) the changelog entry (required when anything changes). With `--yes` or `--json` never ask.

---

## Step 2 — Run the engine

```bash
python3 "$ENGINE" update <plugin> [--description "<text>"] [--status <status>] [--bump none|y|x] --change "<text>" [--dry-run] [--json] [--repo PATH] [--home DIR] [--allow-dirty]
```

Files it would modify are copied to `<repo>/.p4cc/bak/<timestamp>/files/` first (`0600`); add `.p4cc/` to `.gitignore` or `.git/info/exclude` (the engine warns when it is not).

### Options

| Option | Meaning |
|--------|---------|
| `--repo PATH` | Marketplace repo (same as `P4CC_REPO`; the flag wins when both are given) |
| `--home DIR` | Home directory used for `~/.p4cc/` (same as `P4CC_HOME`; default `$HOME`) |
| `--dry-run` | Resolve and validate everything, **write nothing**, print the exact plan (`DRY\|create\|modify\|delete\|<path>`) and end with `RESUMEN\|DRY\|…` instead of `RESUMEN\|OK\|…` |
| `--json` | Machine-readable output (valid JSON) |
| `--allow-dirty` | Skip the "uncommitted changes in the files to modify" check |


### Output and exit codes

One line per item, `STATE|ID|detail` (`STATE` ∈ `OK`, `INFO`, `WARN`, `FAIL`, `DRY`), then a final `RESUMEN|…` line. Exit codes: **0** no failures · **1** failures found · **2** bad usage · **3** precondition not met (no repo, no catalog, ambiguous repo, uncommitted changes).

---

## Step 3 — Report

Show the engine output as is. Next steps: `git add` + commit + push, then In Claude Code: `/plugin` → update the marketplace and `<plugin>` (the cache is managed by Claude Code, never by this skill), then `/reload-plugins`.
