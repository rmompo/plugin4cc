---
name: doc-doctor
description: Audits documentation completeness and language for each plugin: verifies spec files, plugins/README.md listing, README.md skills tables, and English-only content against catalog ground truth. Reports findings and offers to generate or update missing content automatically. Also invoked explicitly as /p4cc-plugin:doc-doctor.
version: 61
argument-hint: "[--plugin <name>]... [--fix auto|N,M,...] [--report-only] [--yes] [--dry-run] [--json] [--repo PATH] [--home DIR] [--allow-dirty]"
allowed-tools: [Bash, AskUserQuestion]
---

# Doc Doctor

Audits plugin documentation: `specs/<plugin>.md`, `plugins/README.md`, `plugins/<plugin>/README.md` and language compliance, against `specs/catalog.json`. All content must be written in the marketplace's documentation language: `docs_language` in `specs/catalog.json` (default `en`). **By default it only audits** (`--report-only`): it asks nothing and writes nothing.

---

## Engine

All the logic lives in one script shared by the p4cc-plugin skills, so a dry-run and a real run execute **the same code** (a single function decides whether anything is written):

```bash
# <Base directory for this skill> is shown when the skill is loaded; the engine is two levels up
ENGINE="<Base directory for this skill>/../../resources/scripts/p4cc_ops.py"
[ -f "$ENGINE" ] || ENGINE="$(ls -d ~/.claude/plugins/cache/*/p4cc-plugin/*/ 2>/dev/null | sort -V | tail -1)resources/scripts/p4cc_ops.py"
python3 "$ENGINE" doc-audit [options]
```

The engine resolves the marketplace itself, in this order: `--repo PATH` → `P4CC_REPO` → git root of the current directory → walk up to `.claude-plugin/marketplace.json` → a bounded last-resort search (never an unbounded `find ~`; several hits → exit 3 listing the candidates, never "the first one"). `--home DIR` (or `P4CC_HOME`) replaces `~` for `~/.p4cc/`.

**Write boundaries.** Only inside the repo, the single global catalog file of *this* marketplace under `~/.p4cc/` (`catalog.json` for plugin4cc, `catalog-<marketplace>.json` otherwise; another marketplace's file is never touched) and `<repo>/.p4cc/bak/`. **Never the Claude Code cache** (managed by `/plugin`). Nothing is ever installed.

---

## Usage

```bash
python3 "$ENGINE" doc-audit                      # audit everything (read-only)
python3 "$ENGINE" doc-audit --plugin p4cc-core   # one plugin, no questions
python3 "$ENGINE" doc-audit --fix auto           # apply the [auto] defects (backup first)
python3 "$ENGINE" doc-audit --fix 2,3 --dry-run  # plan only
python3 "$ENGINE" doc-audit --json
```

| Option | Meaning |
|--------|---------|
| `--plugin <name>` | Restrict the scope (repeatable). Unknown names → exit 2 |
| `--report-only` | Audit only (default; mutually exclusive with `--fix`) |
| `--fix auto` / `--fix N,M,…` | Apply every `[auto]` finding / the findings with those numbers; `[manual]` ones are reported as `WARN\|fix-skipped` |
| `--yes`, `--dry-run`, `--allow-dirty`, `--repo PATH`, `--home DIR`, `--json` | As in the other p4cc-plugin skills |

### Output and exit codes

One line per item, `STATE|ID|detail` (`STATE` ∈ `OK`, `INFO`, `WARN`, `FAIL`, `DRY`), then a final `RESUMEN|…` line. Exit codes: **0** no failures · **1** failures found · **2** bad usage · **3** precondition not met (no repo, no catalog, ambiguous repo, uncommitted changes).

`FAIL` = CRITICAL or MAJOR, `WARN` = MINOR. The IDs are stable across versions.

### Checks

| ID | Severity | Fix | What |
|----|----------|-----|------|
| `D1` | CRITICAL | auto | `specs/<plugin>.md` does not exist (generated from the catalog) |
| `D2` | MAJOR | auto | The spec lacks the Overview or Changelog section (localized headings accepted) |
| `D3` | MAJOR | auto | The spec never mentions a catalog skill (a `## Skill:` section is added) |
| `D4` | MINOR | auto | The spec's version header differs from the catalog |
| `D5` | MAJOR | auto | `plugins/README.md` has no row for the plugin |
| `D6` | MINOR | auto | The row's *Skills* column (found **by header name**) lacks catalog skills; tables without that column are left alone |
| `D7` | MAJOR | auto | The plugin `README.md` is missing, or has no entry for a skill |
| `D8` | MAJOR | manual | Headings not written in `docs_language` (code blocks, identifiers and technical terms are exempt; Spanish docs declared with `"docs_language": "es"` are correct) |
| `D9` | MAJOR | auto | `type: "plugin"` dependencies are not documented in the README |

Generated documents use the headings of `docs_language` (`en` and `es` are localized; other languages fall back to English labels).

---

## Interactive flow (only when invoked with no arguments at all)

Ask the scope (all plugins / a plugin) with **AskUserQuestion**, run `doc-audit`, show the report and, if there are findings, ask whether to fix all `[auto]`, specific numbers, or nothing; then run `doc-audit --fix …` and show the result (it includes the backup location). With any argument the skill never asks anything. A missing catalog gives exit 3: use `/p4cc-plugin:skill-doctor` (its Step 1b bootstraps it).

## Backups

Every fix first copies the files it modifies to `<repo>/.p4cc/bak/<timestamp>/files/` (directories `0700`, files `0600`). Add `.p4cc/` to `.gitignore` or `.git/info/exclude`. Nothing is restored automatically; on failure the engine prints the `cp -a` command that restores the backup.

Next steps: review the generated content, `git add` + commit + push.
