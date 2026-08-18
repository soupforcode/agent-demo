"""LAB 3, PART 1 — Did it reason, or did it get lucky?

    make lab3        (or: python labs/lab3_eval/01_reliability.py)

Start here, before any talk of accuracy or judges, because this check is free,
instant, deterministic, and catches a failure that accuracy scoring misses
completely.

The failure it catches
----------------------
An agent can produce the right answer without doing any work. Ask it about a
hall ticket and "accounts" is a decent guess before looking anything up. It
scores a point. Then you reword the ticket slightly and it falls apart, because
it was never reasoning — it was pattern-matching on your phrasing.

Reliability evaluation checks the *path*, not the answer: did it actually call
the tools that this question requires? You cannot detect this by reading
outputs, which is exactly why it gets missed.

No judge, no cost
-----------------
This is plain assertion on what happened. No second model, no API call, no
subjective scoring. Which means it's the check you can afford to run on every
commit.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "evals"))

from agno.eval.reliability import ReliabilityEval  # noqa: E402
from rich.console import Console  # noqa: E402

from cases import CASES  # noqa: E402
from college_agent.agent import build_triage_agent  # noqa: E402
from college_agent.config import MissingAPIKeyError, check_api_key, describe_config  # noqa: E402

console = Console()


def main() -> None:
    # Not `os.getenv("GOOGLE_API_KEY")`. That names one provider, and this
    # repo supports two — a student with only an OpenAI key would be refused
    # by a lab that was about to work fine. check_api_key() asks config.py,
    # which knows which provider is selected and what its variable is called.
    try:
        check_api_key()
    except MissingAPIKeyError as exc:
        console.print(f"\n[red]{exc}[/red]")
        raise SystemExit(1) from None

    console.print(
        f"\n[bold]Reliability: did it look things up?[/bold]  [dim]{describe_config()}[/dim]\n"
    )

    agent = build_triage_agent()

    # Only the cases that require a specific lookup. A case with no required
    # tools has nothing to assert here.
    checked = [c for c in CASES if c.expected_tools]
    passed = 0

    for case in checked:
        with console.status(f"[dim]{case.name}…[/dim]"):
            response = agent.run(case.ticket)

        evaluation = ReliabilityEval(
            name=case.name,
            agent_response=response,
            expected_tool_calls=list(case.expected_tools),
            # The agent may call more than the minimum — that's fine, often
            # sensible. We're checking it didn't call *fewer*.
            allow_additional_tool_calls=True,
            telemetry=False,
        )
        result = evaluation.run(print_results=False)

        called = [t.tool_name for t in (response.tools or [])]
        ok = result.eval_status == "PASSED"
        passed += ok

        console.print(f"  {'[green]PASS[/green]' if ok else '[red]FAIL[/red]'}  {case.name}")
        console.print(f"        [dim]required: {', '.join(case.expected_tools)}[/dim]")
        console.print(f"        [dim]called:   {', '.join(called) or '(nothing)'}[/dim]")
        if not ok:
            console.print(f"        [red]missing:  {', '.join(result.missing_tool_calls)}[/red]")

    console.print(f"\n[bold]{passed}/{len(checked)} passed[/bold]\n")

    console.print(
        "[dim]"
        "Read the 'called' lines even for the passes. Is the agent doing more\n"
        "work than it needs to? Every extra tool call is latency you're paying\n"
        "for and free-tier quota you're spending.\n"
        "\n"
        "Try this:\n"
        "  · Open src/college_agent/agent.py and delete the instruction that\n"
        "    starts 'If the ticket mentions a roll number, look the student up\n"
        "    first'. Re-run. Watch tools disappear from the 'called' lines —\n"
        "    and notice the final answers often still look plausible. That gap\n"
        "    between 'looks right' and 'is right' is the whole reason this\n"
        "    check exists.\n"
        "\n"
        "Next: 02_accuracy.py — was the answer actually correct?[/dim]\n"
    )


if __name__ == "__main__":
    main()
