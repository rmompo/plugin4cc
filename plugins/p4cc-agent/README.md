# p4cc-agent

> **Status:** `beta`

Agent definition auditor: validates markdown agent files for structural completeness, naming conventions, and cross-reference integrity.

## Skills

| Skill | Invocation | Description |
|-------|-----------|-------------|
| `md-check` | `/p4cc-agent:md-check` | Audits a single agent markdown file for structural completeness and naming conventions. |
| `md-checkrefs` | `/p4cc-agent:md-checkrefs` | Audits an agent markdown file and all files it references, checking cross-reference integrity. |

## Installation

```bash
claude plugins marketplace add rmompo/plugin4cc
claude plugins install p4cc-agent
```
