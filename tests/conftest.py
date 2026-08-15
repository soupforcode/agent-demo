"""Shared test setup.

Everything in this suite runs **without an API key**. That's the point: it's
what lets CI gate every push, and what lets a student whose free-tier quota ran
out at minute 70 still finish the lab.

What that buys, and what it doesn't
-----------------------------------
These tests prove the tools work, the schema is a shape Gemini will accept, the
service behaves when misconfigured, and the eval harness is wired correctly.
They do **not** prove the agent reasons well — that needs a real model, and it
lives in `make eval`.

Being clear about that distinction is worth more than a green tick. A CI badge
that only ever exercised the plumbing has told you nothing about the agent.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "evals"))


@pytest.fixture(scope="session", autouse=True)
def fresh_database():
    """Rebuild the college database once, before anything runs.

    The data is fixed rather than random, so every assertion below can name
    exact values.
    """
    from college_agent.data.seed import build

    build(quiet=True)
    yield


@pytest.fixture
def client():
    """A test client for the FastAPI app."""
    from fastapi.testclient import TestClient

    from college_agent.api import app

    return TestClient(app)
