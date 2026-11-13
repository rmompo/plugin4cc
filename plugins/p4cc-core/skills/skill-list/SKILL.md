---
name: skill-list
description: Lists all p4cc-* plugin skills installed in the current CLI, in a table with columns plugin|skill|v|ready|description. Also invoked explicitly as /p4cc-core:skill-list.
version: 35
argument-hint: "[--json] [--lines] [--home DIR]"
allowed-tools: [Bash]
---

# Skill List

Lists the p4cc-* plugin skills installed in the current CLI (the Claude Code plugin cache), with their version and whether each one is ready to use. Read-only. The skill version always comes from the catalog, never from the `SKILL.md` frontmatter (which can be out of sync).

---

## Engine

```bash
# <Base directory for this skill> is shown when the skill is loaded; the engine is two levels up
ENGINE="<Base directory for this skill>/../../resources/scripts/skill_list.py"
python3 "$ENGINE" [--json | --table] [--home DIR]
```

## How to run it

1. Without options (a person invoking the skill) run `python3 "$ENGINE" --table` and show the output exactly as printed: the Unicode table (columns `plugin │ skill │ v │ ready │ description`) and the footer `N plugins · M skills · M enabled`.
2. With `--json` run `python3 "$ENGINE" --json` and print it as is.
3. With `--lines` run `python3 "$ENGINE"` (the `STATE|ID|detail` lines) and print it as is.
4. Add `--home DIR` when the user passed it.

## Rules the output follows

- **Enabled** (🟢/🔴 prefix on `plugin` and `skill`): a plugin is enabled when its directory has at least one installed version in the cache; a skill when its `SKILL.md` exists in the active version.
- **ready:** `✅` when the skill has no external dependency or all of them are present, `❌` when a declared dependency is missing. Dependencies resolve skill-level first, then plugin-level. `tool` → present in `PATH`; `plugin` → installed in the cache. Only presence is checked (version checks belong to each plugin's `check`). **`install` and `check` always show an empty `ready` column** — they are the skills that perform the check, so ✅/❌ there would be circular.
- Sorted by `plugin` then `skill`; descriptions are the first sentence before `. Also invoked`, wrapped at 60 characters.

### Output and exit codes

Default (script): one line per skill, `STATE|<plugin>:<skill>|v<N> ready=<yes|no|n/a> enabled=<yes|no> — <description>` (`OK`, or `WARN` when a dependency is missing), then `RESUMEN|0 FAIL|<m> WARN`. `--json` gives `{plugin, skill, findings[], summary}`. Exit codes: **0** · **2** bad usage · **3** no plugin cache found (a missing dependency is a WARN, so a normal listing exits 0).
