---
name: install
description: One-time setup skill for p4cc-statusline. Installs the statusline script and activates it in ~/.claude/settings.json. Invoke once after installing the plugin. Also invoked explicitly as /p4cc-statusline:install.
version: 7
argument-hint: "[--dry-run] [--json] [--yes] [--home DIR]"
allowed-tools: [Bash, AskUserQuestion]
---

# p4cc-statusline Install

Installs the custom statusline for Claude Code. Run once after installing the plugin. Idempotent — safe to run multiple times.

## What it does

1. Copies `statusline-command.sh` from the plugin to `~/.claude/` and makes it executable
2. Adds or updates the `statusLine` block in `~/.claude/settings.json` (a minimal patch: every other key and the file's indentation are preserved)

---

## Engine

The logic lives in a script shipped with the plugin, so a dry-run and a real run execute the same code:

```bash
# <Base directory for this skill> is shown when the skill is loaded; the script is two levels up
INSTALLER="<Base directory for this skill>/../../statusline/install.py"
python3 "$INSTALLER" [--dry-run] [--json] [--yes] [--home DIR]
```

| Option | Meaning |
|--------|---------|
| `--dry-run` | Resolve everything, **write nothing**, print the exact plan (`DRY\|create\|modify\|backup\|<path>`) and end with `RESUMEN\|DRY\|…` instead of `RESUMEN\|OK\|…` |
| `--yes` | Overwrite a *different* existing `statusLine` value |
| `--json` | Machine-readable output |
| `--home DIR` | Replaces `~` (same as `P4CC_HOME`) |

Output: `STATE|ID|detail` lines (`OK`, `DRY`, `INFO`, `WARN`) and a final `RESUMEN|…` line. Exit codes: **0** · **1** failure · **2** bad usage · **3** precondition not met (script missing, `settings.json` invalid, or a different `statusLine` exists and `--yes` was not given).

**Write scope.** Configuring Claude Code is this skill's purpose, so — unlike the other p4cc skills — it writes `~/.claude/statusline-command.sh` and `~/.claude/settings.json`. It never writes the plugin cache. Before modifying an existing file it keeps a copy next to it, `<file>.p4cc-bak-<timestamp>` (mode `0600`), and prints where. Nothing is restored automatically; to undo, copy the backup over the file.

---

## Steps

1. Run `python3 "$INSTALLER" --dry-run` first when the person asked for a dry-run, and stop there.
2. Otherwise run `python3 "$INSTALLER"`.
3. If it exits **3** because a different `statusLine` is already configured, show the current value and ask with **AskUserQuestion** whether to overwrite it; on yes re-run with `--yes`, on no stop.
4. Show the output as is. Restart Claude Code if the statusline does not appear immediately.

---

## Expected result

```
[~/your/project] · [⎇ main] · Sonnet 4.6 · cx:16% sn:88% wk:8%
```

| Segment | Color | Description |
|---------|-------|-------------|
| `[~/path]` | 🟡 Yellow | Project directory, `~`-collapsed |
| `[⎇ branch]` | 🔵 Cyan | Current git branch |
| `Model` | 🟠 Orange | Active model name |
| `cx:%` | 🟢/🟡/🔴 | Context window usage |
| `sn:%` | 🟢/🟡/🔴 | 5-hour session rate limit |
| `wk:%` | 🟢/🟡/🔴 | 7-day weekly rate limit |
