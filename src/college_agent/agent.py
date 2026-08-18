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
from pydantic import ValidationError

from .config import get_model
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
    # Read the base-rate line at the end of this block before you tune anything
    # here. Without it the model escalates almost every ticket — correctly, by
    # the letter of the rules above it — and the field stops meaning anything.
    "Set needs_human to true when the ticket ASKS FOR an action a person must "
    "authorise: refunding, waiving or reversing a payment, granting a policy "
    "exception, releasing original documents, or anything touching discipline, "
    "safety or wellbeing.",
    "Judge that by the action requested, not the subject mentioned. A ticket "
    "that merely mentions fees is not money movement. A ticket asking you to "
    "refund fees is.",
    "Also set needs_human to true when the student names a deadline that is "
    "genuinely at risk — an examination in days, a visa appointment, an "
    "application closing. Routine work becomes a person's job when the clock "
    "makes it one, because somebody has to own it.",
    "And set it when you are genuinely uncertain. But a clear, complete answer "
    "from the tools IS confidence: do not escalate merely because the subject "
    "sounds serious, or because a student is upset, or because nothing is "
    "actually wrong and you are surprised by that.",
    "Escalating unnecessarily costs a few minutes; not escalating can harm a "
    "student. Those are not equivalent — but they are not infinitely unequal "
    "either. MOST TICKETS DO NOT NEED A HUMAN. If most of your triages "
    "escalate, the field has stopped carrying information and the queue you are "
    "protecting is now the queue you are flooding.",
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
        # A hard stop. Without a limit a confused agent will happily call tools
        # until your free-tier quota is gone. Six tools, a couple of calls each,
        # plus slack — ten is generous for this task.
        tool_call_limit=10,
        # Gives the model today's date, so "within fifteen days of publication"
        # is something it can actually evaluate.
        add_datetime_to_context=True,
        debug_mode=debug,
    )


def run_triage(agent, ticket: str) -> TriageResult:
    """Run one ticket through `agent` and return a TriageResult. Never a string.

    Use this instead of `agent.run(ticket).content` — everywhere.

    `Agent.run()` does not have the return type you would expect. Its
    `.content` is a `TriageResult` on the happy path, but a plain `str` when
    the model call fails, and sometimes valid JSON that simply hasn't been
    parsed. Code that assumes the happy path gets

        AttributeError: 'str' object has no attribute 'department'

    at some unrelated line, which is a miserable thing to debug.

    So the narrowing happens here, once, and callers get either a real
    TriageResult or a clear exception.

    Args:
        agent: A triage agent, or a Team — both work.
        ticket: What the student wrote.
    """
    result = agent.run(ticket).content

    if isinstance(result, str):
        # Some paths hand back the right JSON as *text* rather than a parsed
        # model — a Team whose leader answers directly is the one you'll meet
        # here. If it validates, take it.
        try:
            return TriageResult.model_validate_json(result)
        except ValidationError:
            pass

    if not isinstance(result, TriageResult):
        raise RuntimeError(f"The agent did not return a TriageResult: {str(result)[:300]}")

    return result


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
    return run_triage(triage_agent(), prompt)


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
