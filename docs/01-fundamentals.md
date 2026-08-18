# Module 1 — Agent Fundamentals

**30 minutes theory · 30 minutes lab**

> **Lab:** `make lab1`

---

## What an agent is

Strip away the marketing and it's this:

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

**An agent is a loop around a language model that can call functions.**

That's the whole idea. You'll write it by hand in the lab — it's about twenty
lines. Everything else in this workshop is built on it.

---

## Chatbot, script, agent

|  | Decides what to do | Can act | Handles the unexpected |
|---|---|---|---|
| **Script** | you did, in advance | yes | no — it breaks |
| **Chatbot** | nothing, it just talks | no | n/a |
| **Agent** | at runtime, per input | yes | sometimes |

A script is a fixed path. A chatbot has no hands. An agent chooses its path at
runtime and can act on the world.

That flexibility is the whole value, and also the whole problem: **you cannot
know in advance exactly what it will do.** Everything difficult about
engineering agents follows from that one fact.

### When not to build an agent

If you can write the `if` statement, write the `if` statement.

An agent is the right tool when the input is unstructured, the path varies by
input, and the cost of occasionally being wrong is acceptable. If your problem
is "route to accounts when the message contains the word 'fee'", that's a
regex, and the regex is faster, cheaper, deterministic, and testable.

Reaching for an agent where a script would do is the most common and most
expensive mistake in this field.

---

## The four components

Every agent, in every framework, is these four things.

### 1. Model — the reasoning engine

Choosing a bigger model is the most common first instinct and the least
effective fix. Most agent failures are bad tools or bad instructions, not
insufficient intelligence.

In this repo the model lives in `config.py`, and only there.

### 2. Instructions — who it is, and how it decides

The most common mistake is describing the *domain* instead of the *behaviour*.
The model already knows what a hostel is. What it doesn't know is that you'd
rather it escalated than guessed.

Compare:

> ❌ "You are a helpful assistant for a college administration office."

> ✅ "If the ticket mentions a roll number, look the student up first. Route on
> the underlying cause, not the symptom. When you are not confident, set
> `needs_human` — uncertainty is the signal, not something to work around."

The second is a decision procedure. The first is a job title.

You'll measure the difference in module 3, where "lazy prompt" is one of the
deliberately broken variants.

### 3. Tools — what it can actually do

A tool is a Python function plus a description of when to call it.

**The model never runs your code.** It can only ask you to, by name, with
arguments. You decide whether to comply. That distinction is the entire
security model of agents — hold onto it.

The description is not documentation. It is prompt text the model reads when
choosing. A vague description produces a vaguely-chosen tool:

```python
def check_fee_status(roll_no: str) -> str:
    """Check what a student owes, what they've paid, and whether they're fee-blocked.

    Use this for anything about money, and also whenever a student cannot get a
    hall ticket or a transcript — those are withheld for unpaid fees, so the
    real cause is often here rather than in the examinations record.
    """
```

That second paragraph is about *timing*, and it is what makes the agent route
correctly in the lab. Delete it and watch the behaviour change.

### 4. Memory — what it remembers

In the raw loop, memory is a Python list that you append to. Nothing else
remembers anything. Frameworks add persistence and summarisation on top, but
underneath it is still that list.

---

## How the model calls a function

The model doesn't execute anything. The exchange is:

1. You send the conversation **plus a list of function schemas**.
2. The model replies either with text, or with a structured request:
   `check_fee_status(roll_no="CS21B014")`.
3. **You** run it — or don't.
4. You append the result to the conversation and send it again.
5. Repeat until the model replies with text instead of a request.

Step 5 is the exit condition. Which brings us to the thing everyone forgets.

---

## Where agents fail

**No stopping condition.** An agent that never decides it's finished loops
until your quota is gone. Always set a limit — `MAX_TURNS` in the raw loop,
`tool_call_limit` in Agno.

**Hallucinated arguments.** The model will invent roll numbers that look
plausible. Validate inputs in the tool; never trust the arguments.

**Confident wrongness.** The most dangerous failure. An agent with no way to
know an answer will usually guess rather than say "I don't know" — and the
guess reads exactly as well as a real answer. You'll see this directly in
module 3's "no tools" variant.

**Tools that raise.** If a tool throws, the loop breaks. If it returns *"No
student found with roll number 'ZZ99Z999'. Do not guess another one."*, the
agent recovers. Always explain, never raise.

---

## In the lab

`labs/lab1_fundamentals/01_raw_loop.py` — the loop by hand, in raw
`google-genai`. No framework. Watch the conversation grow, watch the tool calls
happen, watch it stop.

`labs/lab1_fundamentals/02_first_agent.py` — the same behaviour in ten lines of
Agno.

Read them side by side. Agno hasn't added intelligence; it has removed typing.
Knowing exactly what it removed is what lets you debug it later.

---

## Things worth trying

- Delete a tool's docstring description. Watch tool choice degrade. Descriptions
  are prompts.
- Set `MAX_TURNS = 1`. Watch it give up mid-thought.
- Use a roll number that doesn't exist. Watch it recover rather than crash.
- Turn on `debug_mode=True` and read what's actually being sent.

---

**Next:** [Module 2 — Workflow Design](02-workflow-design.md)
