---
marp: true
theme: default
paginate: true
header: 'Architecting Autonomous Intelligence'
style: |
  section { font-size: 26px; }
  section.lead { text-align: center; }
  section.lead h1 { font-size: 56px; }
  h1 { color: #1a3d5c; }
  h2 { color: #2b6a8f; }
  code { font-size: 0.85em; }
  pre { font-size: 0.7em; }
  table { font-size: 0.8em; }
  .small { font-size: 0.8em; }
---

<!-- _class: lead -->

# Architecting Autonomous Intelligence

### Building, evaluating and shipping AI agents

<br>

**4 hours · 4 modules · one working system**

<span class="small">You'll build a college administration triage agent.
Yes, the fee portal one.</span>

---

<!-- _class: lead -->

# Module 1
## Agent Fundamentals

---

## What we're building

Every one of you has sent an email like this:

> *"I paid my fees by NEFT on the 13th but the portal still says pending and
> I'm worried about my hall ticket. Roll no CS21B014."*

Someone reads it, looks up three systems, and decides who should handle it.

**Today you'll build the thing that does that.**

---

## An agent is a for-loop

```
    ┌──────────────────────────────────────────┐
    │                                          │
    ▼                                          │
  ┌───────┐   "call check_fee_status"   ┌──────────┐
  │ MODEL │ ──────────────────────────► │ YOUR CODE│
  └───────┘                             └──────────┘
    ▲                                          │
    │        "Rs.88,000 outstanding"           │
    └──────────────────────────────────────────┘

         repeat until the model stops asking
```

That's it. About twenty lines. You'll write it yourself in a moment.

---

## Script vs chatbot vs agent

|  | Decides what to do | Can act | Handles surprises |
|---|---|---|---|
| **Script** | you did, in advance | yes | no — it breaks |
| **Chatbot** | nothing, it talks | no | n/a |
| **Agent** | at runtime, per input | yes | sometimes |

<br>

The flexibility is the value **and** the problem:

> **You cannot know in advance exactly what it will do.**

Everything hard about agents follows from that one sentence.

---

## When *not* to build an agent

<br>

# If you can write the `if` statement,<br>write the `if` statement.

<br>

<span class="small">
"Route to accounts when the message contains 'fee'" is a regex.<br>
The regex is faster, cheaper, deterministic, and testable.
</span>

**This is the most expensive mistake in the field.**

---

## The four components

<br>

| | |
|---|---|
| **Model** | the reasoning engine |
| **Instructions** | who it is, and how it decides |
| **Tools** | what it can actually do |
| **Memory** | what it remembers |

<br>

Every agent. Every framework. Underneath, always these four.

---

## Instructions: describe *behaviour*, not domain

❌ "You are a helpful assistant for a college administration office."

<br>

✅ "If the ticket mentions a roll number, look the student up first.
Route on the underlying cause, not the symptom.
When you are not confident, set `needs_human` — uncertainty **is** the signal."

<br>

The model already knows what a hostel is.
It doesn't know you'd rather it escalated than guessed.

---

## Tools: the model never runs your code

<br>

It can only **ask** you to — by name, with arguments.

You decide whether to comply.

<br>

> **That is the entire security model of agents.**

<br>

Hold onto it. It's the thing most people never have stated plainly.

---

## The docstring is a prompt

```python
def check_fee_status(roll_no: str) -> str:
    """Check what a student owes, and whether they're fee-blocked.

    Use this for anything about money, and also whenever a student
    cannot get a hall ticket — those are withheld for unpaid fees,
    so the real cause is often here, not in the exam record.
    """
```

The second paragraph is about **timing**.

It's what makes the agent route correctly. Delete it and behaviour changes.

---

## Where agents fail

| Failure | Fix |
|---|---|
| **No stopping condition** | `tool_call_limit` — always |
| **Hallucinated arguments** | validate inside the tool |
| **Tools that raise** | return an explanation, never throw |
| **Confident wrongness** | ← module 3 |

<br>

> When a normal program breaks, it crashes.
> **When an agent breaks, it writes you a paragraph.**

---

<!-- _class: lead -->

# Lab 1
## `make lab1`

**`01_raw_loop.py`** — the loop by hand, no framework
**`02_first_agent.py`** — the same thing in 10 lines of Agno

*Read them side by side.*

---

<!-- _class: lead -->

# Module 2
## Agent Workflow Design

---

## Prose is useless to a system

Lab 1's agent returned a paragraph.

You cannot **route** on a paragraph. Or count it. Or test it.

```python
agent = Agent(..., output_schema=TriageResult)
```

```python
class TriageResult(BaseModel):
    department: Literal["accounts", "hostel", "examinations", ...]
    urgency:    Literal["low", "normal", "high", "critical"]
    summary:    str
    needs_human: bool
```

**This is what turns an agent into a component.**

---

## The schema is also a prompt

```python
needs_human: bool = Field(
    description=(
        "True if this needs a person: money movement, a policy "
        "exception, a disciplinary matter, anything you are not "
        "confident about."
    )
)
```

Add a field with a good description — the agent fills it in
**without being told to**.

Try it in the lab.

---

## Keep the schema flat

<br>

| Do | Don't |
|---|---|
| `Literal["a", "b"]` | `SomeEnum` — creates `$defs` |
| `str`, `bool`, `int` | nested `BaseModel` |
| required + `""` sentinel | `Optional[str] = None` |

<br>

Gemini rejects nested schemas with unhelpful errors.
Agno has a bug where `Optional` can be marked *required* — **intermittently**.

`tests/test_schemas.py` enforces this so you find out at test time.

---

## Choosing a shape

```
  SINGLE AGENT       ROUTER           PIPELINE         TEAM

   ┌───────┐       ┌───────┐       ┌───┐┌───┐┌───┐  ┌────────┐
   │ agent │       │router │       │ A ││ B ││ C │  │ leader │
   └───┬───┘       └───┬───┘       └───┘└───┘└───┘  └───┬────┘
   ┌───┴───┐      ┌────┼────┐        fixed order     ┌──┼──┐
   │6 tools│      ▼    ▼    ▼                        ▼  ▼  ▼
   └───────┘     acc  hos  exam                      A  B  C

  START HERE   domains are     order never      members must
               clearly separate  varies         talk to each other
```

---

## The honest trade-off

A team **doubles** your model calls.
Router runs, *then* a specialist runs.

<br>

> Start with one agent.
> Split when you can **name the failure** a split would fix.

<br>

Splitting because the diagram looks more serious gives you a system that's
slower, dearer and harder to debug — in exchange for nothing.

---

## Route on cause, not symptom

Students tell you where they **noticed** a problem, not where it lives.

| They say | It belongs to | Because |
|---|---|---|
| "can't get my hall ticket" | **accounts** | fee block |
| "can't get my hall ticket" | **examinations** | attendance < 75% |
| "portal says fees pending" | **accounts** | the portal is only a view |
| "can't log in at all" | **it_support** | that really is IT |

**Rows 1 and 2 are the same sentence.**

No prompt engineering fixes that. It has to look up the record.

---

## Escalation is a design decision

```
Set needs_human for: money movement, policy exceptions,
discipline, safety, third-party requests —
and whenever you are not confident.
```

<br>

> Escalating unnecessarily costs a few minutes of someone's time.
> Not escalating can harm a student.
> **These are not equivalent.**

<br>

Say that explicitly. Left implicit, the model will balance them.

---

<!-- _class: lead -->

# Lab 2
## `make lab2`

Six tickets. Every one is a trap.

*Which ones does it get wrong?*

---

<!-- _class: lead -->

# Module 3
## Agent Evaluation

---

## You tried five tickets. They looked fine.

<br>

# You have no idea whether it works.

<br>

- Models are **non-deterministic** — five passes might be five coin flips
- You chose the tickets your prompt already handles
- One word of prompt change alters behaviour on inputs you never tried
- No compiler. No type system. No stack trace.

---

## Three things worth measuring

<br>

| | Question | Cost |
|---|---|---|
| **Reliability** | did it do the work? | free, deterministic |
| **Accuracy** | was it right? | a judge call per case |
| **Cost** | what did it take? | free |

<br>

Start with reliability. It's free, and it catches something the others can't.

---

## Reliability: did it reason, or get lucky?

An agent can get the right answer **without doing any work**.

Ask about a hall ticket — "accounts" is a decent guess. It scores a point.

Reword the ticket slightly and it collapses.

```python
ReliabilityEval(
    agent_response=response,
    expected_tool_calls=["check_exam_status"],
    allow_additional_tool_calls=True,
)
```

**You cannot see this by reading outputs.** That's why it gets missed.

---

## Judges are not oracles

<br>

- **They reward fluency** — a confident wrong answer beats a hesitant right one
- **They drift** — same eval, same code, different score
- **Weakest where you need them** — borderline cases are exactly where written
  criteria stop being crisp
- **Same blind spots** — same model family as the thing being judged

<br>

> Evidence, not a verdict. **Read the failures yourself.**

---

## The golden dataset

Nine tickets. `evals/cases.py`.

Each one encodes a **specific way it goes wrong**:

| Case | Catches |
|---|---|
| hall ticket / fee block | routing on symptom |
| hall ticket / attendance | ← the **mirror**. Stops shortcuts passing |
| NEFT pending | escalating a non-problem |
| waiting list position | policy that conflicts with being helpful |
| father asking for records | sympathetic requester, must still refuse |

**Ten well-chosen cases beat a hundred sampled ones.**

---

## Now break it on purpose

"7 out of 10" — is that good? **You have no idea.**

An eval suite is useful only if it **detects a regression**.

| Variant | Damage | Result |
|---|---|---|
| baseline | none | — |
| no lookups | removed "look it up first" | invents plausible answers |
| no tools | removed fee/exam tools | **confident guesses** |
| lazy prompt | one vague sentence | inconsistent run to run |

**Break it and the score doesn't move? Your suite is decoration.**

---

<!-- _class: lead -->

# Lab 3
## `make lab3`

Reliability → accuracy → sabotage

*Watch the numbers move.*

---

<!-- _class: lead -->

# Module 4
## Product Deployment

---

## Nobody uses a script you run

```
  client ──► FastAPI ──► agent ──► Gemini
              │           │
              │           └──► tools ──► your database
              │
              └──► AgentOS  (80+ endpoints, mounted not written)
```

<br>

**Your endpoint is the product.** AgentOS is infrastructure underneath it.

Build it the other way round and you can't change frameworks
without changing your public interface.

---

## Start degraded, don't crash

Our app **starts with no API key.**
`/health` says degraded. `/triage` returns 503 with an explanation.

<br>

> A container that crashes at import because a config value is missing
> dies in a restart loop and **never gets to tell anyone why.**

<br>

Start. Serve. Report.

---

## Health checks must be free

`/health` **never calls the model.** Deliberately.

<br>

A health check that costs an API request:

- drains your quota on a schedule
- reports **your provider** being down as **you** being down
- so your orchestrator kills a healthy container because Google had a bad minute

---

## Bound everything

<br>

```python
tool_call_limit=10        # a confused agent can't run away
max_output_tokens=2048    # TPM is a limit too
timeout=60                # don't hang the request
retries=5, exponential_backoff=True
cache_response=True       # re-running while debugging is free
```

<br>

> **An unbounded agent is an unbounded bill.**

One request is **5–15 model calls**, not one.

---

## The part that's actually your responsibility

<br>

**Free-tier Gemini input and output is used to train Google's models
and may be read by human reviewers.**

<span class="small">That's their terms, not a rumour.</span>

<br>

If this were real, every student's fee dispute would be in that pipeline.

An agent that can *read* a student's fee record can *leak* a student's fee record.

---

## CI: the safety net

Prompts get edited casually. No type checker catches what that breaks.

| Job | Needs a key? | Proves |
|---|---|---|
| `checks` | no | plumbing is sound |
| `eval` | yes | the agent reasons well |

<br>

> **CI green means the plumbing works —
> not that the agent works.**

Knowing that difference is most of what separates senior from junior.

---

<!-- _class: lead -->

# Lab 4
## `make lab4` · `make serve` · `make docker`

---

<!-- _class: lead -->

# What you're taking away

---

## Six things

1. An agent is a **for-loop** around an LLM. You wrote one.
2. **Structured output** is what makes an agent composable.
3. The model **never runs your code** — it only asks.
4. You can tell **reasoning from luck**, and you know how.
5. One request is **5–15 model calls**, not one.
6. **CI green ≠ it works.**

---

<!-- _class: lead -->

<br>

# If you can write the `if` statement,
# write the `if` statement.

<br>

<span class="small">

`github.com/soupforcode/agent-demo`

</span>
