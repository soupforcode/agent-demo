"""Checks that run *before* the model does.

A guardrail is not a prompt instruction. That distinction is the whole point of
this module.

An instruction is advice. It usually works, and "usually" is fine for tone or
formatting. A guardrail is a Python function that runs before the model is
called at all — so it costs nothing, cannot be talked out of it, and behaves the
same on the thousandth ticket as the first.

The rule for deciding which to use:

    Would you be comfortable if the model ignored this 5% of the time?
    Yes -> instruction.  No -> guardrail.

Anything about money, privacy, or someone's safety belongs on the "no" side.
The instructions in `agent.py` already ask the agent to refuse third-party
requests; the guardrail below means it cannot comply even if a cleverly worded
ticket persuades it to try.

Two more things worth noticing:

**Guardrails run before the API call.** A blocked ticket costs zero tokens and
zero quota. On a free tier that matters, and in production it's the cheapest
filter you own.

**They fail loudly.** Raising `InputCheckError` stops the run. Your service
turns that into a clean 4xx rather than a wrong answer delivered confidently.
"""

from __future__ import annotations

import re

from agno.exceptions import CheckTrigger, InputCheckError
from agno.guardrails import BaseGuardrail, PIIDetectionGuardrail
from agno.run.agent import RunInput
from agno.run.team import TeamRunInput


class TicketBlocked(RuntimeError):
    """A guardrail refused the ticket before the model ran.

    Agno does not propagate `InputCheckError` out of `Agent.run()` — it catches
    it and hands back a `RunOutput` with `status=error` whose `content` is the
    message *as a string*, not your output schema.

    That is easy to miss and produces a nasty downstream failure: code that
    expects a `TriageResult` silently receives a `str`. So `agent.triage()`
    detects the error status and raises this instead, which the API turns
    into a clean 403.
    """


# --------------------------------------------------------------------------
# Third-party requests
# --------------------------------------------------------------------------
# Someone asking about a student who isn't them. Sympathetic — usually a
# parent — and must be refused anyway. The examinations policy is explicit:
# records go to the student, or to an institution on written request, and to
# nobody else.
#
# The agent is already told this. The guardrail exists because "already told"
# is not the same as "cannot do otherwise", and this is a case where the
# difference matters to a real person.

_THIRD_PARTY_PATTERNS = [
    # "I am X's father/mother/guardian/parent/brother/sister"
    r"\b(?:i\s*am|i'm|this\s+is)\b[^.?!]{0,40}\b(?:father|mother|parent|guardian|brother|sister|uncle|aunt)\b",
    # "my son/daughter/child/ward ..."
    r"\bmy\s+(?:son|daughter|child|ward)\b",
    # "on behalf of ..."
    r"\bon\s+behalf\s+of\b",
    # "his/her results", "his/her attendance" — asking about someone else
    r"\b(?:his|her|their)\s+(?:result|results|attendance|marks|record|records|transcript|fees)\b",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in _THIRD_PARTY_PATTERNS]


class ThirdPartyRequestGuardrail(BaseGuardrail):
    """Block anyone asking for a student's records who isn't that student.

    Deliberately a little over-eager. A false positive costs one polite
    redirect; a false negative discloses someone's academic record to a
    stranger. Those are not the same size of mistake, so the threshold is not
    set in the middle.
    """

    def _detect(self, run_input: RunInput | TeamRunInput) -> str | None:
        content = run_input.input_content_string()
        for pattern in _COMPILED:
            match = pattern.search(content)
            if match:
                return match.group(0)
        return None

    def _raise(self, phrase: str) -> None:
        raise InputCheckError(
            "This looks like a request about someone else's records. Student "
            "records are released only to the student, so this needs a human "
            "and cannot be answered automatically.",
            check_trigger=CheckTrigger.INPUT_NOT_ALLOWED,
            additional_data={"matched": phrase},
        )

    def check(self, run_input: RunInput | TeamRunInput) -> None:
        phrase = self._detect(run_input)
        if phrase:
            self._raise(phrase)

    async def async_check(self, run_input: RunInput | TeamRunInput) -> None:
        phrase = self._detect(run_input)
        if phrase:
            self._raise(phrase)


# --------------------------------------------------------------------------
# Personal data
# --------------------------------------------------------------------------
# Agno's built-in PII detector, tuned for this domain.
#
# There's a specific reason to want this in a *workshop*: free-tier Gemini
# input is used for training and may be read by human reviewers. A student
# testing the agent on their own Aadhaar number or bank details has just
# published it. The guardrail stops that at the door.
#
# `mask_pii=False` means we refuse rather than silently redact. For teaching,
# refusing is better — a masked value looks like it worked.


def build_pii_guardrail() -> PIIDetectionGuardrail:
    """PII detection with the identifiers this domain actually sees."""
    return PIIDetectionGuardrail(
        mask_pii=False,
        enable_email_check=False,  # college emails are in every ticket, legitimately
        enable_phone_check=True,
        enable_ssn_check=True,
        enable_credit_card_check=True,
        custom_patterns={
            # Aadhaar: 12 digits, usually spaced in groups of four.
            "aadhaar": re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"),
            # PAN: five letters, four digits, one letter.
            "pan": re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),
        },
    )


def default_guardrails() -> list[BaseGuardrail]:
    """The set the triage agent runs with.

    Order matters a little: the cheapest, most certain check goes first.
    """
    return [ThirdPartyRequestGuardrail(), build_pii_guardrail()]


def enforce(text: str) -> None:
    """Run every default guardrail over `text`, raising TicketBlocked if any fires.

    Why this exists as well as `pre_hooks`:

    Agno catches `InputCheckError` inside `Agent.run()` and returns a
    `RunOutput` with `status=error` and the message as a plain string. A
    model failure — a bad key, a rate limit — produces a RunOutput that looks
    *exactly the same*. There is no field that separates them, so a caller
    cannot tell 'we refused this on policy grounds' from 'the API is down'.

    Those need different answers (403 versus 502), so the service layer
    checks explicitly and gets a typed exception. The agent keeps its
    `pre_hooks` too: anything calling the Agent directly is still protected.
    Defence in depth, and the duplication costs a few microseconds of regex.
    """
    probe = RunInput(input_content=text)
    for guard in default_guardrails():
        try:
            guard.check(probe)
        except InputCheckError as exc:
            raise TicketBlocked(str(exc)) from exc
