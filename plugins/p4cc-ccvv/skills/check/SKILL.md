---
name: check
description: Read-only verification of the p4cc-ccvv infrastructure — folders, files, external tools and plugin resources. Reports status and tells how to install anything missing. Also invoked explicitly as /p4cc-ccvv:check.
version: 20
argument-hint: "[--json] [--lines] [--home DIR]"
allowed-tools: [Bash]
---

# p4cc-ccvv Check

Read-only verification of everything p4cc-ccvv needs: folders, the global catalog, the files the plugin ships, external tools and optional components. It **never creates, changes or installs anything**; for each problem it prints how to fix it. Safe to re-run at any time.

---

## Engine

The logic lives in a script shipped with the plugin, so the result is identical however the skill is invoked (and usable from a shell or CI):

```bash
# <Base directory for this skill> is shown when the skill is loaded; the engine is two levels up
ENGINE="<Base directory for this skill>/../../resources/scripts/check_engine.py"
python3 "$ENGINE" check [--json | --table] [--home DIR]
```

## What it checks

- **Folders:** `~/.p4cc/`, `~/.p4cc/p4cc-ccvv/` and `~/.p4cc/p4cc-ccvv/profiles/`, and `input/`, `data/`, `output/` inside each existing profile.
- **Global catalog:** present, valid and up to date.
- **Shipped files:** the CV guidelines, templates and JSON schemas.
- **Tools:** `pandoc`, `pdflatex`, `python3` (constraints from the catalog).

Tool versions are read from the plugin's `dependencies` in the catalog (`~/.p4cc/catalog.json`), falling back to the values shipped with the plugin.

---

## How to run it

1. Without options (a person invoking the skill) run `python3 "$ENGINE" check --table` and show the result: a Markdown table plus, for each ❌/⚠️, the install commands for every platform.
2. With `--json` run `python3 "$ENGINE" check --json` and print it as is.
3. With `--lines` run `python3 "$ENGINE" check` (the `STATE|ID|detail` lines) and print it as is.
4. Add `--home DIR` when the user passed it (it replaces `~` for `~/.p4cc/`).

### Output and exit codes

Default (script): one line per finding, `STATE|ID|detail` (`STATE` ∈ `OK`, `INFO`, `WARN`, `FAIL`), then `RESUMEN|<n> FAIL|<m> WARN`. IDs are stable across versions (`folder-*`, `catalog-*`, `res-*`, `tool-*`, `pkg-*`, `ocr-lang-*`, `profile-*`). `--json` gives `{plugin, skill, findings[], summary}`. Exit codes: **0** no failures · **1** failures · **2** bad usage · **3** precondition not met. Tools are never installed: every problem comes with the command the person has to run.

If any `folder-*` / `catalog-*` finding fails, the fix is `/p4cc-ccvv:install`. Any other ❌ is fixed by the command shown next to it (the person runs it; this skill never does).
