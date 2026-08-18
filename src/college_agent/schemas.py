"""The contract the agent has to fill in.

This is the single most important design decision in the whole project, and
it's easy to walk past. A chatbot returns prose. Prose is unusable: you can't
route on it, you can't count it, you can't test it. The moment you ask for a
*structured* result instead, the agent becomes a component you can build a
system out of.

Two rules learned the hard way, both enforced below:

**Keep it flat.** Gemini rejects large or deeply nested schemas, and the error
it gives you is not friendly. Every field here is a plain string, bool or int —
no nested models, no lists of objects.

**Avoid Optional.** Agno has a schema-sanitising bug where `Optional[str] = None`
can end up marked as *required*, which fails intermittently and is horrible to
debug. So instead of optional fields, we use required fields with an explicit
empty-string or sentinel meaning. Less elegant, considerably more reliable.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Which desk in the administration block actually owns this problem.
Department = Literal[
    "accounts",  # fees, scholarships, refunds, fines
    "hostel",  # allotment, room changes, mess, wardens
    "examinations",  # hall tickets, results, re-evaluation, transcripts
    "admissions",  # applications, documents, transfers, bonafide certificates
    "it_support",  # portal logins, email, wifi
    "unknown",  # we genuinely couldn't tell — a human should look
]

Urgency = Literal[
    "low",  # can wait a week
    "normal",  # a few days
    "high",  # today — something is blocked
    "critical",  # a deadline is being missed right now
]


class TriageResult(BaseModel):
    """A triage decision about one student ticket.

    This is what the agent must produce. Nothing here is decoration — every
    field exists because a downstream system would need it to act.
    """

    department: Department = Field(
        description="Which department owns this ticket. Use 'unknown' if genuinely unclear.",
    )
    urgency: Urgency = Field(
        description=(
            "How fast this needs handling. Reserve 'critical' for a deadline being "
            "missed right now, not for a student who sounds upset."
        ),
    )
    summary: str = Field(
        description="One sentence, factual, no more than 25 words. What is actually wrong?",
    )
    student_id: str = Field(
        description=(
            "The student's roll number if you could establish it, else an empty "
            "string. Do not guess or invent one."
        ),
    )
    suggested_action: str = Field(
        description="The single concrete next step whoever picks this up should take.",
    )
    needs_human: bool = Field(
        description=(
            "True if this needs a person: money movement, a policy exception, a "
            "disciplinary matter, anything you are not confident about, or anything "
            "where being wrong would harm the student."
        ),
    )
    reasoning: str = Field(
        description="Briefly, why you routed it this way. What evidence did you use?",
    )


class TriageRequest(BaseModel):
    """An incoming ticket, as the API receives it."""

    message: str = Field(
        description="What the student wrote, in their own words.",
        min_length=1,
        max_length=4000,
    )
    student_id: str = Field(
        default="",
        description="Roll number, if the portal already knows who's asking.",
        max_length=32,
    )
