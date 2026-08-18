"""The triage agent — step 2: a contract instead of prose.

One parameter changed since step 1:

    output_schema=TriageResult

That's it. The agent must now return a validated object — a department, an
urgency, whether a human is needed — instead of a paragraph.

It is a bigger change than it looks. Prose can be read; an object can be
routed, counted, stored and tested. This is the line between a demo and a
component.

**And watch what it does not fix.** The agent still has no tools, so it still
cannot look up a single fact about CS22B007. What you get back now is a
beautifully structured, fully validated, entirely invented answer.

That is worth sitting with for a moment. Structure buys you parseability. It
does not buy you truth, and it makes a wrong answer look considerably more
authoritative than prose did.

Tools are step 3.
"""

from __future__ import annotations

from agno.agent import Agent

from .config import get_model
from .schemas import TriageResult

INSTRUCTIONS = [
    "You triage incoming student tickets for a college administration office.",
    "Your job is to decide who should handle a ticket and how urgently. "
    "You do not resolve the ticket yourself and you do not reply to the student.",
    "Never invent a roll number, an amount, a date or a policy. If you could not "
    "establish the roll number, leave student_id empty and say so in the "
    "suggested action.",
    "Set needs_human to true for anything involving money movement (refunds, "
    "waivers, disputed payments), policy exceptions, discipline, safety or "
    "wellbeing, requests about a student other than the sender, or the release "
    "of original documents.",
    "Also set needs_human to true when you are simply not confident. Uncertainty "
    "is the signal, not something to work around.",
    "Judge urgency by consequences, not by tone. Reserve 'critical' for a "
    "deadline being missed right now. Most tickets are 'normal'.",
    "Keep the summary under 25 words and factual — it is read by someone with "
    "thirty seconds and forty tickets.",
]


def build_triage_agent(model_id: str | None = None, *, debug: bool = False) -> Agent:
    """Build the triage agent.

    Args:
        model_id: Override the model. Defaults to the provider's cheapest.
        debug: Print every message, response and token count.
    """
    return Agent(
        name="College Triage Agent",
        model=get_model(model_id),
        instructions=INSTRUCTIONS,
        # The contract. Without this the agent returns prose, and prose can't be
        # routed, counted or tested.
        output_schema=TriageResult,
        add_datetime_to_context=True,
        debug_mode=debug,
    )


def triage(message: str, student_id: str = "") -> TriageResult:
    """Triage one ticket and return the structured decision."""
    prompt = message if not student_id else f"[Ticket from {student_id}]\n\n{message}"
    return build_triage_agent().run(prompt).content


if __name__ == "__main__":
    from rich import print as rprint

    from .config import describe_config

    rprint(f"[dim]{describe_config()}[/dim]\n")

    result = triage(
        "I can't download my hall ticket, the portal shows an error. "
        "My exam is on Monday. Roll no CS22B007."
    )
    rprint(result)

    rprint(
        "\n[dim]"
        "That is a real Python object now — validated by Pydantic, with a\n"
        "department you could route on and a needs_human flag you could act on.\n"
        "\n"
        "It is also, almost certainly, wrong.\n"
        "\n"
        "CS22B007 is fee-blocked. The hall ticket is withheld by Accounts, not\n"
        "Examinations. The agent has no way to know that — it has no tools —\n"
        "so it guessed from the words in the ticket, and the schema wrapped\n"
        "that guess in something that looks authoritative.\n"
        "\n"
        "Run it twice. Does it even agree with itself?\n"
        "\n"
        "Next:  git switch step-3-tools[/dim]\n"
    )
