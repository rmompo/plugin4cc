---
name: skill-remove
description: Removes a skill from a plugin. Deletes the SKILL.md, and updates catalog.json (Z does not decrease). Never touches the Claude Code cache. Destructive — requires explicit confirmation. Also invoked explicitly as /p4cc-plugin:skill-remove with the plugin and skill name.
version: 62
argument-hint: "<plugin> <skill> [--soft|--restore] [--yes] [--dry-run] [--json] [--repo PATH] [--home DIR] [--allow-dirty]"
allowed-tools: [Bash, AskUserQuestion]
---

# Skill Remover

Removes a skill from a plugin. **Destructive — the skill directory is deleted** (a backup is kept first).

Z does **not** decrease on removal — the counter is monotonic.

---

## Engine

All the logic lives in one script shared by the p4cc-plugin skills, so a dry-run and a real run execute **the same code** (a single function decides whether anything is written):

```bash
# <Base directory for this skill> is shown when the skill is loaded; the engine is two levels up
ENGINE="<Base directory for this skill>/../../resources/scripts/p4cc_ops.py"
[ -f "$ENGINE" ] || ENGINE="$(ls -d ~/.claude/plugins/cache/*/p4cc-plugin/*/ 2>/dev/null | sort -V | tail -1)resources/scripts/p4cc_ops.py"
python3 "$ENGINE" skill-remove <plugin> <skill> --yes [options]
```

The engine resolves the marketplace itself, in this order: `--repo PATH` → `P4CC_REPO` → git root of the current directory → walk up to `.claude-plugin/marketplace.json` → a bounded last-resort search (never an unbounded `find ~`; several hits → exit 3 listing the candidates, never "the first one"). `--home DIR` (or `P4CC_HOME`) replaces `~` for `~/.p4cc/`.

**Write boundaries.** Only inside the repo, the single global catalog file of *this* marketplace under `~/.p4cc/` (`catalog.json` for plugin4cc, `catalog-<marketplace>.json` otherwise; another marketplace's file is never touched) and `<repo>/.p4cc/bak/`. **Never the Claude Code cache** (managed by `/plugin`). Nothing is ever installed.

---

## Step 1 — Confirm

Unless `--yes` or `--dry-run` was given, confirm with **AskUserQuestion**: `"¿Confirmas la eliminación del skill <skill> de <plugin>? Esta acción no se puede deshacer."` (header `Confirmar`; options `Sí, eliminar` / `Cancelar`). On cancel, stop.

---

## Step 2 — Run the engine

```bash
python3 "$ENGINE" skill-remove <plugin> <skill> --yes [--dry-run] [--json] [--repo PATH] [--home DIR] [--allow-dirty]
```

Before deleting anything it copies every file it will modify or delete to `<repo>/.p4cc/bak/<timestamp>/files/` (directories `0700`, files `0600`) and prints where. It then deletes the skill directory, removes the catalog entry (plugin changelog line `Remove <skill> skill`, version unchanged), refreshes the global catalog copy, removes the row from the plugin's `README.md` and the name from the *Skills* column of `plugins/README.md`.

The backup folder must be ignored by git: add `.p4cc/` to `.gitignore` or `.git/info/exclude` (the engine warns when it is not). Nothing is restored automatically; if the operation fails the engine prints the exact `cp -a` command that restores the backup.

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

### Logical removal (`--soft` / `--restore`)

`--soft` marks the skill as retired in the catalog (`retired: {at: <date>}` plus a plugin changelog line) **without deleting any file**, so nothing is lost and no confirmation is needed; `--restore` undoes it. Z is not touched. They are mutually exclusive, and a backup of the catalog is still kept first.

```bash
python3 "$ENGINE" skill-remove <plugin> <skill> --soft      # retire (reversible)
python3 "$ENGINE" skill-remove <plugin> <skill> --restore   # bring it back
```

---

## Step 3 — Report

Show the engine output as is (it includes the backup location). Next steps: `git add` + commit + push, then In Claude Code: `/plugin` → update the marketplace and `<plugin>` (the cache is managed by Claude Code, never by this skill), then `/reload-plugins`.
