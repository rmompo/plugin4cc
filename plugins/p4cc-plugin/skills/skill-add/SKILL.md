---
name: skill-add
description: Adds a new skill to an existing plugin. Bumps Z versioning in catalog.json and plugin.json and creates the SKILL.md. Never touches the Claude Code cache. Also invoked explicitly as /p4cc-plugin:skill-add with the plugin and skill name.
version: 55
argument-hint: "<plugin> <skill> [--description \"<text>\"] [--argument-hint \"<hint>\"] [--allowed-tools \"A, B\"] [--dry-run] [--json] [--repo PATH] [--home DIR]"
allowed-tools: [Bash, AskUserQuestion]
---

# Skill Adder

Adds a new skill to an existing plugin, bumps Z versioning and syncs the catalogs. It does not touch the Claude Code cache.

---

## Z versioning rules

- `new_Z = current_Z + 1`
- New skill gets `version: new_Z`
- Plugin `Z` → `new_Z`
- Z is monotonic — never resets

---

## Engine

All the logic lives in one script shared by the p4cc-plugin skills, so a dry-run and a real run execute **the same code** (a single function decides whether anything is written):

```bash
# <Base directory for this skill> is shown when the skill is loaded; the engine is two levels up
ENGINE="<Base directory for this skill>/../../resources/scripts/p4cc_ops.py"
[ -f "$ENGINE" ] || ENGINE="$(ls -d ~/.claude/plugins/cache/*/p4cc-plugin/*/ 2>/dev/null | sort -V | tail -1)resources/scripts/p4cc_ops.py"
python3 "$ENGINE" skill-add <plugin> <skill> --description "<one line>" [options]
```

The engine resolves the marketplace itself, in this order: `--repo PATH` → `P4CC_REPO` → git root of the current directory → walk up to `.claude-plugin/marketplace.json` → a bounded last-resort search (never an unbounded `find ~`; several hits → exit 3 listing the candidates, never "the first one"). `--home DIR` (or `P4CC_HOME`) replaces `~` for `~/.p4cc/`.

**Write boundaries.** Only inside the repo, the single global catalog file of *this* marketplace under `~/.p4cc/` (`catalog.json` for plugin4cc, `catalog-<marketplace>.json` otherwise; another marketplace's file is never touched) and `<repo>/.p4cc/bak/`. **Never the Claude Code cache** (managed by `/plugin`). Nothing is ever installed.

---

## Step 1 — Collect the arguments

If not given as options and the invocation is interactive, ask with **AskUserQuestion**: (1) skill description (one line, also used in the `SKILL.md` frontmatter), (2) `argument-hint` (optional), (3) `allowed-tools` (default `Bash, Read, Edit, Write`). With `--yes` or `--json` never ask: a missing `--description` is exit 2.

---

## Step 2 — Run the engine

```bash
python3 "$ENGINE" skill-add <plugin> <skill> --description "<text>" [--argument-hint "<hint>"] [--allowed-tools "Bash, Read"] [--dry-run] [--json] [--repo PATH] [--home DIR]
```

It creates `plugins/<plugin>/skills/<skill>/SKILL.md` (with `version: <new_Z>`), appends the skill to the catalog (changelog `Initial release`), bumps the plugin version and changelog, sets `plugin.json`, refreshes the global catalog copy, adds the row to the plugin's `README.md` (creating it if missing) and appends the skill to the *Skills* column of `plugins/README.md` (located by header name).

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

Show the engine output as is. Next steps: fill in the skill logic in `skills/<skill>/SKILL.md`, then `git add` + commit + push, then In Claude Code: `/plugin` → update the marketplace and `<plugin>` (the cache is managed by Claude Code, never by this skill), then `/reload-plugins`.
