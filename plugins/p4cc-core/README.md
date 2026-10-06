# p4cc-core

Core productivity plugin for Claude Code. Applies behavioral directives automatically and routes tasks to the right model tier via subagents.

## Behavioral Directives (P4CCD)

Active automatically when the plugin is installed — no setup required.

| ID | Directive |
|----|-----------|
| P4CCD-000 | Load directives from source at session start — never from memory |
| P4CCD-001 | Restricted actions require explicit confirmation — restriction restored immediately after |
| P4CCD-002 | Destructive actions forbidden without explicit authorization |
| P4CCD-003 | Consultation mode by default — execution requires explicit directive |
| P4CCD-004 | Git commits require unambiguous explicit instruction |
| P4CCD-005 | Clarify ambiguous input before acting |
| P4CCD-006 | Every factual claim must be verifiable — state uncertainty explicitly |
| P4CCD-007 | Evaluate independently before agreeing or validating |
| P4CCD-008 | Respond in the language of the user's last message |
| P4CCD-009 | Lists and comparable items must use structured, identified output |

Full spec: [`.project/rules.md`](./.project/rules.md)

---

## Skills

### 🔀 `model-route`

Evaluates task complexity and **delegates** to the right model tier via subagents.

| Agent | Model | Best for |
|-------|-------|----------|
| `p4cc-core:p4cc-lightweight` | **Haiku** | Quick lookups, file search, simple formatting |
| `p4cc-core:p4cc-standard` | **Sonnet** | General development, refactoring, PR reviews |
| `p4cc-core:p4cc-advanced` | **Opus** | Architecture design, complex debugging, critical decisions |

**Invocation:**
- Auto — activates when Claude detects complexity signals in the task
- Explicit — `/p4cc-core:model-route [task description]`

---

### 📝 `git-commit`

Generates and enforces [Conventional Commits](https://www.conventionalcommits.org/) on every commit.

- Interprets the user's intent (any language) and maps it to the correct type and scope
- **Always outputs in English**, regardless of input language
- **Never adds `Co-Authored-By:` lines**
- Subject ≤72 chars, imperative mood, no trailing period
- Breaking changes flagged with `!` and `BREAKING CHANGE:` footer

**Invocation:**
- Auto — activates whenever Claude is about to propose or execute a `git commit`
- Explicit — `/p4cc-core:git-commit [hint]`

**Examples:**

| Input | Output |
|-------|--------|
| `"arreglé el login"` | `fix(auth): resolve login failure on invalid credentials` |
| `"nueva pantalla de perfil"` | `feat(profile): add user profile screen` |
| *(staged changes, no hint)* | `feat(auth): add OAuth2 login with Google provider` |

---

### 🧠 `model-behaviour`

Loads and activates P4CCD behavioral directives for the session. Fires automatically at session start via the p4cc-core agent.

- Reads directives from the plugin cache — never from training memory
- Applies all P4CCD rules (P4CCD-000 through P4CCD-009) for the duration of the session
- Safe to re-invoke to reload updated directives

**Invocation:**
- Auto — fires at session start via the p4cc-core agent
- Explicit — `/p4cc-core:model-behaviour`

---

### 📋 `skill-list`

Lists all p4cc-* plugin skills installed in the current CLI, in a Markdown table with plugin, version, skill, tools status, and description columns.

- Reads from the CLI plugin cache — no network access
- Shows `✅` / `❌` in the `tools` column based on external dependency availability
- Collapses repeated plugin names for readability

**Invocation:**
- Explicit — `/p4cc-core:skill-list`

---

### 🧹 `git-sanitize`

Ensures every git repo has correct line-ending hygiene. At session start, silently checks for `.gitattributes` with `eol=lf` and tracked files with CRLF contamination. Creates the file if missing and offers to normalize contaminated files. Silent when everything is clean.

**Invocation:**
- Auto — fires at session start via the p4cc-core agent
- Explicit — `/p4cc-core:git-sanitize`

---

### 🔧 `setup`

Verifies that all external tools required by p4cc-core skills are installed and available in PATH. Reports status with install instructions for each missing dependency.

**Invocation:**
- Explicit — `/p4cc-core:setup`

---

## Installation

```bash
claude plugins marketplace add rmompo/plugin4cc
claude plugins install p4cc-core
```

No setup step required — behavioral directives activate automatically.

## Companion plugin

[`p4cc-statusline`](../p4cc-statusline/README.md) — visual enhancement with custom statusline (optional).
