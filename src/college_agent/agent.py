"""The triage agent.

Four things make an agent, and all four are visible in `build_triage_agent`:

    model        the reasoning engine          -> config.get_model()
    instructions who it is and how it decides  -> INSTRUCTIONS
    tools        what it can actually do       -> tools.TRIAGE_TOOLS
    output       the contract it must fill in  -> schemas.TriageResult

Everything else Agno offers — memory, sessions, knowledge, teams — is built on
top of those four. If you understand this file, you understand agents.
"""

from __future__ import annotations

from agno.agent import Agent

from .config import get_model
from .guardrails import default_guardrails, enforce
from .schemas import TriageResult
from .tools import TRIAGE_TOOLS

# --------------------------------------------------------------------------
# Instructions
# --------------------------------------------------------------------------
# Notice what these are and aren't. They are not a description of the college.
# They are a *decision procedure*: what to do first, what to check, when to
# stop and ask a human.
#
# The most common mistake when writing instructions is describing the domain
# instead of the behaviour. The model already knows what a hostel is. What it
# doesn't know is that you'd rather it escalated than guessed.
INSTRUCTIONS = [
    "You triage incoming student tickets for a college administration office.",
    "Your job is to decide who should handle a ticket and how urgently. "
    "You do not resolve the ticket yourself and you do not reply to the student.",
    # --- Order of operations ---
    "If the ticket mentions a roll number, look the student up first. Their actual "
    "fee, hostel and examination records usually settle the question faster than "
    "re-reading the message does.",
    "Check the records before you check the policy. A student who says their fees "
    "are pending may simply be inside the bank reconciliation window — the fee "
    "record will tell you, the policy will not.",
    "When the answer depends on a rule, a deadline or an amount, search the policy "
    "documents. Do not answer policy questions from memory.",
    # --- The trap this domain is full of ---
    "Route on the underlying cause, not the symptom the student describes. Students "
    "report where they noticed a problem, not where it lives. A withheld hall ticket "
    "caused by unpaid fees is an accounts ticket, not an examinations ticket.",
    # --- Honesty ---
    "Never invent a roll number, an amount, a date or a policy. If you could not "
    "establish the roll number, leave student_id empty and say so in the suggested "
    "action.",
    # --- Escalation ---
    "Set needs_human to true for anything involving money movement (refunds, "
    "waivers, disputed payments), policy exceptions, discipline, safety or "
    "wellbeing, requests about a student other than the sender, or the release of "
    "original documents.",
    "Also set needs_human to true when you are simply not confident. Uncertainty is "
    "the signal, not something to work around. Escalating unnecessarily costs a few "
    "minutes; not escalating can harm a student. Those are not equivalent.",
    # --- Urgency discipline ---
    "Judge urgency by consequences, not by tone. Capital letters are not an "
    "emergency; a visa interview on Thursday is. Reserve 'critical' for a deadline "
    "being missed right now. Most tickets are 'normal'.",
    # --- Output ---
    "Keep the summary under 25 words and factual — it is read by someone with "
    "thirty seconds and forty tickets.",
]


def build_triage_agent(
    model_id: str | None = None,
    *,
    instructions: list[str] | None = None,
    tools: list | None = None,
    guardrails: bool = True,
    debug: bool = False,
    name: str = "College Triage Agent",
) -> Agent:
    """Build the triage agent.

    The arguments exist so module 3 can *break* it deliberately — swap in
    weaker instructions or remove a tool, then watch the eval scores move. An
    agent you can't degrade on purpose is an agent you can't measure.

    Args:
        model_id: Override the model. Module 3 uses this to compare a cheap
            model against a stronger one.
        instructions: Override the decision procedure. Defaults to INSTRUCTIONS.
        tools: Override the toolset. Defaults to all six.
        guardrails: Run the pre-flight checks in `guardrails.py` — third-party
            record requests and personal identifiers. Set False to see what the
            instructions alone catch, which is the point of the exercise: an
            instruction is advice, a guardrail is a rule.
        debug: Print the messages sent to the model, the raw response, every
            tool call and the token counts. Turn this on the first time
            anything surprises you — it is the fastest way to understand what
            your agent actually did, as opposed to what you assumed it did.
        name: Shows up in traces and in the AgentOS UI.
    """
    return Agent(
        name=name,
        model=get_model(model_id),
        instructions=instructions if instructions is not None else INSTRUCTIONS,
        tools=tools if tools is not None else TRIAGE_TOOLS,
        # The contract. Without this the agent returns prose, and prose can't be
        # routed, counted or tested.
        output_schema=TriageResult,
        # Checks that run BEFORE the model does — so they cost nothing, can't be
        # argued out of, and behave identically on the thousandth ticket. The
        # instructions above also ask for this behaviour; the difference is that
        # instructions are advice and these are not.
        pre_hooks=default_guardrails() if guardrails else None,
        # A hard stop. Without a limit a confused agent will happily call tools
        # until your free-tier quota is gone. Six tools, a couple of calls each,
        # plus slack — ten is generous for this task.
        tool_call_limit=10,
        # Gives the model today's date, so "within fifteen days of publication"
        # is something it can actually evaluate.
        add_datetime_to_context=True,
        debug_mode=debug,
    )


# A ready-built agent for the labs and the API to import. Built lazily so that
# merely importing this module doesn't demand an API key — the tests need to
# import it without one.
_default_agent: Agent | None = None


def triage_agent() -> Agent:
    """The shared triage agent, built on first use."""
    global _default_agent
    if _default_agent is None:
        _default_agent = build_triage_agent()
    return _default_agent


def triage(message: str, student_id: str = "") -> TriageResult:
    """Triage one ticket and return the structured decision.

    This is the function the API, the labs and the evals all go through.

    Args:
        message: What the student wrote.
        student_id: Roll number, if the portal already knows who is asking.
    """
    prompt = message if not student_id else f"[Ticket from {student_id}]\n\n{message}"

    # Check before dispatching. The agent has the same guardrails on its
    # pre_hooks, but Agno swallows those into a RunOutput that is
    # indistinguishable from a model failure — so the service layer checks
    # explicitly to get an exception it can actually act on. See
    # guardrails.enforce for the full reasoning.
    enforce(prompt)

    result = triage_agent().run(prompt).content

    # A failed run (bad key, rate limit, refused schema) comes back with the
    # error message as a plain string rather than a TriageResult. Returning
    # that would sail past this function and blow up in FastAPI's response
    # validation as a 500 - a server error for what is usually a provider
    # problem. Fail here instead, where the caller can classify it.
    if not isinstance(result, TriageResult):
        raise RuntimeError(f"The agent did not return a TriageResult: {str(result)[:300]}")

    return result


if __name__ == "__main__":
    # A quick manual smoke test:  python -m college_agent.agent
    from rich import print as rprint

    from .config import describe_config

    rprint(f"[dim]{describe_config()}[/dim]\n")
    rprint(
        triage(
            "I paid my semester fees by NEFT on the 13th but the portal still "
            "shows pending and I'm worried about my hall ticket. Roll no CS21B014."
        )
    )
