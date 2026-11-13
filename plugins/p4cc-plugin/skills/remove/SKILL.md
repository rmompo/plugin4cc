---
name: remove
description: Removes a plugin and all its files from the repo, and every catalog. Never touches the Claude Code cache. Destructive — requires explicit confirmation. Also invoked explicitly as /p4cc-plugin:remove with the plugin name.
version: 58
argument-hint: "<plugin> [--yes] [--dry-run] [--json] [--repo PATH] [--home DIR] [--allow-dirty]"
allowed-tools: [Bash, AskUserQuestion]
---

# Plugin Remover

Removes a plugin completely — all its files and all catalog entries (not the Claude Code cache). **Destructive** — a backup of everything deleted or modified is kept first.

---

## Engine

All the logic lives in one script shared by the p4cc-plugin skills, so a dry-run and a real run execute **the same code** (a single function decides whether anything is written):

```bash
# <Base directory for this skill> is shown when the skill is loaded; the engine is two levels up
ENGINE="<Base directory for this skill>/../../resources/scripts/p4cc_ops.py"
[ -f "$ENGINE" ] || ENGINE="$(ls -d ~/.claude/plugins/cache/*/p4cc-plugin/*/ 2>/dev/null | sort -V | tail -1)resources/scripts/p4cc_ops.py"
python3 "$ENGINE" remove <plugin> --yes [options]
```

The engine resolves the marketplace itself, in this order: `--repo PATH` → `P4CC_REPO` → git root of the current directory → walk up to `.claude-plugin/marketplace.json` → a bounded last-resort search (never an unbounded `find ~`; several hits → exit 3 listing the candidates, never "the first one"). `--home DIR` (or `P4CC_HOME`) replaces `~` for `~/.p4cc/`.

**Write boundaries.** Only inside the repo, the single global catalog file of *this* marketplace under `~/.p4cc/` (`catalog.json` for plugin4cc, `catalog-<marketplace>.json` otherwise; another marketplace's file is never touched) and `<repo>/.p4cc/bak/`. **Never the Claude Code cache** (managed by `/plugin`). Nothing is ever installed.

---

## Step 1 — Confirm

First run `python3 "$ENGINE" remove <plugin> --dry-run` and show the plan (what will be deleted and which entries removed). Unless `--yes` or `--dry-run` was given, confirm with **AskUserQuestion**: `"¿Confirmas la eliminación de <plugin> y todos sus ficheros?"` (options `Sí, eliminar` / `Cancelar`). On cancel, stop.

---

## Step 2 — Run the engine

```bash
python3 "$ENGINE" remove <plugin> --yes [--dry-run] [--json] [--repo PATH] [--home DIR] [--allow-dirty]
```

It deletes `plugins/<plugin>/` and `specs/<plugin>.md`, removes the entry from `specs/catalog.json` (and refreshes the global catalog copy), from `.claude-plugin/marketplace.json` and the row from `plugins/README.md`. Everything touched is first copied to `<repo>/.p4cc/bak/<timestamp>/files/` (directories `0700`, files `0600`); add `.p4cc/` to `.gitignore` or `.git/info/exclude`. Nothing is restored automatically; on failure the engine prints the `cp -a` command that restores the backup.

### Options

| Option | Meaning |
|--------|---------|
| `--repo PATH` | Marketplace repo (same as `P4CC_REPO`; the flag wins when both are given) |
| `--home DIR` | Home directory used for `~/.p4cc/` (same as `P4CC_HOME`; default `$HOME`) |
| `--dry-run` | Resolve and validate everything, **write nothing**, print the exact plan (`DRY\|create\|modify\|delete\|<path>`) and end with `RESUMEN\|DRY\|…` instead of `RESUMEN\|OK\|…` |
| `--json` | Machine-readable output (valid JSON) |
| `--allow-dirty` | Skip the "uncommitted changes in the files to modify" check |
| `--yes` | Skip the confirmation (the skill asks you first when interactive) |


### Output and exit codes

One line per item, `STATE|ID|detail` (`STATE` ∈ `OK`, `INFO`, `WARN`, `FAIL`, `DRY`), then a final `RESUMEN|…` line. Exit codes: **0** no failures · **1** failures found · **2** bad usage · **3** precondition not met (no repo, no catalog, ambiguous repo, uncommitted changes).

---

## Step 3 — Report

Show the engine output as is (it includes the backup location). Next steps: `git add` + commit + push; if the plugin was installed, `/plugin` → uninstall it (the cache is managed by Claude Code, never by this skill).
