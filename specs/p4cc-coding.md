# Plugin Spec: p4cc-coding

> **Status:** `beta` | **Version:** `1.1.6`

---

## Overview

`p4cc-coding` is a coding standards plugin for the plugin4cc ecosystem. It provides universal coding directives (SOLID, DRY, KISS, naming, error handling, security, testability, complexity control) that load automatically at session start, plus stack-specific directives for TypeScript/JavaScript and Python that can be activated on demand.

The universal directives are identified by the `P4CCC-NNN` scheme (Plugin4 Coding), and stack-specific ones use a sub-namespace (`P4CCC-TS-NNN`, `P4CCC-PY-NNN`, etc.).

---

## Skill: `code-standards`

### Purpose
Loads and activates 16 universal coding directives (P4CCC-001 to P4CCC-016) applicable to any programming language or stack. Fires automatically at session start via the `p4cc-coding` agent.

### Invocation
```
/p4cc-coding:code-standards
```
Also fires silently at session start — no invocation needed.

### Directives covered

| ID | Category | Summary |
|----|----------|---------|
| P4CCC-001 | SOLID: SRP | One class/module/function = one reason to change |
| P4CCC-002 | SOLID: OCP | Extend without modifying existing code |
| P4CCC-003 | SOLID: LSP | Subtypes must not break the supertype contract |
| P4CCC-004 | SOLID: ISP | Small, specific interfaces — no "Swiss Army knife" |
| P4CCC-005 | SOLID: DIP | Depend on abstractions, inject dependencies |
| P4CCC-006 | DRY/KISS/YAGNI | No duplication, no speculation, simplest solution wins |
| P4CCC-007 | Naming | Descriptive, consistent, semantic prefixes |
| P4CCC-008 | Functions | One thing, max 4 params, early return, no bool flags |
| P4CCC-009 | Immutability | Immutable by default, minimize global state |
| P4CCC-010 | Error Handling | Fail fast, descriptive messages, never silence |
| P4CCC-011 | Documentation | Comment the why, not the what; sync comments with code |
| P4CCC-012 | Testability | Designed to test, DI, AAA, one behavior per test |
| P4CCC-013 | Modularity | High cohesion, low coupling, domain-based structure |
| P4CCC-014 | Complexity | Low cyclomatic, no deep nesting, Boy Scout Rule |
| P4CCC-015 | Security | Sanitize inputs, no secrets in code, least privilege |
| P4CCC-016 | Style | One linter/formatter, code review before merge, atomic commits |

### Non-Goals
- Does not replace linters or static analysis tools
- Does not apply to a specific language (use stack-specific skills for that)

---

## Skill: `typescript-standards`

### Purpose
Activates 10 TypeScript/JavaScript-specific coding directives (P4CCC-TS-001 to P4CCC-TS-010) to complement the universal standards.

### Invocation
```
/p4cc-coding:typescript-standards
```

### Directives covered

| ID | Summary |
|----|---------|
| P4CCC-TS-001 | `"strict": true` mandatory, no `any` |
| P4CCC-TS-002 | Explicit types at public/exported boundaries |
| P4CCC-TS-003 | `async/await` over raw Promises |
| P4CCC-TS-004 | No non-null assertion (`!`) without comment justification |
| P4CCC-TS-005 | `const` > `let`, never `var`, `readonly` on non-mutating props |
| P4CCC-TS-006 | ESM over CommonJS, one primary export per file |
| P4CCC-TS-007 | Custom error classes extending `Error` |
| P4CCC-TS-008 | No `==`, no `eval()`, no parameter mutation, no `delete` |
| P4CCC-TS-009 | Jest/Vitest: test files co-located, mock at boundary |
| P4CCC-TS-010 | ESLint + Prettier mandatory, CI enforces lint |

### Non-Goals
- Does not cover framework-specific rules (React, Next.js, Vue, etc.)
- Does not replace `tsc` type checking

---

## Skill: `python-standards`

### Purpose
Activates 10 Python-specific coding directives (P4CCC-PY-001 to P4CCC-PY-010) to complement the universal standards.

### Invocation
```
/p4cc-coding:python-standards
```

### Directives covered

| ID | Summary |
|----|---------|
| P4CCC-PY-001 | PEP 8 via `ruff`/`black`, 88-char lines |
| P4CCC-PY-002 | Type hints mandatory, `mypy --strict` |
| P4CCC-PY-003 | `with` for all resources, never manual `.close()` |
| P4CCC-PY-004 | No bare `except:`, custom exception hierarchy, `raise ... from err` |
| P4CCC-PY-005 | `@dataclass`, `Protocol`, `TypedDict` over raw classes/dicts |
| P4CCC-PY-006 | `tuple` over `list` for immutable, no mutable defaults |
| P4CCC-PY-007 | Generators over lists for single-pass iteration |
| P4CCC-PY-008 | `isort` import order, no `import *`, explicit relative imports |
| P4CCC-PY-009 | `pytest` + fixtures + `@pytest.mark.parametrize`, 80% coverage |
| P4CCC-PY-010 | `pyproject.toml`, separate dev deps, pin versions in production |

### Non-Goals
- Does not cover framework-specific rules (Django, FastAPI, etc.)
- Does not replace `mypy` or `ruff` type/lint checking

---

## Skill: `go-standards` *(proposal)*

### Purpose
Will activate Go-specific coding directives covering goroutines, channels, error returns, interface patterns, `defer`, context propagation, and `go test`.

### Invocation
```
/p4cc-coding:go-standards
```

> **Status: proposal — not yet implemented.**

---

## Skill: `java-standards` *(proposal)*

### Purpose
Will activate Java/Kotlin-specific coding directives covering Java 17+ features, Spring Boot patterns, exception hierarchy, Stream API, Optional, and JUnit 5 testing.

### Invocation
```
/p4cc-coding:java-standards
```

> **Status: proposal — not yet implemented.**

---

## Skill: `code-review` *(proposal)*

### Purpose
Will analyze the current `git diff` or a specified file against all active p4cc-coding standards (universal + any loaded stack-specific skill) and return a structured violation report with severity levels (ERROR / WARNING / INFO).

### Invocation
```
/p4cc-coding:code-review [file-or-diff-target]
```

> **Status: proposal — not yet implemented.**

---

## Changelog

| Version | Changes |
|---------|---------|
| 1.0.6 | Add `code-review` skill (proposal) |
| 1.0.5 | Add `java-standards` skill (proposal) |
| 1.0.4 | Add `go-standards` skill (proposal) |
| 1.0.3 | Add `python-standards` skill |
| 1.0.2 | Add `typescript-standards` skill |
| 1.0.1 | Add `code-standards` skill |
| 1.0.0 | Initial release |
