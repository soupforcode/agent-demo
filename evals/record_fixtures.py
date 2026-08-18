#!/usr/bin/env python3
"""Record real agent runs so the reliability evals can run without an API key.

    python evals/record_fixtures.py

Needs a key to record. Once recorded, nothing else does.

Why this exists
---------------
`ReliabilityEval` inspects a `RunOutput` — which tools were called, with what
arguments. A `RunOutput` is just data, so it serialises. Record one now, assert
against it forever, for free.

That gets you a genuinely useful CI check: it catches the case where a prompt
edit stops the agent looking up a student's record. Not as good as running the
real agent, but free and deterministic, which means it can gate every push
rather than every release.

The honest caveat: a fixture is a snapshot. It tells you what the agent did on
the day you recorded it, not what it does now. Re-record when you change the
agent — and don't mistake a green fixture run for evidence that today's agent
works. That's what `make eval` is for.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "evals"))

from rich.console import Console

from cases import CASES
from college_agent.agent import build_triage_agent
from college_agent.config import MissingAPIKeyError, check_api_key, describe_config

console = Console()
FIXTURE_DIR = Path(__file__).parent / "fixtures"


def main() -> int:
    # Recording fixtures means calling the real provider, so a key is
    # required — but which key depends on the provider config.py selected.
    try:
        check_api_key()
    except MissingAPIKeyError as exc:
        console.print(f"\n[red]{exc}[/red]")
        console.print("[dim]Recording fixtures needs a real key — that is the point of it.[/dim]\n")
        return 1

    FIXTURE_DIR.mkdir(exist_ok=True)
    agent = build_triage_agent()

    console.print(f"\n[bold]Recording fixtures[/bold]  [dim]{describe_config()}[/dim]\n")

    recorded = 0
    for case in CASES:
        if not case.expected_tools:
            continue  # nothing to assert about, so nothing worth recording

        with console.status(f"[dim]{case.name}…[/dim]"):
            response = agent.run(case.ticket)

        path = FIXTURE_DIR / f"{case.name}.json"
        path.write_text(json.dumps(response.to_dict(), indent=2, default=str), encoding="utf-8")

        tools = [t.tool_name for t in (response.tools or [])]
        console.print(
            f"  [green]saved[/green] {path.name}  [dim]{', '.join(tools) or '(no tools)'}[/dim]"
        )
        recorded += 1

    console.print(
        f"\n[bold]{recorded} fixtures written to {FIXTURE_DIR.relative_to(REPO_ROOT)}[/bold]"
    )
    console.print(
        "\n[dim]These are a snapshot of today's behaviour. Re-record after you change\n"
        "the agent, and remember a green fixture run is not evidence that the\n"
        "current agent works — that's what `make eval` is for.[/dim]\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
