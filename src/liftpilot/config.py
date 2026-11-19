"""Project paths. Everything is relative to the repository root, or to the
directory named by the ``LIFTPILOT_HOME`` environment variable."""

from __future__ import annotations

import os
from pathlib import Path


def root() -> Path:
    env = os.environ.get("LIFTPILOT_HOME")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    return Path.cwd()


def raw_dir(dataset: str) -> Path:
    return root() / "data" / "raw" / dataset


def interim_dir() -> Path:
    return root() / "data" / "interim"


def artifacts_dir(dataset: str) -> Path:
    return root() / "artifacts" / dataset


def cache_dir() -> Path:
    return root() / "data" / "cache"


def runs_dir() -> Path:
    return root() / "runs"
