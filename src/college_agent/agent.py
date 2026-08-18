"""The triage agent — step 1.

Three things, and that's a working agent:

    model         the reasoning engine   -> config.get_model()
    instructions  how it should decide   -> INSTRUCTIONS
    (that's it)

There are no tools yet, so it cannot look anything up. There is no schema yet,
so it answers in prose. Both of those are deliberate: you're going to add them
one at a time and see exactly what each one buys.

Run it:

    python -m college_agent.agent
"""

from __future__ import annotations

from agno.agent import Agent

from .config import get_model

# --------------------------------------------------------------------------
# Instructions
# --------------------------------------------------------------------------
# Notice what these are and aren't. They are not a description of the college.
# They are a *decision procedure*: how to decide, and when to stop and ask a
# human.
#
# The most common mistake when writing instructions is describing the domain
# instead of the behaviour. The model already knows what a hostel is. What it
# doesn't know is that you'd rather it escalated than guessed.
INSTRUCTIONS = [
    "You triage incoming student tickets for a college administration office.",
    "Your job is to decide who should handle a ticket and how urgently. "
    "You do not resolve the ticket yourself and you do not reply to the student.",
    "The departments are: accounts, hostel, examinations, admissions, it_support.",
    "Judge urgency by consequences, not by tone. Capital letters are not an "
    "emergency; a visa interview on Thursday is. Most tickets are not urgent.",
    "Say when you are not confident. Escalating unnecessarily costs a few "
    "minutes of someone's time; not escalating can harm a student. Those are "
    "not equivalent, so do not treat them as a balanced trade-off.",
]


def build_triage_agent(model_id: str | None = None, *, debug: bool = False) -> Agent:
    """Build the triage agent.

    Args:
        model_id: Override the model. Defaults to the provider's cheapest.
        debug: Print every message sent to the model, the raw response and the
            token counts. Turn this on the first time anything surprises you —
            it is the fastest way to see what your agent actually did, as
            opposed to what you assumed it did.
    """
    return Agent(
        name="College Triage Agent",
        model=get_model(model_id),
        instructions=INSTRUCTIONS,
        # Gives the model today's date. Useful the moment any deadline is
        # mentioned, and free.
        add_datetime_to_context=True,
        markdown=True,
        debug_mode=debug,
    )


if __name__ == "__main__":
    from rich import print as rprint

    from .config import describe_config

    rprint(f"[dim]{describe_config()}[/dim]\n")

    build_triage_agent().print_response(
        "I can't download my hall ticket, the portal shows an error. "
        "My exam is on Monday. Roll no CS22B007.",
        stream=True,
    )

    rprint(
        "\n[dim]"
        "Read that answer carefully before you're impressed by it.\n"
        "\n"
        "It sounds confident. It named a department. But the agent has no way\n"
        "to look up CS22B007 — no database, no tools — so whatever it told you\n"
        "about that student, it made up.\n"
        "\n"
        "Two separate problems, and step 2 and step 3 fix one each:\n"
        "  · the answer is prose, so no system can use it   -> step 2\n"
        "  · the answer is invented, so nobody should trust it -> step 3\n"
        "\n"
        "Next:  git switch step-2-structured[/dim]\n"
    )
