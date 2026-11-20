# Contributing to LiftPilot

Thank you for your interest. LiftPilot is a course project that is kept to open-source
standards. Bug reports, questions and pull requests are welcome.

## Setup

```powershell
uv venv --python 3.13
.\.venv\Scripts\Activate.ps1      # Linux or macOS: source .venv/bin/activate
uv pip install -e ".[dev]"
pre-commit install
```

Python 3.11 to 3.13 is supported.

## Before you open a pull request

```powershell
ruff check src tests
ruff format --check src tests
pytest
```

The same three commands run in CI (`.github/workflows/ci.yml`) on Ubuntu and Windows with Python
3.11 and 3.13. Optional type check: `mypy`.

The default test suite uses synthetic data with a known answer. It needs no download, no GPU
and no language model. Two pytest markers are reserved for tests that do: `data` (needs the
downloaded datasets) and `llm` (needs a running local Ollama server).

## Rules of the house

1. **No raw data in the repository.** `data/raw/`, `data/interim/` and `data/cache/` are ignored
   by git. Neither dataset states a licence that allows redistribution. If a source file
   changes, update `data/checksums.sha256`.
2. **No hand-typed numbers.** Every figure in the documents comes from `docs/RESULTS.md`, which
   is written by `liftpilot results`. Do not edit that file by hand. If you change the
   pipeline, re-run `liftpilot train x5`, `liftpilot train hillstrom` and `liftpilot results`,
   and update the documents that quote the numbers.
3. **Every profit figure carries its 95% interval.** Negative results are reported, not removed.
4. **Age and gender never become model inputs.** They are audit columns only.
5. **The agent's fences are not optional.** A new tool must declare a privilege level (`read`,
   `propose` or `action`); an `action` tool must refuse to run without a human approval. A
   change to the agent loop, the tools or the guards should come with a test, and
   `liftpilot agent-eval` should be re-run.
6. **Tests are split by topic**: `tests/test_uplift.py` (learners and metrics),
   `tests/test_policy.py` (economics, allocation, replay), `tests/test_engine_agent.py` (engine,
   guards, agent). New behaviour needs a test with a known answer.
7. **Plain English** in code comments and documents. Define a term once. State limits in the
   text.

## Commit messages

Short imperative subject with a type prefix, as in the existing history: `feat:`, `fix:`,
`docs:`, `test:`, `refactor:`, `chore:`.

## Reporting a problem

Open an issue with: what you ran, what you expected, what happened, your operating system and
Python version, and, for agent problems, the relevant lines of `runs/audit.jsonl` (they contain
tool names, arguments and result fingerprints, not customer records).

## Licence

By contributing you agree that your contribution is released under the MIT licence of this
repository.
