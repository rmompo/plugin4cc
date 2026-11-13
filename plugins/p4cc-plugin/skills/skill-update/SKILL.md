---
name: skill-update
description: Bumps the version of an existing skill and records the changelog entry in catalog.json. Never touches the Claude Code cache. Also invoked explicitly as /p4cc-plugin:skill-update with the plugin and skill name.
version: 54
argument-hint: "<plugin> <skill> [--change \"<text>\"] [--dry-run] [--json] [--repo PATH] [--home DIR] [--allow-dirty]"
allowed-tools: [Bash, AskUserQuestion]
---

# Skill Updater

Bumps the skill version (Z+1) and records the change in `specs/catalog.json`. It does not touch the Claude Code cache.

---

## Z versioning rules

- `new_Z = current_Z + 1`
- Skill `version` → `new_Z`
- Plugin `Z` → `new_Z`
- Z is monotonic — never resets

---

## Engine

All the logic lives in one script shared by the p4cc-plugin skills, so a dry-run and a real run execute **the same code** (a single function decides whether anything is written):

```bash
# <Base directory for this skill> is shown when the skill is loaded; the engine is two levels up
ENGINE="<Base directory for this skill>/../../resources/scripts/p4cc_ops.py"
[ -f "$ENGINE" ] || ENGINE="$(ls -d ~/.claude/plugins/cache/*/p4cc-plugin/*/ 2>/dev/null | sort -V | tail -1)resources/scripts/p4cc_ops.py"
python3 "$ENGINE" skill-update <plugin> <skill> --change "<one line>" [options]
```

The engine resolves the marketplace itself, in this order: `--repo PATH` → `P4CC_REPO` → git root of the current directory → walk up to `.claude-plugin/marketplace.json` → a bounded last-resort search (never an unbounded `find ~`; several hits → exit 3 listing the candidates, never "the first one"). `--home DIR` (or `P4CC_HOME`) replaces `~` for `~/.p4cc/`.

**Write boundaries.** Only inside the repo, the single global catalog file of *this* marketplace under `~/.p4cc/` (`catalog.json` for plugin4cc, `catalog-<marketplace>.json` otherwise; another marketplace's file is never touched) and `<repo>/.p4cc/bak/`. **Never the Claude Code cache** (managed by `/plugin`). Nothing is ever installed.

---

## Step 1 — Collect the arguments

`<plugin>` and `<skill>` come from the invocation. If `--change` is missing and the invocation is interactive, ask with **AskUserQuestion**: `"Describe el cambio realizado en el skill <skill> (una línea)"` (header `Changelog`, free text). With `--yes` or `--json` never ask: a missing `--change` is exit 2.

---

## Step 2 — Run the engine

```bash
python3 "$ENGINE" skill-update <plugin> <skill> --change "<description>" [--dry-run] [--json] [--repo PATH] [--home DIR] [--allow-dirty]
```

In one pass it: sets `version:` in the skill's `SKILL.md` (**inserting the line when the frontmatter has none**), updates the skill and plugin entries in `specs/catalog.json` (version + changelog), sets `plugin.json`, and refreshes the global catalog copy.

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

Show the engine output as is. With `--dry-run` the result is the plan (`DRY|modify|…` lines and `RESUMEN|DRY|…`); nothing changed.

Next steps:
1. `git add` + commit + push
2. In Claude Code: `/plugin` → update the marketplace and `<plugin>` (the cache is managed by Claude Code, never by this skill), then `/reload-plugins`
