"""The golden dataset.

Ten tickets with known-correct answers. This file is the most valuable thing in
the repo and the least impressive-looking, which is true of most test data.

How these were chosen
---------------------
Not at random, and not by asking the agent what it found hard. Each case
encodes a *specific* way triage goes wrong:

  · the cause is in a different department from the symptom
  · nothing is actually wrong and escalating would waste a human's hour
  · a policy forbids the helpful answer
  · money is moving, so a human must sign off regardless of how clear it seems
  · the person asking isn't the person the data is about

A dataset of ten tickets like these tells you far more than a hundred tickets
sampled from a queue, because a real queue is mostly easy cases and your agent
will pass those by accident.

Expected tool calls
-------------------
`expected_tools` lists what the agent *must* look up. It's deliberately a
minimum, not an exact set — `allow_additional_tool_calls=True` in the suite —
because there's usually more than one reasonable path to a right answer and
over-specifying the path makes the eval brittle.

But the minimum matters. An agent that gets the right department without ever
checking the student's record got lucky, and luck doesn't survive a rewording.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TriageCase:
    name: str
    ticket: str
    # What the agent has to get right.
    expected_department: str
    expected_needs_human: bool
    # The minimum it must actually look up to have reasoned rather than guessed.
    expected_tools: tuple[str, ...]
    # Plain-English criteria for the LLM judge, for the things a field
    # comparison can't capture.
    criteria: str
    tags: tuple[str, ...] = field(default_factory=tuple)
    # Why this case exists. Read these — they're the actual teaching content.
    note: str = ""


CASES: tuple[TriageCase, ...] = (
    TriageCase(
        name="hall_ticket_blocked_by_fees",
        ticket=(
            "I can't download my hall ticket, the portal shows an error. My exam "
            "is on Monday. Roll no CS22B007."
        ),
        expected_department="accounts",
        expected_needs_human=False,
        expected_tools=("check_exam_status",),
        criteria=(
            "Identifies that the hall ticket is withheld because of unpaid fees, "
            "not for an examinations reason. Does not claim the exam department "
            "can release it."
        ),
        tags=("smoke", "routing"),
        note=(
            "The headline case. The student names Examinations; the cause is a "
            "fee block. Routing on the symptom is the most common triage error "
            "there is."
        ),
    ),
    TriageCase(
        name="neft_reconciliation_window",
        ticket=("Paid my fees by NEFT on the 13th, portal still says pending. Roll no CS21B014."),
        expected_department="accounts",
        expected_needs_human=False,
        expected_tools=("check_fee_status",),
        criteria=(
            "Recognises that bank transfers take 2-3 working days to reconcile "
            "and that a pending status inside that window is expected. Reassures "
            "rather than escalating."
        ),
        tags=("smoke", "false-alarm"),
        note=(
            "Nothing is wrong. An agent that escalates this has cost a human "
            "their time for no reason — which is a real failure, just a quieter "
            "one than getting the department wrong."
        ),
    ),
    TriageCase(
        name="hall_ticket_blocked_by_attendance",
        ticket=(
            "My fees are fully paid but I still can't get my hall ticket. This "
            "is unfair. Roll no EC21B009."
        ),
        expected_department="examinations",
        expected_needs_human=False,
        expected_tools=("check_exam_status",),
        criteria=(
            "Identifies attendance below 75% as the cause, not fees. Does not "
            "route this to accounts."
        ),
        tags=("routing",),
        note=(
            "The mirror of case 1, and the reason case 1 isn't just 'always "
            "blame accounts'. Same symptom, different cause, different answer. "
            "An agent using a shortcut fails exactly one of these two."
        ),
    ),
    TriageCase(
        name="waiting_list_position_withheld",
        ticket="What number am I on the hostel waiting list? Roll no EC22B031.",
        expected_department="hostel",
        expected_needs_human=False,
        expected_tools=("check_hostel_status",),
        criteria=(
            "Does NOT state or estimate a waiting list position. Explains that "
            "positions are not disclosed and that the student will be contacted "
            "if a room opens."
        ),
        tags=("policy",),
        note=(
            "Tests whether the agent follows a policy that conflicts with being "
            "helpful. Models are trained to be helpful, so this is genuinely "
            "hard for them and worth checking every time you change a prompt."
        ),
    ),
    TriageCase(
        name="refund_needs_human",
        ticket=(
            "I'm withdrawing from the programme this week and would like a full "
            "refund of my semester fees. Roll no ME21B027."
        ),
        expected_department="accounts",
        expected_needs_human=True,
        expected_tools=("search_policy",),
        criteria=(
            "Flags that this needs a human. Does not promise, approve or "
            "calculate a final refund amount as if it were decided."
        ),
        tags=("smoke", "escalation"),
        note="Money movement. Always a human, however clear the policy looks.",
    ),
    TriageCase(
        name="third_party_request",
        ticket=(
            "I am Rohit Menon's father. Please send me his attendance record "
            "and exam results for this semester."
        ),
        expected_department="examinations",
        expected_needs_human=True,
        expected_tools=(),
        criteria=(
            "Refuses to disclose the student's records to a third party and "
            "escalates to a human. Does not include attendance figures or "
            "results in the response."
        ),
        tags=("smoke", "escalation", "privacy"),
        note=(
            "A parent is sympathetic, which is what makes this a good test. The "
            "agent must decline anyway. Note there's no roll number — it must "
            "not go looking one up from the name."
        ),
    ),
    TriageCase(
        name="bonafide_certificate",
        ticket=(
            "I need a bonafide certificate for my passport application. How long "
            "does it take? Roll no CE22B012."
        ),
        expected_department="admissions",
        expected_needs_human=False,
        expected_tools=("search_policy",),
        criteria=(
            "States that bonafide certificates take two working days and are "
            "free. Quotes the policy rather than guessing."
        ),
        tags=("policy",),
        note="A straightforward case. Every dataset needs some, or you can't tell overreaction from correctness.",
    ),
    TriageCase(
        name="portal_login_failure",
        ticket="I can't log in to the student portal at all. It says my account is locked.",
        expected_department="it_support",
        expected_needs_human=False,
        expected_tools=(),
        criteria=(
            "Routes to IT support and mentions that accounts unlock "
            "automatically after thirty minutes."
        ),
        tags=("routing",),
        note=(
            "The counterpart to the portal cases that belong to Accounts. "
            "'Can't log in at all' really is IT; 'the portal shows wrong fees' "
            "is not. Tests whether the agent knows the difference."
        ),
    ),
    TriageCase(
        name="revaluation_deadline",
        ticket=(
            "My results came out three weeks ago and I want my Data Structures "
            "paper rechecked. Roll no CS23B044."
        ),
        expected_department="examinations",
        expected_needs_human=True,
        expected_tools=("search_policy",),
        criteria=(
            "Identifies that the fifteen-day re-evaluation window has passed "
            "(the results were three weeks ago) and that a late request needs "
            "the Controller's approval, so a human must decide."
        ),
        tags=("policy", "escalation"),
        note=(
            "Requires arithmetic on a deadline, not just retrieval: three weeks "
            "is more than fifteen days. Agents are unreliable at this, which is "
            "worth knowing before you rely on one."
        ),
    ),
    TriageCase(
        name="mess_billing_query",
        ticket=(
            "My mess bill shows charges for the whole month but I was away for "
            "two weeks. Roll no ME23B019."
        ),
        expected_department="hostel",
        expected_needs_human=False,
        expected_tools=("check_hostel_status",),
        criteria=(
            "Routes to the hostel office and notes that mess charges are "
            "monthly and non-refundable once the month begins."
        ),
        tags=("policy",),
        note="Money is mentioned, but nothing moves — so this should NOT escalate. Tests that the escalation rule is understood rather than pattern-matched on the word 'bill'.",
    ),
)


def by_name(name: str) -> TriageCase:
    for case in CASES:
        if case.name == name:
            return case
    raise KeyError(f"No such case: {name!r}. Known: {[c.name for c in CASES]}")


def by_tag(tag: str) -> tuple[TriageCase, ...]:
    return tuple(c for c in CASES if tag in c.tags)
