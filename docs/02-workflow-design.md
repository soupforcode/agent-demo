# Module 2 — Agent Workflow Design

**30 minutes theory · 30 minutes lab**

> **Lab:** `make lab2`

Module 1 built an agent. This module is about building a *system* — which means
deciding what shape it should be, and resisting the shapes that only look good
on a slide.

---

## Structured output: the change that matters most

Module 1's agent replied with a paragraph. Useful to a human, useless to a
system. You cannot route on a paragraph, count it, put it in a queue, or write
a test that checks it.

Add one parameter and everything changes:

```python
agent = Agent(..., output_schema=TriageResult)
```

Now the agent must return a validated object:

```python
class TriageResult(BaseModel):
    department: Literal["accounts", "hostel", "examinations", ...]
    urgency: Literal["low", "normal", "high", "critical"]
    summary: str
    student_id: str
    suggested_action: str
    needs_human: bool
    reasoning: str
```

**This is what turns an agent from a demo into a component.** Everything
downstream — the API, the eval suite, the dashboard — depends on it.

### The schema is a prompt

Field descriptions aren't documentation; the model reads them to decide what
goes in each field.

```python
needs_human: bool = Field(
    description=(
        "True if this needs a person: money movement, a policy exception, a "
        "disciplinary matter, anything you are not confident about."
    )
)
```

Add a field with a good description and the agent fills it in without being
told to. Try it in the lab.

### Keep it flat

Gemini rejects large or deeply nested schemas, with poor error messages. And
Agno has a bug where `Optional[X] = None` can get marked *required* —
intermittently, which is the worst way for anything to fail.

So: primitives only, `Literal` rather than `Enum` (Literal inlines, Enum
creates a `$defs` entry), no Optionals. Use a required field with an empty
string as the "unknown" value.

`tests/test_schemas.py` enforces this, so a well-meaning refactor fails at test
time rather than in front of a room.

---

## Designing tools that are hard to misuse

The tool is where your agent meets reality, and reality is where it breaks.

**Say when, not just what.** "Look up a student" is weak. "Call this first
whenever a roll number is mentioned" tells the model about timing, which is the
thing it's actually bad at.

**Never raise for an ordinary miss.** A raised exception ends the loop. A
returned sentence lets the agent recover:

```python
return (
    f"No student found with roll number {roll_no!r}. "
    "Do not guess another roll number — ask the student to confirm it."
)
```

Note the second sentence. The tool is steering behaviour, not just reporting.

**Validate on the way in.** The model will occasionally invent a department.
`create_ticket` rejects it and says what's valid, so the agent can correct
itself:

```python
if department not in valid_departments:
    return f"Rejected: {department!r} is not a department. Use one of: ..."
```

**Put domain knowledge in the tool output.** `check_fee_status` doesn't just
return a balance — it explains that a pending NEFT payment inside three working
days is normal. That one sentence stops the agent escalating a non-problem, and
it belongs there rather than in the prompt because it's *about the data*.

**Keep the set small.** Six sharp tools beat fifteen vague ones. Most
tool-selection errors come from a model choosing plausibly among too many
options.

---

## Choosing a shape

```
  SINGLE AGENT          ROUTER              PIPELINE           TEAM
                                                            
   ┌───────┐          ┌───────┐          ┌───┐┌───┐┌───┐   ┌────────┐
   │ agent │          │router │          │ A ││ B ││ C │   │ leader │
   └───┬───┘          └───┬───┘          └───┘└───┘└───┘   └───┬────┘
   ┌───┴───┐         ┌────┼────┐           fixed order      ┌──┼──┐
   │6 tools│         ▼    ▼    ▼                            ▼  ▼  ▼
   └───────┘        acc  hos  exam                          A  B  C

  start here    when domains are   when the steps    when members must
                clearly separate   never vary        talk to each other
```

**Start with a single agent.** Split only when you can name the failure a split
would fix — usually "it keeps picking the wrong tool" or "two teams need to own
two halves of this".

**Router** (`TeamMode.route`) — a leader picks one specialist and returns its
answer unchanged. Each specialist gets a shorter prompt and fewer tools, which
measurably improves tool choice. Costs one extra model call per request.

**Pipeline** (`Workflow`) — fixed sequence of steps. If the order genuinely
never varies, this isn't an agent problem at all; it's a function call, and you
should write it as one.

**Team** — members collaborate. Powerful, expensive, hard to debug. Needed far
less often than it's used.

### The honest trade-off

A team roughly doubles latency and token spend, because the router runs *and*
then a specialist runs. On a free tier where requests-per-minute is your binding
constraint, that is not free.

In the lab you'll run both against the same ticket and compare. Ask yourself
honestly whether the team did better, or just cost more. For this problem — six
tools, one clear domain — a single agent is usually enough.

Splitting because the architecture diagram looks more serious gives you a system
that's slower, dearer and harder to debug, in exchange for nothing.

---

## Routing on cause, not symptom

The hardest part of this domain, and the most transferable lesson.

**Students tell you where they noticed a problem, not where it lives.**

| The student says | It belongs to | Because |
|---|---|---|
| "can't download my hall ticket" | **accounts** | fee block — examinations can't release it |
| "can't download my hall ticket" | **examinations** | attendance under 75% |
| "portal says my fees are pending" | **accounts** | the portal is only a view |
| "can't log in at all" | **it_support** | that really is IT |

Note that the first two are the *same sentence* with different causes. No amount
of prompt engineering resolves that — the agent has to **look up the record**.

Which is exactly why module 3 checks whether it did.

---

## Escalation is a design decision

```python
"Set needs_human to true for money movement, policy exceptions, discipline,
 safety, third-party requests, or whenever you are not confident."
```

The last clause matters most. Models are trained to be helpful, and helpfulness
under uncertainty looks like a confident guess.

Be explicit about the asymmetry:

> Escalating unnecessarily costs a few minutes of someone's time. Not
> escalating can harm a student. These are not equivalent, so do not treat them
> as a balanced trade-off.

Spell that out in the prompt. Left implicit, the model will balance them.

---

## In the lab

`01_structured_triage.py` — six deliberately hard tickets. Each one is a trap:
symptom-vs-cause, a false alarm that shouldn't escalate, a policy that forbids
the helpful answer, a third party asking about a student.

`02_routing_team.py` — the same ticket through one agent and through a team.
Compare the answers *and* the latency.

---

## Things worth trying

- Add a field to `TriageResult`. The agent fills it in unprompted.
- Delete the "route on the underlying cause" instruction and re-run the hall
  ticket case. One sentence was holding that up.
- Give the router a deliberately vague ticket and see which specialist it picks.

---

**Next:** [Module 3 — Evaluation](03-evaluation.md)
