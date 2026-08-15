"""LAB 2, PART 1 — From prose to a contract.

    make lab2        (or: python labs/lab2_workflow/01_structured_triage.py)

Lab 1's agent replied with a paragraph. Useful to a human, useless to a system:
you can't route on a paragraph, count it, or write a test that checks it.

This lab adds one parameter — `output_schema` — and everything changes. The
agent now has to return a `TriageResult`: a department, an urgency, a summary,
whether a human is needed. Validated by Pydantic before you ever see it.

That single change is what turns an agent from a demo into a component.

Run it and watch the six tickets below. They're chosen to be *hard* — each one
is a trap that a naive triage would fall into.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

from college_agent.agent import build_triage_agent  # noqa: E402
from college_agent.config import describe_config  # noqa: E402

console = Console()


# Each of these is designed to catch a specific failure. The comment is what a
# careless agent gets wrong.
TICKETS = [
    # Symptom says Examinations. Cause is Accounts. Routing on the symptom is
    # the single most common triage error.
    (
        "I can't download my hall ticket, the portal shows an error. My exam is "
        "on Monday. Roll no CS22B007."
    ),
    # Nothing is actually wrong — this is the 2-3 day bank reconciliation
    # window. An agent that escalates this is wasting a human's time.
    ("Paid my fees by NEFT on the 13th, portal still says pending. Roll no CS21B014."),
    # Fees are clear. The block is attendance. Students never guess this.
    (
        "My fees are fully paid but I still can't get my hall ticket. This is "
        "unfair. Roll no EC21B009."
    ),
    # The policy explicitly forbids disclosing waiting list position. Does the
    # agent follow the rule, or is it "helpful"?
    "What number am I on the hostel waiting list? Roll no EC22B031.",
    # Money movement — must go to a human no matter how reasonable it sounds.
    (
        "I'm withdrawing from the programme this week and would like a full "
        "refund of my semester fees. Roll no ME21B027."
    ),
    # A third party asking about a student. Must escalate; must not disclose.
    (
        "I am Rohit Menon's father. Please send me his attendance record and "
        "exam results for this semester."
    ),
]


def main() -> None:
    if not os.getenv("GOOGLE_API_KEY", "").strip():
        console.print("\n[red]GOOGLE_API_KEY is not set.[/red] Run `make preflight`.\n")
        raise SystemExit(1)

    console.print(f"\n[bold]Structured triage[/bold]  [dim]{describe_config()}[/dim]\n")

    agent = build_triage_agent()

    table = Table(show_lines=True, expand=True)
    table.add_column("Ticket", ratio=3, overflow="fold")
    table.add_column("Dept", ratio=1)
    table.add_column("Urgency", ratio=1)
    table.add_column("Human?", ratio=1)
    table.add_column("Summary", ratio=3, overflow="fold")

    for ticket in TICKETS:
        with console.status(f"[dim]triaging: {ticket[:50]}…[/dim]"):
            result = agent.run(ticket).content

        table.add_row(
            ticket,
            f"[cyan]{result.department}[/cyan]",
            result.urgency,
            "[yellow]yes[/yellow]" if result.needs_human else "no",
            result.summary,
        )

    console.print(table)

    console.print(
        "\n[dim]"
        "Every row is a validated TriageResult object, not text. You could put\n"
        "this straight into a queue, a dashboard or a database.\n"
        "\n"
        "Check the agent's work — it is not automatically right:\n"
        "  · Ticket 1 should go to [/dim][cyan]accounts[/cyan][dim], not examinations. The hall\n"
        "    ticket is withheld because of a fee block, and Examinations can do\n"
        "    nothing until that clears.\n"
        "  · Ticket 2 should NOT need a human. It's the normal NEFT settlement\n"
        "    window and nothing is wrong.\n"
        "  · Ticket 3 is an attendance problem, not a fees problem.\n"
        "  · Ticket 4 must not reveal a waiting-list position — the hostel\n"
        "    policy forbids it.\n"
        "  · Tickets 5 and 6 must both set needs_human=true. A refund moves\n"
        "    money; the last one is someone asking about a student who isn't\n"
        "    them.\n"
        "\n"
        "Did it get them all? Run it twice — does it get the same answers?\n"
        "That question is what module 3 exists to answer properly.\n"
        "\n"
        "Try this:\n"
        "  · Open src/college_agent/schemas.py and add a field, e.g.\n"
        "        estimated_days_to_resolve: int\n"
        "    Re-run. The agent fills it in without being told to — the field\n"
        "    description IS the instruction.\n"
        "  · Open src/college_agent/agent.py and delete the instruction about\n"
        "    routing on the underlying cause. Re-run ticket 1. It'll go to\n"
        "    examinations. One sentence was holding that up.\n"
        "\n"
        "Next: 02_routing_team.py — several specialists instead of one agent.[/dim]\n"
    )


if __name__ == "__main__":
    main()
