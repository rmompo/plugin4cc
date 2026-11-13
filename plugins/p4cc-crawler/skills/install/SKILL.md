---
name: install
description: Installs the p4cc-crawler infrastructure — creates the required folders and files — then runs the check. Tools are never installed automatically; missing ones are reported with install instructions. Also invoked explicitly as /p4cc-crawler:install.
version: 5
argument-hint: "[--dry-run] [--json] [--home DIR]"
allowed-tools: [Bash]
---

# p4cc-crawler Install

Installs the marketplace `catalog.json` copy under `~/.p4cc/`. Then verifies the result with `/p4cc-crawler:check`. Idempotent — safe to re-run at any time. External tools are **never** installed automatically: `/p4cc-crawler:check` reports each missing one with its install command.

---

## Engine

The logic lives in a script shipped with the plugin, so the result is identical however the skill is invoked (and usable from a shell or CI):

```bash
# <Base directory for this skill> is shown when the skill is loaded; the engine is two levels up
ENGINE="<Base directory for this skill>/../../resources/scripts/check_engine.py"
python3 "$ENGINE" install [--dry-run] [--json] [--home DIR]
```

## Options

| Option | Meaning |
|--------|---------|
| `--dry-run` | Resolve everything, **write nothing** and print the exact plan (`DRY\|create\|modify\|<path>`), ending with `RESUMEN\|DRY\|…` instead of `RESUMEN\|OK\|…` |
| `--json` | Machine-readable output |
| `--home DIR` | Home directory used for `~/.p4cc/` (same as `P4CC_HOME`) |

Write boundaries: only under `~/.p4cc/` — and never another marketplace's `catalog.json` (if `~/.p4cc/catalog.json` belongs to another marketplace it is left untouched and reported). Never the Claude Code cache.

---

## Steps

1. Run `python3 "$ENGINE" install [--dry-run] [--json] [--home DIR]` and show the output.
2. After a real install (no `--dry-run`), run `python3 "$ENGINE" check --table` and show it. If it lists missing tools, show their install commands and ask the person to re-run `/p4cc-crawler:check` once installed.

### Output and exit codes

Default (script): one line per finding, `STATE|ID|detail` (`STATE` ∈ `OK`, `INFO`, `WARN`, `FAIL`), then `RESUMEN|<n> FAIL|<m> WARN`. IDs are stable across versions (`folder-*`, `catalog-*`, `res-*`, `tool-*`, `pkg-*`, `ocr-lang-*`, `profile-*`). `--json` gives `{plugin, skill, findings[], summary}`. Exit codes: **0** no failures · **1** failures · **2** bad usage · **3** precondition not met. Tools are never installed: every problem comes with the command the person has to run.
