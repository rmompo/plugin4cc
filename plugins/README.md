# Plugins

Index of the plugins in this marketplace. Register the marketplace once and all plugins become available via `claude plugin install`.

## Register the marketplace

```bash
claude plugin marketplace add rmompo/plugin4cc
```

## Install a plugin

```bash
claude plugin install p4cc-core@plugin4cc
```

## Available plugins

| Plugin | Status | Skills | Auto-setup |
|--------|--------|--------|------------|
| [`p4cc-core`](./p4cc-core/README.md) | stable | `model-behaviour`, `model-route`, `git-commit`, `git-sanitize`, `sanitize`, `skill-list`, `setup` | ✅ via agent |
| [`p4cc-statusline`](./p4cc-statusline/README.md) | stable | `install` | ✅ via agent |
| [`p4cc-buddy`](./p4cc-buddy/README.md) | beta | `gcomp` | — |
| [`p4cc-plugin`](./p4cc-plugin/README.md) | beta | `create`, `update`, `remove`, `skill-add`, `skill-update`, `skill-remove`, `skill-doctor`, `doc-doctor` | — |
| [`p4cc-ccvv`](./p4cc-ccvv/README.md) | beta | `setup`, `profile-gather`, `profile-update`, `generate`, `regen`, `export` | — |
| [`p4cc-converter`](./p4cc-converter/README.md) | beta | `setup`, `any-to-md` | — |
| [`p4cc-crawler`](./p4cc-crawler/README.md) | beta | `setup`, `extract` | — |
| [`p4cc-agent`](./p4cc-agent/README.md) | beta | `md-check`, `md-checkrefs` | — |
| [`p4cc-coding`](./p4cc-coding/README.md) | beta | `code-standards`, `typescript-standards`, `python-standards`, `go-standards`, `java-standards`, `code-review` | ✅ via agent |

## Update the marketplace index

```bash
claude plugin marketplace update plugin4cc
```

## Remove the marketplace

```bash
claude plugin marketplace remove plugin4cc
```
