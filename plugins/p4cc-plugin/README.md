# p4cc-plugin

Plugin lifecycle management for the plugin4cc Claude Code marketplace. Tools to scaffold, update and maintain plugins.

## Skills

| Skill | Invocation | What it does |
|-------|-----------|--------------|
| `create` | `/p4cc-plugin:create <name> [skills...]` | Scaffolds a complete new plugin with all required files and registry entries |
| `update` | `/p4cc-plugin:update <plugin>` | Updates plugin metadata (description, status) and propagates changes to all catalogs and the Claude Code cache |
| `remove` | `/p4cc-plugin:remove <plugin>` | Removes a plugin and all its files from the repo, every catalog, and the Claude Code cache — requires explicit confirmation |
| `skill-add` | `/p4cc-plugin:skill-add <plugin> <skill>` | Adds a new skill to an existing plugin, bumps Z versioning, creates the SKILL.md, and syncs the Claude Code cache |
| `skill-update` | `/p4cc-plugin:skill-update <plugin> <skill>` | Bumps the version of an existing skill, records the changelog entry in catalog.json, and syncs the Claude Code cache |
| `skill-remove` | `/p4cc-plugin:skill-remove <plugin> <skill>` | Removes a skill from a plugin — deletes SKILL.md and updates catalog.json (Z does not decrease) |
| `skill-doctor` | `/p4cc-plugin:skill-doctor [plugin] [skill]` | Audits plugin skills for version mismatches, frontmatter issues, allowed-tools gaps, and structural defects — offers to auto-fix eligible findings |
| `doc-doctor` | `/p4cc-plugin:doc-doctor [plugin]` | Audits documentation completeness and language across specs, plugins/README.md, and README.md — reports findings and offers to auto-generate missing content |
| `sanitize` | `/p4cc-plugin:sanitize [plugin] [skill]` | Scans plugin and skill files for sensitive information and offers to anonymize it |

## Installation

```bash
claude plugins marketplace add rmompo/plugin4cc
claude plugins install p4cc-plugin
```

## Notes

- Encodes the full plugin creation checklist to avoid common mistakes.
- Automatically updates both registry files (`marketplace.json` and `plugins/README.md`).
