"""LAB 2, PART 2 — One agent, or several?

    python labs/lab2_workflow/02_routing_team.py

Same problem, different shape: a router in front of three specialists
(accounts, hostel, examinations) instead of one agent holding every tool.

This lab is a comparison, not an upgrade. Run both and judge for yourself.

What a team buys you
--------------------
Each specialist has a shorter prompt and fewer tools. Most tool-selection
mistakes come from a model choosing plausibly among too many options, so
narrowing the set genuinely helps. It also means the fee logic and the hostel
logic can be owned and changed by different people.

What it costs
-------------
An extra model call per ticket — the router runs, *then* a specialist runs. You
roughly double latency and token spend. On a free tier where requests-per-minute
is the binding constraint, that is not free.

The rule worth remembering
--------------------------
Start with one agent. Split when you can name the failure a split would fix.
Splitting because the architecture diagram looks more serious gives you a
system that is slower, dearer and harder to debug, in exchange for nothing.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rich.console import Console  # noqa: E402

from college_agent.agent import build_triage_agent, run_triage  # noqa: E402
from college_agent.config import MissingAPIKeyError, check_api_key, describe_config  # noqa: E402
from college_agent.team import build_triage_team  # noqa: E402

console = Console()

TICKET = (
    "I can't download my hall ticket, the portal shows an error. My exam is on "
    "Monday and I'm panicking. Roll no CS22B007."
)


def show(label: str, result, seconds: float) -> None:
    console.print(f"\n[bold]{label}[/bold]  [dim]{seconds:.1f}s[/dim]")
    console.print(f"  department   [cyan]{result.department}[/cyan]")
    console.print(f"  urgency      {result.urgency}")
    console.print(f"  needs human  {'[yellow]yes[/yellow]' if result.needs_human else 'no'}")
    console.print(f"  summary      {result.summary}")
    console.print(f"  action       {result.suggested_action}")


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

    console.print(f"\n[bold]One agent vs a team[/bold]  [dim]{describe_config()}[/dim]")
    console.print(f"\n[bold]Ticket:[/bold] {TICKET}")

    # --- one agent, six tools --------------------------------------------
    agent = build_triage_agent()
    start = time.perf_counter()
    single = run_triage(agent, TICKET)
    single_time = time.perf_counter() - start
    show("Single agent", single, single_time)

    # --- router + three specialists --------------------------------------
    team = build_triage_team()
    start = time.perf_counter()
    # run_triage takes a Team just as happily as an Agent, and applies the
    # guardrails at the call site — the specialists have none of their own.
    routed = run_triage(team, TICKET)
    team_time = time.perf_counter() - start
    show("Routing team", routed, team_time)

    # --- the comparison that matters -------------------------------------
    agreed = single.department == routed.department
    console.print(
        f"\n[bold]Same department?[/bold] "
        f"{'[green]yes[/green]' if agreed else '[yellow]no — worth investigating[/yellow]'}"
        f"   [dim]team took {team_time / max(single_time, 0.01):.1f}x as long[/dim]\n"
    )

    console.print(
        "[dim]"
        "The right answer here is [/dim][cyan]accounts[/cyan][dim]: CS22B007 is fee-blocked, and\n"
        "Examinations cannot release the hall ticket until that clears. Routing on\n"
        "the symptom ('hall ticket') instead of the cause ('fee block') is the\n"
        "mistake both designs can make.\n"
        "\n"
        "Ask yourself honestly: did the team do better, or just cost more?\n"
        "For this problem, one agent with six good tools is usually enough. Teams\n"
        "start paying off when a domain is big enough that one prompt can't hold\n"
        "it — not at six tools.\n"
        "\n"
        "Try this:\n"
        "  · build_triage_team(debug=True) shows you the router's choice and each\n"
        "    member's reasoning. Watch where the decision is actually made.\n"
        "  · Give the router a deliberately vague ticket ('nothing works, please\n"
        "    help') and see which specialist it picks. Then decide whether\n"
        "    that's the behaviour you want, and how you'd fix it.\n"
        "\n"
        "Next: lab 3 — stop eyeballing it and start measuring it.[/dim]\n"
    )


if __name__ == "__main__":
    main()
