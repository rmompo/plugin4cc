---
name: skill-doctor
description: Audits plugin skills for version mismatches, frontmatter issues, allowed-tools gaps, catalog inconsistencies, and structural defects. Emits a prioritized findings report and offers to fix auto-correctable defects. Also invoked explicitly as /p4cc-plugin:skill-doctor.
version: 60
argument-hint: "[--plugin <name>]... [--skill <name>]... [--fix auto|N,M,...] [--report-only] [--yes] [--dry-run] [--json] [--repo PATH] [--home DIR] [--allow-dirty]"
allowed-tools: [Bash, AskUserQuestion]
---

# Skill Doctor

Audits plugin skills for version mismatches, frontmatter issues, `allowed-tools` gaps, catalog inconsistencies and structural defects. **By default it only audits** (`--report-only`): it asks nothing and writes nothing. Corrections are explicit (`--fix`) and always leave a backup first.

---

## Engine

All the logic lives in one script shared by the p4cc-plugin skills, so a dry-run and a real run execute **the same code** (a single function decides whether anything is written):

```bash
# <Base directory for this skill> is shown when the skill is loaded; the engine is two levels up
ENGINE="<Base directory for this skill>/../../resources/scripts/p4cc_ops.py"
[ -f "$ENGINE" ] || ENGINE="$(ls -d ~/.claude/plugins/cache/*/p4cc-plugin/*/ 2>/dev/null | sort -V | tail -1)resources/scripts/p4cc_ops.py"
python3 "$ENGINE" doctor [options]
```

The engine resolves the marketplace itself, in this order: `--repo PATH` → `P4CC_REPO` → git root of the current directory → walk up to `.claude-plugin/marketplace.json` → a bounded last-resort search (never an unbounded `find ~`; several hits → exit 3 listing the candidates, never "the first one"). `--home DIR` (or `P4CC_HOME`) replaces `~` for `~/.p4cc/`.

**Write boundaries.** Only inside the repo, the single global catalog file of *this* marketplace under `~/.p4cc/` (`catalog.json` for plugin4cc, `catalog-<marketplace>.json` otherwise; another marketplace's file is never touched) and `<repo>/.p4cc/bak/`. **Never the Claude Code cache** (managed by `/plugin`). Nothing is ever installed.

---

## Usage

```bash
python3 "$ENGINE" doctor                                   # audit everything (read-only)
python3 "$ENGINE" doctor --plugin p4cc-core --skill check  # audit one skill, no questions
python3 "$ENGINE" doctor --fix auto                        # apply only the [auto] defects (backup first)
python3 "$ENGINE" doctor --fix 1,4 --dry-run               # show what fixing findings #1 and #4 would do
python3 "$ENGINE" doctor --json                            # {plugin, skill, findings[], summary}
```

| Option | Meaning |
|--------|---------|
| `--plugin <name>` / `--skill <name>` | Restrict the scope; both can be repeated. Unknown names → exit 2 |
| `--report-only` | Audit only (default; mutually exclusive with `--fix`) |
| `--fix auto` | Apply every finding marked `[auto]`; `[manual]` ones are reported as `WARN\|fix-skipped` |
| `--fix N,M,…` | Apply the findings with those numbers (`#N` in the report) |
| `--yes` | Skip any confirmation that would remain |
| `--dry-run` | With `--fix`: show the plan (`DRY\|…`), write nothing |
| `--allow-dirty` | Skip the uncommitted-changes check before fixing |
| `--repo PATH` / `--home DIR` / `--json` | As in the other p4cc-plugin skills |

### Output and exit codes

One line per item, `STATE|ID|detail` (`STATE` ∈ `OK`, `INFO`, `WARN`, `FAIL`, `DRY`), then a final `RESUMEN|…` line. Exit codes: **0** no failures · **1** failures found · **2** bad usage · **3** precondition not met (no repo, no catalog, ambiguous repo, uncommitted changes).

In the default format each finding is `STATE|ID|plugin:skill: #N detail [auto|manual]`, then `RESUMEN|<n> FAIL|<m> WARN`. `FAIL` = CRITICAL or MAJOR, `WARN` = MINOR. The IDs below are stable across versions.

### Checks

| ID | Severity | Fix | What |
|----|----------|-----|------|
| `C1` | CRITICAL | auto | `SKILL.md` `version` differs from the catalog — or there is no `version:` line (it is inserted) |
| `C2` | CRITICAL | auto | `plugin.json` version differs from the catalog |
| `C3` | MINOR | manual | Installed version differs from `plugin.json` (advisory, read-only: never writes the Claude Code cache) |
| `C4` | CRITICAL | manual | Missing frontmatter field (`name`, `description`, and `allowed-tools` when the marketplace uses it) |
| `C5` | MAJOR | manual | The body uses `AskUserQuestion`, a fenced shell block or one of the file-editing tools but `allowed-tools` does not list it |
| `C6` | MAJOR | manual | The plugin has dependencies but no `install` skill |
| `C7` | MINOR | auto | Description lacks the `Also invoked explicitly as /<plugin>:<skill>` suffix (only enforced when most skills of the marketplace already have it) |
| `C8` | MINOR | auto | No changelog entry for the skill's current version |
| `C9` | MINOR | manual | A skill-level catalog dependency is never mentioned in the body |
| `C10` | MAJOR | manual | Plugin files changed versus `origin/main` but `plugin.json` still has the same version |

`allowed-tools` (C4) and the description suffix (C7) are plugin4cc conventions: they are only enforced when at least half of the marketplace's skills already follow them.

---

## Interactive flow (only when invoked with no arguments at all)

1. Ask the scope with **AskUserQuestion**: all plugins / a plugin / a plugin and a skill (options from the catalog), then run `doctor` with the matching `--plugin` / `--skill`.
2. Show the report. If there are findings, ask what to fix: **Fix all auto-fixable** (`--fix auto`) / **Fix specific findings** (numbers) / **Nothing — report only**.
3. Run `doctor --fix …` accordingly and show the result, including where the backup went.

With any argument the skill never asks anything.

---

## Step 1b — Missing catalog: bootstrap

When the engine answers exit 3 because `specs/catalog.json` does not exist, nothing was written and no audit is possible. Offer to build the catalog from the plugins already in the repo:

1. Ask the documentation language of the marketplace with **AskUserQuestion**: English (`en`), Spanish (`es`) or other (stored as `docs_language`; used by `doc-doctor`).
2. Dry-run first and show the plan:

```bash
python3 "$ENGINE" bootstrap --docs-language <en|es|...> --dry-run
```

3. Ask for confirmation (`Apply` / `Cancel`), then run the same command without `--dry-run`. It writes the missing `specs/<plugin>.md`, then `specs/catalog.json` last (a crash never leaves an orphan catalog), then the global copy (never another marketplace's).
4. Re-run the audit.

The bootstrap registers every `plugins/<dir>/.claude-plugin/plugin.json` keeping its `X.Y.Z`; skills get `version` = the plugin's Z; `status` is `beta` and `category` comes from `marketplace.json` (or `other`) — placeholders to review. `SKILL.md` files are not modified: `doctor --fix auto` adds any missing `version:`.

---

## Backups

Every fix first copies the files it modifies to `<repo>/.p4cc/bak/<timestamp>/files/` (directories `0700`, files `0600`) and prints the location. Add `.p4cc/` to `.gitignore` or `.git/info/exclude` (the engine warns when it is not). Nothing is restored automatically; on failure the engine prints the `cp -a` command that restores the backup.

Next steps after fixing: `git add` + commit + push, then In Claude Code: `/plugin` → update the marketplace and `<plugin>` (the cache is managed by Claude Code, never by this skill), then `/reload-plugins`.
