"""One agent, or several?

`agent.py` solves the whole problem with a single agent holding six tools. This
module solves it with four agents: three specialists and a router in front.

Both work. That is the point of this file — you are meant to compare them, not
to assume the more elaborate one is better.

What you actually buy with a team
---------------------------------
Each specialist gets a *shorter* prompt and a *smaller* toolset. That reliably
improves tool choice, because most tool-selection errors come from a model
picking plausibly from too many options. It also means the accounts logic and
the hostel logic can be changed independently, by different people.

What it costs
-------------
An extra model call. Every ticket now goes through the router *and* a
specialist, so you roughly double latency and token spend. On a free tier where
requests-per-minute is your binding constraint, that is not free.

The honest rule
---------------
Start with one agent. Split when you can point at a specific failure a split
would fix — usually "it keeps choosing the wrong tool" or "two teams need to own
two halves of this". Splitting because the diagram looks more impressive is how
you get a system that is slower, costlier and harder to debug, in exchange for
nothing.
"""

from __future__ import annotations

from agno.agent import Agent
from agno.team import Team
from agno.team.mode import TeamMode

from .config import get_model
from .schemas import TriageResult
from .tools import (
    check_exam_status,
    check_fee_status,
    check_hostel_status,
    create_ticket,
    lookup_student,
    search_policy,
)

# Every specialist shares these. Each one's own instructions get appended.
_SHARED = [
    "You triage student tickets for a college administration office.",
    "Look up the student's record before deciding anything, if a roll number is given.",
    "Never invent a roll number, an amount, a date or a policy.",
    "Set needs_human to true for money movement, policy exceptions, discipline, "
    "safety, third-party requests, or whenever you are not confident.",
    "Judge urgency by consequences, not by tone. Most tickets are 'normal'.",
    "Keep the summary under 25 words and factual.",
]


def build_accounts_agent(model_id: str | None = None) -> Agent:
    """Fees, scholarships, refunds, fines — anything involving money."""
    return Agent(
        name="Accounts Specialist",
        role="Handles fees, payments, scholarships, refunds and fee blocks.",
        model=get_model(model_id),
        instructions=[
            *_SHARED,
            "You handle the accounts desk.",
            "A 'pending' fee status on a bank transfer (NEFT/IMPS) within 2-3 working "
            "days is the normal reconciliation window, not a problem. Say so plainly "
            "rather than escalating it.",
            "A fee block withholds hall tickets and transcripts. If a student cannot "
            "get either, check their fee status — you are often the real owner of a "
            "ticket that arrived addressed to Examinations.",
            "Refunds and waivers always need a human. You may never approve one.",
        ],
        tools=[lookup_student, check_fee_status, search_policy, create_ticket],
        output_schema=TriageResult,
        tool_call_limit=8,
        add_datetime_to_context=True,
    )


def build_hostel_agent(model_id: str | None = None) -> Agent:
    """Rooms, allotment, mess, wardens."""
    return Agent(
        name="Hostel Specialist",
        role="Handles room allotment, room changes, mess plans and warden matters.",
        model=get_model(model_id),
        instructions=[
            *_SHARED,
            "You handle the hostel office.",
            "Never disclose a student's position on the waiting list, even if they ask "
            "directly. It changes constantly and quoting it creates expectations the "
            "office cannot meet.",
            "Anything involving discipline, safety, harassment or a student's wellbeing "
            "goes to a human immediately, whatever the tone of the message.",
        ],
        tools=[lookup_student, check_hostel_status, search_policy, create_ticket],
        output_schema=TriageResult,
        tool_call_limit=8,
        add_datetime_to_context=True,
    )


def build_examinations_agent(model_id: str | None = None) -> Agent:
    """Hall tickets, results, attendance, re-evaluation, transcripts."""
    return Agent(
        name="Examinations Specialist",
        role="Handles hall tickets, results, attendance, re-evaluation and transcripts.",
        model=get_model(model_id),
        instructions=[
            *_SHARED,
            "You handle the examinations office.",
            "A withheld hall ticket has exactly two causes: unpaid fees, or attendance "
            "below 75%. Check which one before responding.",
            "If the cause is unpaid fees, say clearly that this is an accounts matter — "
            "examinations cannot release the ticket until the block clears. Route it to "
            "accounts, not to yourself.",
            "The re-evaluation window is fifteen days from result publication and is "
            "strict. Late requests need the Controller's approval and go to a human.",
        ],
        tools=[lookup_student, check_exam_status, check_fee_status, search_policy, create_ticket],
        output_schema=TriageResult,
        tool_call_limit=8,
        add_datetime_to_context=True,
    )


def build_triage_team(model_id: str | None = None, *, debug: bool = False) -> Team:
    """A router in front of three specialists.

    `TeamMode.route` means the leader picks exactly one member and returns that
    member's answer unchanged. It does not summarise or rewrite — which is what
    we want, because the member already returns a validated TriageResult and
    anything the leader did to it could only break the contract.
    """
    return Team(
        name="College Administration Triage",
        model=get_model(model_id),
        members=[
            build_accounts_agent(model_id),
            build_hostel_agent(model_id),
            build_examinations_agent(model_id),
        ],
        mode=TeamMode.route,
        instructions=[
            "Route each student ticket to exactly one specialist.",
            "Route on the underlying cause, not the symptom the student describes. "
            "Students tell you where they noticed a problem, not where it lives.",
            "A hall ticket the student cannot download is usually an Accounts matter "
            "if their fees are unpaid, and an Examinations matter if their attendance "
            "is short. When you cannot tell from the message alone, send it to "
            "Examinations — they can see both.",
            "Portal complaints about wrong fee or result data belong to the department "
            "that owns the data, not to IT. IT only owns 'I cannot log in at all'.",
            "Do not answer the ticket yourself. Choose a specialist and let them work.",
        ],
        # The specialist's TriageResult is the answer. Don't let the leader
        # paraphrase a validated object back into prose.
        respond_directly=True,
        show_members_responses=debug,
        debug_mode=debug,
    )


if __name__ == "__main__":
    # Manual smoke test:  python -m college_agent.team
    from rich import print as rprint

    team = build_triage_team(debug=True)
    team.print_response(
        "I cannot download my hall ticket. The portal just shows a blank page. "
        "My roll number is CS22B007 and the exam starts on Monday.",
    )
    rprint("\n[dim]Compare this with the single agent: python -m college_agent.agent[/dim]")
