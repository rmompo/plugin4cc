# Plugin Spec: p4cc-core

> **Status:** `stable` | **Version:** `1.2.37`

---

## Overview

`p4cc-core` bundles three skills that address the most common friction points in daily AI-assisted development: enforcing behavioral directives, choosing the right model, and writing consistent commit messages. All three skills activate automatically from context and can also be invoked explicitly.

---

## Skill 1: `model-behaviour`

### Purpose

Load and apply P4CCD behavioral directives for the session. Fires automatically at session start via the p4cc-core agent. Ensures the model always operates from the canonical, up-to-date directive set — never from training memory or stale context.

### Invocation

```bash
/p4cc-core:model-behaviour    # inspect or reload directives at any time
```

### Behavior

At session start, reads the directive file from the plugin cache:
```bash
find ~/.claude/plugins -path "*/p4cc-core/skills/model-behaviour/SKILL.md" 2>/dev/null | head -1
```

Applies directives P4CCD-000 through P4CCD-009 for the duration of the session.

### Key directives (summary)

| ID | Name | Effect |
|----|------|--------|
| P4CCD-000 | Load from source | Always read from plugin cache — never from memory |
| P4CCD-001 | Confirmation protocol | Any restricted action requires explicit user confirmation |
| P4CCD-002 | Destructive actions | Extra confirmation for irreversible operations |
| P4CCD-003 | Consultation mode | Default is propose/explain — not execute |
| P4CCD-004 | Commit gating | Never commit without explicit user instruction |
| P4CCD-005 | Ambiguity | Clarify before acting on ambiguous input |
| P4CCD-006 | Factual claims | State uncertainty explicitly — never hallucinate |
| P4CCD-007 | Independent evaluation | Evaluate before agreeing — no silent validation |
| P4CCD-008 | Language | Respond in the language of the user's last message |
| P4CCD-009 | Structured output | Lists and comparable items use numbered format |

### Non-Goals
- Does not apply to tasks where the user has explicitly overridden a directive
- Does not block execution indefinitely — one confirmation = one execution

---

## Skill 2: `model-route`

### Purpose

Guide the model into selecting the most appropriate model tier for a given task, balancing output quality, latency, and token cost.

### Invocation

```bash
/p4cc-core:model-route                  # route the current task
/p4cc-core:model-route <description>    # route a described task
```

### Routing tiers

| Tier | Characteristics | Representative Tasks |
|------|-----------------|----------------------|
| **Lightweight** | Fast, cheap, single-step | File search, grep, quick formatting, boilerplate, log parsing |
| **Standard** *(default)* | Balanced, multi-step | Feature impl, bug fixes, refactoring, PR review, test writing |
| **Advanced** | Deep reasoning, high stakes | System design, unknown-root debugging, security analysis, architecture decisions |

### Decision criteria
1. **Scope** — one step or a reasoning chain?
2. **Stakes** — cost of an error?
3. **Ambiguity** — is the problem well-defined?
4. **Frequency** — repeated in a loop?

### Non-Goals
- Does not override explicit model selections by the user
- Does not apply organizational or policy-level model restrictions

---

## Skill 3: `git-commit`

### Purpose

Ensure every `git commit` follows the [Conventional Commits v1.0.0](https://www.conventionalcommits.org/) specification, producing a clean, machine-readable commit history.

### Invocation

```bash
/p4cc-core:git-commit              # auto-infer from staged changes
/p4cc-core:git-commit <hint>       # use hint to guide the message
```

### Format

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

### Allowed types

| Type | Use for |
|------|---------|
| `feat` | New user-facing feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `style` | Formatting, whitespace — no logic change |
| `refactor` | Code restructure without feature/fix |
| `perf` | Performance improvement |
| `test` | Adding or fixing tests |
| `build` | Build system or dependency changes |
| `ci` | CI/CD pipeline changes |
| `chore` | Maintenance, tooling, non-production |
| `revert` | Reverts a previous commit |

### Rules
- Subject line: max 72 chars, imperative mood, no trailing period
- Always written in English regardless of user language
- Never includes `Co-Authored-By:` lines
- Breaking changes: `feat(api)!:` + `BREAKING CHANGE:` footer

### Non-Goals
- Does not block commits — suggests and corrects, never refuses
- Does not validate scope against real module names

---

## Skill: `skill-list`

### Purpose
Lists the p4cc-* skills installed in the Claude Code plugin cache with their catalog version and `ready` status (dependencies present). Read-only.

### Invocation
```
/p4cc-core:skill-list [--json] [--lines] [--home DIR]
```

### Output
- Default (script): `STATE|<plugin>:<skill>|v<N> ready=<yes|no|n/a> enabled=<yes|no> — <description>` per skill (`OK`, or `WARN` when a dependency is missing), then `RESUMEN|0 FAIL|<m> WARN`. `--json` gives `{plugin, skill, findings[], summary}`.
- Invoked as a skill without options it shows the Unicode table (`--table`) and the footer `N plugins · M skills · M enabled`, fed by the same data.
- Exit codes: `0` · `2` bad usage · `3` no plugin cache found. `install` and `check` always show an empty `ready` column.

### Non-Goals
- Does not verify tool versions (each plugin's `check` does).
- Never writes anything.

---

## Skill: `sanitize`

### Purpose
Scans the repository's text files for sensitive information (credentials, infrastructure, PII, company data, financial and special-category data) and offers to replace findings with safe placeholders.

### Invocation
```
/p4cc-core:sanitize [path] [--dry-run] [--repo PATH]
```

### Options and safety
- `--dry-run` — runs the scan and prints the exact plan, one `DRY|modify|<file>:<line> (<category>) <masked> -> <placeholder>` line per replacement, ending with `RESUMEN|DRY|…`; writes nothing and asks nothing.
- `--repo PATH` — repository to scan (same as `P4CC_REPO`). Resolution: flag → `P4CC_REPO` → git root → walk up to `.claude-plugin/marketplace.json`; never an unbounded `find ~`.
- **Backup before editing**: files about to be modified are copied to `<repo>/.p4cc/bak/<timestamp>/files/` (dirs `0700`, files `0600`). Nothing is restored automatically.
- **Secrets are never printed in full**: only category, line, the first 3 characters + `***` and the length; `.env` contents are never shown.

### Non-Goals
- Does not rewrite git history.

---

## Skill: `git-sanitize`

### Purpose

Ensure every git repo has correct line-ending hygiene. Fires automatically at session start: creates `.gitattributes` with `eol=lf` if missing, detects tracked files with CRLF contamination, and offers to normalize them. Silent when everything is already clean.

### Invocation

```bash
/p4cc-core:git-sanitize    # explicit run — always prints full status report
```

Auto — fires at session start via the p4cc-core agent.

### Behavior

| State | Session-start | Explicit |
|-------|--------------|---------|
| `.gitattributes` OK, no CRLF files | silent | ✅ status report |
| `.gitattributes` missing/incomplete | creates it + prints notice | creates it + report |
| CRLF files found | asks user to normalize | asks user to normalize |
| Not a git repo | silent exit | silent exit |

### `.gitattributes` content enforced

```
* text=auto eol=lf
*.png binary  *.jpg binary  *.woff binary  *.vsix binary  ...
```

### Options and safety
- `--dry-run` (explicit invocation) — runs every detection step, writes nothing (no `.gitattributes`, `git config`, `sed -i`, `git add`/`update-index`, no backup) and prints the plan as `DRY|create|modify|<target> (<what>)`, ending with `RESUMEN|DRY|…`. All writes go through one gate, so dry-run and real run share the code.
- Files that already exist are copied to `<repo>/.p4cc/bak/<timestamp>/files/` (dirs `0700`, files `0600`) before being modified.
- CRLF detection uses `git ls-files --eol` (no dependency on the `file` command).

### Non-Goals
- Does not modify files without user confirmation
- Does not affect user's `core.autocrlf` git config — operates at repo level via `.gitattributes`

---

## Skill: `install`

### Purpose
Creates `~/.p4cc/` and installs the marketplace `catalog.json` copy. Idempotent. A real run is followed by `check`.

### Invocation
```
/p4cc-core:install [--dry-run] [--json] [--home DIR]
```

### Options
- `--dry-run` — resolves everything, **writes nothing**, prints the exact plan (`DRY|create|modify|<path>`) and ends with `RESUMEN|DRY|…` instead of `RESUMEN|OK|…`. Dry-run and real run share one code path.
- `--json` — machine-readable output. `--home DIR` — replaces `~` for `~/.p4cc/` (also `P4CC_HOME`).
- Exit codes: `0` ok · `1` failure · `2` bad usage · `3` precondition not met.

### Non-Goals
- Never installs external tools: `check` reports the command the person must run.
- Never writes another marketplace's `~/.p4cc/catalog.json` (it is left untouched and reported), nor the Claude Code cache.

---

## Skill: `check`

### Purpose
Read-only verification. Verifies `~/.p4cc/` and a valid, up-to-date `catalog.json`, and the tool `git` (used by `git-commit`). Reports how to install anything missing.

### Invocation
```
/p4cc-core:check [--json] [--lines] [--home DIR]
```

### Output
- Default (script): one line per finding, `STATE|ID|detail` (`OK`, `INFO`, `WARN`, `FAIL`), then `RESUMEN|<n> FAIL|<m> WARN`. IDs are stable across versions: `folder-*`, `catalog-*`, `res-*`, `tool-*`, `pkg-*`, `ocr-lang-*`, `profile-*`.
- `--json` — `{plugin, skill, findings[{estado, id, detalle, componente}], summary{fail, warn}}`.
- Invoked as a skill without options it shows the human presentation (`--table`), fed by the same findings.
- Exit codes: `0` no failures · `1` failures · `2` bad usage · `3` precondition not met.

### Non-Goals
- Never creates, modifies or installs anything.
- Optional components (OCR, Playwright, `openpyxl`…) are WARN, never FAIL.

---

## Changelog

| Version | Changes |
|---------|---------|
| 1.2.37 | git-sanitize: add --dry-run and backup before modifying; CRLF detection via git ls-files --eol (no dependency on file) |
| 1.2.36 | sanitize: add --dry-run, --repo, backup before editing, secrets masked in every output; no unbounded find |
| 1.2.35 | skill-list: STATE\|ID\|detail output, --json, --lines and --table from a script; stable IDs |
| 1.2.34 | check: STATE\|ID\|detail output, --json, --table and exit codes from the shared check engine |
| 1.2.33 | install: add --dry-run, --json and --home; creates folders and the catalog copy through the shared check engine |
| 1.2.30 | model-route: fix: delegate via Agent tool, not Skill tool |
| 1.2.29 | skill-list: remove enabled column, use 🟢/🔴 emoji indicators on plugin and skill cells |
| 1.2.15 | setup: add plugin dep check; skill-list: rename column to ready, check all dep types |
| 1.2.13 | setup: read dependencies[] instead of requires[] |
| 1.2.12 | skill-list: fix skill version source to catalog.json |
| 1.2.11 | skill-list: add dedicated v column for skill version |
| 1.2.10 | skill-list: add plugin/skill version display, collapse repeated plugin column |
| 1.2.9 | Add setup skill to verify git and other tool dependencies |
| 1.2.8 | git-commit: declare git as skill-level requires; skill-list: resolve tools from skill.requires when present |
| 1.2.7 | skill-list: setup skills always show empty tools column |
| 1.2.6 | skill-list: add tools column showing external dependency status |
| 1.2.5 | skill-list: use Markdown table format in output |
| 1.2.4 | Add skill-list skill |
| 1.2.32 | `skill-list`: treat install and check as circular skills with an empty ready column |
| 1.2.31 | Add `check` skill; `install` now creates folders/files and delegates verification to `check` |
| 1.2.18 | Add `git-sanitize` skill — session-start CRLF hygiene enforcer |
| 1.2.17 | `sanitize`: update argument-hint to `[path]` |
| 1.2.16 | `sanitize`: new skill (moved from p4cc-plugin) |
| 1.2.3 | Skill versions normalized to Z system (integers) |
| 1.2.0 | Skill renames: commit→git-commit, model-routing→model-route, behaviour→model-behaviour |
| 1.1.0 | Add model-behaviour skill (P4CCD directives) |
| 1.0.0 | Initial release — model-route and git-commit skills |
