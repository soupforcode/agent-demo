"""LAB 3, PART 3 — Break your own agent on purpose.

    python labs/lab3_eval/03_break_it.py

A number on its own means nothing. "7 out of 10" — is that good? You have no
idea, and neither does anyone reading your slide.

An eval suite becomes useful the moment it can *detect a regression*. So the
honest way to find out whether yours works is to damage the agent deliberately
and check that the score moves. If you break it and the number doesn't budge,
your suite is decoration.

This runs four agents against the same cases:

    baseline      the real thing
    no lookups    the instruction to check records first, removed
    no tools      the fee and exam tools, taken away
    lazy prompt   instructions replaced with one vague sentence

Watch which failures each one produces. They are not the same failures, and
that's the interesting part.

A warning about quota
---------------------
Four agents × ten cases is forty runs, each making several model calls. On a
free tier that is a meaningful chunk of your daily allowance. `SAMPLE` below
limits it to the four smoke cases by default — raise it only if you have quota
to spend.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "evals"))

from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

from cases import CASES  # noqa: E402
from college_agent.agent import INSTRUCTIONS, build_triage_agent, run_triage  # noqa: E402
from college_agent.config import MissingAPIKeyError, check_api_key, describe_config  # noqa: E402
from college_agent.guardrails import TicketBlocked  # noqa: E402
from college_agent.tools import (  # noqa: E402
    check_hostel_status,
    create_ticket,
    lookup_student,
    search_policy,
)

console = Console()

# Keep the free tier alive. Set to None to run every case.
SAMPLE = "smoke"


def variants() -> dict[str, object]:
    """Four agents: one healthy, three damaged in specific ways."""
    return {
        # The real thing.
        "baseline": build_triage_agent(),
        # Removes the instruction telling it to look up records before
        # deciding. Everything else identical. Expect: it starts guessing, and
        # the guesses often *sound* fine.
        "no lookups": build_triage_agent(
            instructions=[
                i
                for i in INSTRUCTIONS
                if "look the student up first" not in i and "Check the records before" not in i
            ]
        ),
        # Takes away the fee and exam tools. It now physically cannot
        # distinguish a fee block from an attendance block. Expect: confident
        # nonsense rather than "I don't know".
        "no tools": build_triage_agent(
            tools=[lookup_student, check_hostel_status, search_policy, create_ticket]
        ),
        # The prompt someone writes in thirty seconds.
        "lazy prompt": build_triage_agent(
            instructions=["You are a helpful assistant for a college. Triage this ticket."]
        ),
    }


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

    cases = [c for c in CASES if SAMPLE is None or SAMPLE in c.tags]

    console.print(f"\n[bold]Breaking it on purpose[/bold]  [dim]{describe_config()}[/dim]")
    console.print(f"[dim]{len(cases)} cases x {len(variants())} variants[/dim]\n")

    table = Table(expand=True)
    table.add_column("Case", ratio=3)
    for label in variants():
        table.add_column(label, ratio=2, justify="center")

    scores = dict.fromkeys(variants(), 0)
    built = variants()

    for case in cases:
        row = [case.name]
        for label, agent in built.items():
            with console.status(f"[dim]{label}: {case.name}…[/dim]"):
                try:
                    result = run_triage(agent, case.ticket)
                    ok = (
                        result.department == case.expected_department
                        and result.needs_human == case.expected_needs_human
                    )
                    scores[label] += ok
                    row.append("[green]ok[/green]" if ok else f"[red]{result.department[:9]}[/red]")
                except TicketBlocked:
                    # Refused pre-model. Correct whenever the case expects
                    # escalation — and no variant can degrade it, which is
                    # rather the point of a guardrail.
                    scores[label] += case.expected_needs_human
                    row.append("[magenta]blocked[/magenta]")
                except Exception as exc:  # noqa: BLE001
                    row.append(f"[red]{type(exc).__name__[:9]}[/red]")
        table.add_row(*row)

    table.add_section()
    table.add_row(
        "[bold]score[/bold]",
        *[f"[bold]{scores[label]}/{len(cases)}[/bold]" for label in built],
    )
    console.print(table)

    baseline = scores["baseline"]
    worst = min(scores.values())

    console.print()
    if baseline > worst:
        console.print(
            f"  [green]Your eval suite works.[/green] It caught the damage: "
            f"baseline {baseline}/{len(cases)}, worst variant {worst}/{len(cases)}.\n"
        )
    else:
        console.print(
            "  [yellow]The suite did not distinguish the broken agents from the "
            "good one.[/yellow]\n"
            "  Either your cases are too easy, or too few, or the model is "
            "compensating\n  for the damage. Any of those is worth knowing — and "
            "worth fixing before\n  you trust a green run.\n"
        )

    console.print(
        "[dim]"
        "The point isn't the numbers, it's that they [/dim][bold]moved[/bold][dim]. A suite that\n"
        "can't detect a deliberately broken agent won't detect an accidentally\n"
        "broken one either — and the accidental kind is the one that reaches\n"
        "your users.\n"
        "\n"
        "Look at *how* each variant fails, not just how often:\n"
        "  · 'no lookups' invents plausible answers. The prose still reads well.\n"
        "  · 'no tools' cannot possibly know the answer, and mostly does not say\n"
        "    so — it commits to a guess instead. This is the failure mode that\n"
        "    should worry you most in production.\n"
        "  · 'lazy prompt' is inconsistent rather than wrong: run it twice and\n"
        "    it disagrees with itself.\n"
        "\n"
        "Try this:\n"
        "  · Set SAMPLE = None to run all ten cases and see the gaps widen.\n"
        "  · Add a fifth variant that damages something you care about — drop\n"
        "    the escalation instruction, or halve the tool_call_limit — and see\n"
        "    whether your suite notices.\n"
        "\n"
        "Next: lab 4 — ship it.[/dim]\n"
    )


if __name__ == "__main__":
    main()
