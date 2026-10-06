# plugin4cc

A personal [Claude Code](https://claude.ai/code) plugin marketplace: productivity skills, agents and tooling for everyday development.

---

## Installation

```bash
claude plugin marketplace add rmompo/plugin4cc
claude plugin install <plugin>@plugin4cc
```

Full install, update, uninstall, enable and disable instructions → **[INSTALL.md](./INSTALL.md)**

---

## Plugins

| Plugin | Description | Status | Spec |
|--------|-------------|--------|------|
| `p4cc-agent` | Agent definition auditor: validates markdown agent files for structural completeness, naming conventions, and cross-reference integrity. | `beta` | [spec](./specs/p4cc-agent.md) |
| `p4cc-buddy` | Skills for \<company> employees: \<hr-platform> mission report generation from workspace context. | `beta` | [spec](./specs/p4cc-buddy.md) |
| `p4cc-ccvv` | AI-powered CV generation and management — multi-user profiles, job offer adaptation, and multi-format export. | `beta` | [spec](./specs/p4cc-ccvv.md) |
| `p4cc-statusline` | Claude Code-exclusive enhancements: custom statusline with project path, git branch, active model and color-coded usage metrics. | `stable` | [spec](./specs/p4cc-statusline.md) |
| `p4cc-coding` | Coding standards and best practices plugin: universal directives (SOLID, DRY, naming, error handling, security) auto-loaded at session start, with stack-specific skills for TypeScript, Python, Go, and Java. | `beta` | [spec](./specs/p4cc-coding.md) |
| `p4cc-converter` | Converts documents to Markdown (PDF, DOC, DOCX, PPT, PPTX) using a multi-step local tool pipeline. | `beta` | [spec](./specs/p4cc-converter.md) |
| `p4cc-core` | Core productivity plugin: behavioral directives (P4CCD), intelligent model routing via subagents, and Conventional Commits enforcement. | `stable` | [spec](./specs/p4cc-core.md) |
| `p4cc-crawler` | Web crawler and documentation extractor: crawls sites (static or SPA/Storybook), filters by topic, downloads attachments, and generates structured Markdown output. | `beta` | [spec](./specs/p4cc-crawler.md) |
| `p4cc-plugin` | Marketplace lifecycle tooling: create and manage plugins and skills with automatic version tracking. | `beta` | [spec](./specs/p4cc-plugin.md) |

Skills per plugin are indexed in [`plugins/README.md`](./plugins/README.md).

---

## Repository layout

| Path | Content |
|------|---------|
| `.claude-plugin/marketplace.json` | Marketplace index consumed by Claude Code |
| `plugins/<plugin>/` | One directory per plugin (`.claude-plugin/plugin.json`, `skills/`, optional `agents/`, `settings.json`) |
| `specs/<plugin>.md` | Canonical spec for each plugin |
| `specs/catalog.json` | Source of truth for plugins, skills, versions and changelogs (validated by `catalog.schema.json`) |

---

## Adding a New Plugin

Use the `p4cc-plugin` skill — it scaffolds everything in one step:

```
/p4cc-plugin:create <plugin-name> [skill1 skill2 ...]
```

See [`specs/p4cc-plugin.md`](./specs/p4cc-plugin.md) for full details.
