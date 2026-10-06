# p4cc-coding

Coding standards and best practices for Claude Code. Universal directives (SOLID, DRY, naming, error handling, security) load automatically at session start. Stack-specific standards for TypeScript, Python, Go, and Java can be activated on demand.

## Skills

| Skill | Invocation | Auto | Description |
|-------|-----------|:----:|-------------|
| `code-standards` | `/p4cc-coding:code-standards` | ✅ | Universal coding directives: SOLID, DRY/KISS/YAGNI, naming, functions, immutability, error handling, documentation, testability, modularity, complexity, security, style |
| `typescript-standards` | `/p4cc-coding:typescript-standards` | — | TypeScript/JavaScript-specific standards: strict mode, type safety, async/await, null safety, ESLint/Prettier |
| `python-standards` | `/p4cc-coding:python-standards` | — | Python-specific standards: PEP 8, type hints, context managers, exceptions, dataclasses, pytest |
| `go-standards` | `/p4cc-coding:go-standards` | — | Go-specific standards *(proposal)* |
| `java-standards` | `/p4cc-coding:java-standards` | — | Java/Kotlin-specific standards *(proposal)* |
| `code-review` | `/p4cc-coding:code-review` | — | Review current diff against active standards *(proposal)* |

## How loading works

```
Session start
    └── p4cc-coding agent fires automatically
            └── code-standards loaded silently (P4CCC-001 to P4CCC-016 active)

On demand
    └── /p4cc-coding:typescript-standards  →  P4CCC-TS-001 to P4CCC-TS-010 active
    └── /p4cc-coding:python-standards      →  P4CCC-PY-001 to P4CCC-PY-010 active
```

## Installation

```bash
claude plugins marketplace add rmompo/plugin4cc
claude plugins install p4cc-coding
```
