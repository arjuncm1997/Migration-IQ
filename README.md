# MigrationIQ

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

**Git-aware migration safety CLI for Django and Alembic projects.**

MigrationIQ detects migration graph conflicts, risky schema operations, and branch divergence *before* merging into a target branch.

---

## Features

- 🔍 **Migration Graph Analysis** – Build a DAG, detect multiple heads, cycles, orphans, and missing dependencies
- 🧹 **Lint Rules** – Catch DROP TABLE, DROP COLUMN, non-null without default, risky type changes
- 🔀 **Branch Comparison** – Detect parallel migrations, branch-behind state, and diverged graphs
- 🛡️ **CI Protection Gate** – Enforce risk score thresholds in your pipeline
- 📊 **Rich Terminal UI** – Beautiful, structured output with severity highlighting

---

## Installation

```bash
pip install migrationiq
```

Or install directly from GitHub:

```bash
pip install git+https://github.com/arjuncm1997/Migration-IQ.git
```

Or clone and install from source:

```bash
git clone https://github.com/arjuncm1997/Migration-IQ.git
cd Migration-IQ
pip install -e ".[dev]"
```

---

## Quick Start

```bash
migrationiq check                          # Check migration graph health
migrationiq lint                           # Lint for risky operations
migrationiq compare --target origin/main   # Compare branches
migrationiq ready                          # Full pre-PR check
migrationiq protect --ci                   # CI gate (fails on high risk)
```

---

## CLI Commands

### `migrationiq check`
Builds the migration dependency graph and detects structural issues.
```bash
migrationiq check --dir ./myproject --framework django
```
**Detects:** Multiple heads · Broken dependencies · Missing migrations · Cycles · Orphans

**Exit codes:** `0` = safe · `1` = warning · `2` = critical

### `migrationiq lint`
Parses migration files and flags risky schema operations.
```bash
migrationiq lint --dir ./myproject
```

### `migrationiq compare`
Compares migration state between your branch and a target branch.
```bash
migrationiq compare --target origin/main
```

### `migrationiq ready`
Runs the full suite before creating a PR: `fetch → compare → check → lint`.

### `migrationiq protect`
Same as `ready`, but enforces a risk score threshold. Designed for CI.
```bash
migrationiq protect --ci --threshold 7
```

---

## Configuration

Create a `migrationiq.yaml` in your project root:

```yaml
database: postgres
target_branch: origin/main
risk_threshold: 7
framework: auto

rules:
  allow_drop_table: false
  allow_drop_column: false
  require_two_step_non_null: true
```

---

## Risk Scoring

| Category                 | Score |
|--------------------------|-------|
| Drop table               | +10   |
| Multiple heads           | +9    |
| Drop column              | +8    |
| Non-null without default | +7    |
| Risky type change        | +6    |
| Large table alter        | +6    |
| Branch behind target     | +5    |

**Severity:** `0–3` LOW · `4–6` MEDIUM · `7–9` HIGH · `10+` CRITICAL

---

## Git Hooks

```bash
# .git/hooks/pre-commit
#!/bin/sh
migrationiq lint

# .git/hooks/pre-push
#!/bin/sh
migrationiq compare --target origin/main
```

---

## GitHub Actions CI

```yaml
name: Migration Safety Check
on:
  pull_request:
    branches: [main]
jobs:
  migrationiq:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install migrationiq
      - run: migrationiq protect --ci --threshold 7
```

---

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -v --cov=migrationiq --cov-report=term-missing
```

---

## Architecture

```
migrationiq/
├── cli/            # Typer commands
├── core/           # Engine, graph, scoring, comparison
├── adapters/       # Django & Alembic parsers
├── rules/          # Pluggable lint rules
├── git/            # Safe subprocess Git wrapper
├── config/         # Pydantic settings + YAML loader
└── utils/          # Rich-based logging
```

---

## License

MIT
