# p4cc-plugin

Plugin lifecycle management for the plugin4cc Claude Code marketplace. Tools to scaffold, update and maintain plugins.

## Skills

| Skill | Invocation | What it does |
|-------|-----------|--------------|
| `create` | `/p4cc-plugin:create <name> [skills...]` | Scaffolds a complete new plugin with all required files and registry entries |
| `update` | `/p4cc-plugin:update <plugin>` | Updates plugin metadata (description, status, version bump) and propagates it to the catalogs; keeps a backup |
| `remove` | `/p4cc-plugin:remove <plugin> [--soft\|--restore]` | Removes a plugin (backup first, explicit confirmation) or retires it logically without deleting files |
| `skill-add` | `/p4cc-plugin:skill-add <plugin> <skill>` | Adds a new skill to an existing plugin, bumps Z versioning and creates the SKILL.md |
| `skill-update` | `/p4cc-plugin:skill-update <plugin> <skill>` | Bumps the version of an existing skill and records the changelog entry in catalog.json |
| `skill-remove` | `/p4cc-plugin:skill-remove <plugin> <skill> [--soft\|--restore]` | Removes a skill (backup first, explicit confirmation) or retires it logically; Z does not decrease |
| `skill-doctor` | `/p4cc-plugin:skill-doctor [--plugin P] [--skill S] [--fix auto\|N,M]` | Audits skills (C1–C10). Report-only by default; `--fix` applies the `[auto]` defects after a backup |
| `doc-doctor` | `/p4cc-plugin:doc-doctor [--plugin P] [--fix auto\|N,M]` | Audits documentation (D1–D9). Report-only by default; `--fix` applies the `[auto]` defects after a backup |

## Common options

Every skill accepts `--dry-run` (writes nothing, prints the exact plan and ends with `RESUMEN|DRY|…`), `--json`, `--repo PATH` (same as `P4CC_REPO`) and `--home DIR`. Output is `STATE|ID|detail` lines plus a `RESUMEN|…` line; exit codes are `0` ok · `1` failures · `2` bad usage · `3` precondition not met. All of it runs through one script, `resources/scripts/p4cc_ops.py`, so it also works from a shell or CI.

## Installation

```bash
claude plugins marketplace add rmompo/plugin4cc
claude plugins install p4cc-plugin
```

## Notes

- Encodes the full plugin creation checklist to avoid common mistakes.
- Works with any marketplace (repo resolved from `--repo`, `P4CC_REPO` or the current git repository) and never writes the Claude Code cache — after pushing, update through `/plugin`.
- Destructive operations and `--fix` leave a `0600` backup in `<repo>/.p4cc/bak/` first; keep `.p4cc/` out of git.
