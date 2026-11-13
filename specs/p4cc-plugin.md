# Plugin Spec: p4cc-plugin

> **Status:** `beta` | **Version:** `1.1.63`

---

## Overview

`p4cc-plugin` provides full lifecycle management for the plugin4cc marketplace. It handles creation, modification and removal of plugins and skills, keeping the catalogs in sync automatically after every operation. It works with any marketplace, not only plugin4cc, and it never writes the Claude Code cache (that is managed by `/plugin`).

`specs/catalog.json` is the primary source of truth — all operations write there first and derive all other files from it.

---

## Skills

| Skill | Invocation | Description |
|-------|-----------|-------------|
| `create` | `/p4cc-plugin:create <plugin> [skills...]` | Scaffold a new plugin with all required files |
| `update` | `/p4cc-plugin:update <plugin>` | Update plugin metadata (description, status, version bump) |
| `remove` | `/p4cc-plugin:remove <plugin> [--soft\|--restore]` | Remove a plugin (backup first) or retire it logically |
| `skill-add` | `/p4cc-plugin:skill-add <plugin> <skill>` | Add a new skill to an existing plugin |
| `skill-update` | `/p4cc-plugin:skill-update <plugin> <skill>` | Bump skill version and update changelogs |
| `skill-remove` | `/p4cc-plugin:skill-remove <plugin> <skill> [--soft\|--restore]` | Remove a skill (backup first) or retire it logically |
| `skill-doctor` | `/p4cc-plugin:skill-doctor [--plugin P] [--skill S] [--fix auto\|N,M]` | Audit skills (C1–C10); report-only by default, `--fix` with backup |
| `doc-doctor` | `/p4cc-plugin:doc-doctor [--plugin P] [--fix auto\|N,M]` | Audit documentation (D1–D9); report-only by default, `--fix` with backup |

---

## Files updated per operation

| File | create | update | remove | skill-add | skill-update | skill-remove |
|------|--------|--------|--------|-----------|--------------|--------------|
| `specs/catalog.json` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `plugins/<plugin>/.claude-plugin/plugin.json` | ✅ | ✅* | ❌ deleted | ✅ | ✅ | — |
| `.claude-plugin/marketplace.json` | ✅ | ✅* | ✅ | — | — | — |
| `plugins/README.md` | ✅ | ✅* | ✅ | — | — | — |
| `specs/<plugin>.md` | ✅ | — | ❌ deleted | — | — | — |
| `plugins/<plugin>/skills/<skill>/SKILL.md` | ✅ | — | — | ✅ created | ✅ bumped | ❌ deleted |
| Backup in `<repo>/.p4cc/bak/` | — | ✅ | ✅ | — | — | ✅ |

*only if version or description changed

---

## Version management — Z system

Plugin version is `X.Y.Z`:
- `X` — major: breaking changes
- `Y` — minor: new features or significant behaviour changes
- `Z` — monotonic skill counter: **never resets**, even when X or Y change

`Z` always equals the highest skill version ever assigned in the plugin.

| Event | Z |
|-------|---|
| `skill-add` | Z + 1 (new skill gets this value) |
| `skill-update` | Z + 1 (updated skill gets this value) |
| `skill-remove` | unchanged (monotonic) |
| `update` metadata | unchanged |

---

## Engine

All the logic lives in `resources/scripts/p4cc_ops.py` (`env`, `skill-update`, `skill-add`, `skill-remove`, `update`, `remove`, `create`, `doctor`, `doc-audit`, `bootstrap`). A single function (`Plan.run`) decides whether anything is written, so `--dry-run` and the real run execute the same code. The SKILL.md files are thin wrappers that collect missing arguments with `AskUserQuestion` (only when invoked without arguments) and call the engine.

### Options shared by every command

| Option | Meaning |
|--------|---------|
| `--repo PATH` | Marketplace repo (same as `P4CC_REPO`; the flag wins) |
| `--home DIR` | Replaces `~` for `~/.p4cc/` (same as `P4CC_HOME`) |
| `--dry-run` | Resolve and validate everything, write nothing, print the exact plan (`DRY|create|modify|delete|<path>`), end with `RESUMEN|DRY|…` |
| `--json` | Machine-readable output |
| `--allow-dirty` | Skip the "uncommitted changes in the files to modify" check (applies to `remove`, `update`, `skill-remove` and `--fix`; untracked files are ignored) |
| `--yes` | Skip confirmations |

Repo resolution: `--repo` → `P4CC_REPO` → git root of the current directory → walk up to `.claude-plugin/marketplace.json` → bounded last-resort search (several hits → exit 3 with the candidates). Marketplace name comes from `marketplace.json`; the global catalog is `~/.p4cc/catalog.json` for plugin4cc and `~/.p4cc/catalog-<marketplace>.json` otherwise (another marketplace's file is never touched).

**Write boundaries:** only inside the repo, the single global catalog file of the current marketplace and `<repo>/.p4cc/bak/`. Never the Claude Code cache. Nothing is ever installed.

### Output, stable IDs and exit codes

Default: one line per item, `STATE|ID|detail`, then `RESUMEN|…`. `STATE` ∈ `OK`, `INFO`, `WARN`, `FAIL`, `DRY`. Exit codes: `0` no failures · `1` failures found · `2` bad usage · `3` precondition not met (no repo, no catalog, ambiguous repo, uncommitted changes).

`doctor` / `doc-audit` print `STATE|ID|plugin:skill: #N detail [auto|manual]`, then `RESUMEN|<n> FAIL|<m> WARN` (`FAIL` = CRITICAL or MAJOR, `WARN` = MINOR); `--json` gives `{plugin, skill, findings[], summary}`. They only audit by default (`--report-only`); `--fix auto` applies the `[auto]` findings and `--fix N,M` those numbers, always after a backup. `--plugin` and `--skill` (repeatable) restrict the scope without questions.

| Doctor | IDs (stable across versions) |
|--------|------------------------------|
| `skill-doctor` | `C1` version (also: missing `version:`), `C2` plugin.json, `C3` installed version (advisory), `C4` frontmatter, `C5` allowed-tools, `C6` install skill, `C7` description suffix, `C8` changelog, `C9` dependencies documented, `C10` changed without version bump (vs `origin/main`) |
| `doc-doctor` | `D1` spec missing, `D2` spec sections, `D3` skill documented, `D4` spec version, `D5` plugins/README row, `D6` Skills column (found by header name), `D7` plugin README, `D8` documentation language (`docs_language`), `D9` plugin dependencies |

`bootstrap` builds a missing `specs/catalog.json` from the existing plugins (dry-run first; skills get `version` = the plugin's Z; `SKILL.md` files are not modified).

---

## Destructive operations

`remove` and `skill-remove` require explicit confirmation via `AskUserQuestion` before proceeding. Before deleting or overwriting anything, `remove`, `update`, `skill-remove` and the `--fix` of both doctors copy the affected files to `<repo>/.p4cc/bak/<timestamp>/files/` (directories `0700`, files `0600`) and print where; add `.p4cc/` to `.gitignore` or `.git/info/exclude` (they warn when it is not). Nothing is restored automatically: on failure the engine prints the `cp -a` command that restores the backup.

`--soft` retires a plugin or skill in the catalog **without deleting any file** (plugin: `status: deprecated` plus `retired: {from_status, at}`; skill: `retired: {at}`), needs no confirmation and is undone with `--restore`.

---

## Non-Goals

- Does not push to git (`git add + commit + push` is a manual next step)
- Does not touch the Claude Code cache: after pushing, update through `/plugin` (and `/reload-plugins`)
- Does not fill in skill logic — only scaffolds the structure

---

## Changelog

| Version | Changes |
|---------|---------|
| 1.1.63 | remove: add --soft/--restore: logical removal that retires the plugin (status deprecated) without deleting files |
| 1.1.62 | skill-remove: add --soft/--restore: logical removal that marks the skill as retired in the catalog without deleting files |
| 1.1.61 | doc-doctor: report-only by default; --fix auto\|N,M, --plugin, STATE\|ID\|detail output, --json, exit codes, backup, header-driven README columns |
| 1.1.60 | skill-doctor: report-only by default; --fix auto\|N,M, --plugin/--skill, STATE\|ID\|detail output, --json, exit codes, backup, C10, bootstrap |
| 1.1.59 | create: add --dry-run, --json, non-interactive options, --repo and --home |
| 1.1.58 | remove: add --dry-run, --json, --yes, backup before deleting, --repo and --home |
| 1.1.57 | update: add --dry-run, --json, backup before modifying, --repo and --home |
| 1.1.56 | skill-remove: add --dry-run, --json, --yes, backup before deleting, --repo and --home |
| 1.1.55 | skill-add: add --dry-run, --json, --repo and --home; runs through the shared ops engine |
| 1.1.54 | skill-update: add --dry-run, --json, --repo and --home; runs through the shared ops engine |
| 1.1.53 | update: stop writing to the Claude Code cache; the cache is managed by /plugin |
| 1.1.52 | skill-update: stop writing to the Claude Code cache; the cache is managed by /plugin |
| 1.1.51 | skill-remove: stop writing to the Claude Code cache; the cache is managed by /plugin |
| 1.1.50 | skill-doctor: stop writing to the Claude Code cache; the cache is managed by /plugin |
| 1.1.49 | skill-add: stop writing to the Claude Code cache; the cache is managed by /plugin |
| 1.1.48 | remove: stop writing to the Claude Code cache; the cache is managed by /plugin |
| 1.1.47 | doc-doctor: stop writing to the Claude Code cache; the cache is managed by /plugin |
| 1.1.46 | create: stop writing to the Claude Code cache; the cache is managed by /plugin |
| 1.1.45 | create: example tool dependency uses python3 >=3.10.0 |
| 1.1.44 | update: work with any marketplace: resolve repo, cache and global catalog dynamically |
| 1.1.43 | skill-update: work with any marketplace; insert a missing version in the SKILL.md frontmatter |
| 1.1.42 | skill-remove: work with any marketplace: resolve repo, cache and global catalog dynamically |
| 1.1.41 | skill-doctor: work with any marketplace; offer a catalog bootstrap when it is missing; C1 handles a missing version |
| 1.1.40 | skill-add: work with any marketplace: resolve repo, cache and global catalog dynamically |
| 1.1.39 | remove: work with any marketplace: resolve repo, cache and global catalog dynamically |
| 1.1.38 | doc-doctor: work with any marketplace; D8 honors docs_language from the catalog |
| 1.1.37 | create: work with any marketplace: resolve repo, marketplace name, cache and global catalog dynamically; homepage and author from marketplace data |
| 1.1.29 | create: enforce two-group alphabetical README.md convention in Step 7b |
| 1.1.30 | update: enforce two-group alphabetical README.md convention in Step 4 |
| 1.1.28 | sanitize: Extend scan scope to all sensitive-capable file types across the repo (docs, configs, scripts, structured data), not just plugin/skill files |
| 1.1.27 | Add sanitize skill |
| 1.1.26 | create: unified dep scaffold; skill-doctor: C6 plugin dep check; doc-doctor: D9 plugin dep docs |
| 1.1.23 | schema migration: requires[] → dependencies[{type,name,version}] in skill-doctor, create, doc-doctor |
| 1.1.20 | skill-remove: remove skill row from README.md |
| 1.1.19 | skill-add: update README.md on skill creation |
| 1.1.18 | doc-doctor: D7→[auto], add D8 language check |
| 1.1.17 | skill-doctor: tighten C5 detection to avoid prose false positives |
| 1.1.16 | skill-doctor: expand C6 to cover skill-level tool dependencies |
| 1.1.14 | Rename skill-check → skill-doctor |
| 1.1.15 | Rename doc-update → doc-doctor |
| 1.1.13 | Add doc-update skill |
| 1.1.12 | Add skill-check — global plugin/skill auditor with auto-fix support |
| 1.1.11 | create: add requires field and setup skill auto-scaffold |
| 1.1.10 | create: add scopes collection and setup skill convention |
| 1.1.36 | `skill-doctor`: C6 now requires an install skill instead of setup |
| 1.1.35 | `create`: align setup-skill convention with the rename to install (install creates folders, check verifies) |
| 1.1.9 | Split manage into 6 independent skills: create, update, remove, skill-add, skill-update, skill-remove |
| 1.0.3 | manage: full lifecycle rewrite — catalog-first sync, cache sync |
| 1.0.2 | manage: update plugin.json template with skills/changelog structure |
| 1.0.1 | Rename create→manage; add lifecycle operations and Z versioning |
| 1.0.0 | Initial release with create skill |
