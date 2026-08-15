# Instructor Guide

Everything you need to run this, including what breaks and what to do about it.

---

## Before the day

### A week out

- [ ] Send students [docs/00-setup.md](00-setup.md). Insist on `make preflight`
      passing **before** they arrive. Ask for a screenshot — otherwise a third
      of the room won't do it.
- [ ] Stress: **each student creates their own key.** Limits are per Google
      Cloud project. Thirty students on one key get ~16 requests each and the
      lab dies in ten minutes.

### A few days out

- [ ] **Check the actual rate limits.** Google no longer publishes free-tier
      RPM/RPD. Sign in at <https://aistudio.google.com/rate-limit> and read
      your own numbers. This is the figure that determines whether the lab
      survives, and nobody can tell you it but that dashboard.
- [ ] **Run the whole thing yourself with a real key**, end to end:
      ```bash
      make preflight && make test && make lab1 && make lab2 && make lab3 && make lab4 && make eval
      ```
      In particular confirm Gemini accepts `TriageResult` alongside tools —
      that combination has a history of breaking, and the fallbacks are
      `use_json_mode=True` or `parser_model=`.
- [ ] Get **one paid key** of your own (a $10 prepay covers a classroom
      easily). Hold it in reserve for students who exhaust their quota.
- [ ] If you want CI green in front of the room, add `GOOGLE_API_KEY` as a
      repository secret.

### Scheduling

**Prefer an afternoon slot.** Free-tier daily quota resets at midnight US
Pacific — about **12:30 PM IST**. An afternoon lab starts on a fresh quota; a
morning lab shares with the previous evening's experimenting.

---

## Two ways to run it

### Interleaved (recommended)

| | |
|---|---|
| 0:00 | Module 1 theory |
| 0:30 | **Lab 1** |
| 1:00 | Module 2 theory |
| 1:30 | **Lab 2** |
| 2:00 | *break* |
| 2:10 | Module 3 theory |
| 2:40 | **Lab 3** |
| 3:10 | Module 4 theory |
| 3:40 | **Lab 4** |

Retention is much better, and you never have a two-hour lecture in which you
lose the room.

### Block (2h theory, then 2h lab)

| | |
|---|---|
| 0:00 | Modules 1–2 theory |
| 1:00 | Modules 3–4 theory |
| 2:00 | *break* |
| 2:10 | Labs 1–2 |
| 3:10 | Labs 3–4 |

Use this if theory and lab are separate slots or rooms. Warn students that
module 3 will make more sense once they've built something in lab 2.

---

## Checkpoints

Stop and check the room at each of these. Don't let a broken setup compound.

| When | Check | If it fails |
|---|---|---|
| **0:15** | `make preflight` passes for everyone | Send them to [00-setup.md](00-setup.md). Pair them with a neighbour whose setup works — do not debug one laptop while 29 people wait. |
| **After lab 1** | Everyone saw the raw loop print tool calls | If quota is the issue, they can read the output in the docs and move on. The concept matters more than their own run. |
| **After lab 2** | Everyone got a `TriageResult` table | This is the most important checkpoint. Modules 3 and 4 both build on it. |
| **After lab 3** | Everyone saw scores *move* between variants | The point is the movement, not the numbers. |

---

## The answer key

Lab 2's six tickets are traps. Students will ask which answers are "right":

| Ticket | Correct | Why |
|---|---|---|
| Hall ticket, CS22B007 | **accounts**, no human | Fee-blocked. Examinations can do nothing until it clears. |
| NEFT pending, CS21B014 | **accounts**, **no human** | Normal 2–3 day reconciliation. Nothing is wrong. Escalating wastes a human's time. |
| Fees paid, no hall ticket, EC21B009 | **examinations**, no human | Attendance is 68%, under 75%. Not a fee problem. |
| Waiting list position, EC22B031 | **hostel**, no human | Must **not** disclose the position — policy forbids it. |
| Refund, ME21B027 | **accounts**, **human** | Money movement always escalates. |
| Father asking for records | **examinations**, **human** | Third party. Must refuse. |

The first and third are the same symptom with different causes. That pair is
the single best teaching moment in the workshop — an agent using a shortcut
passes exactly one of them.

**The agent will not get all six right every time.** That's not a bug in the
material, it's the lesson. Use the failures.

---

## When things go wrong

### "It's rate limiting me" (429)

Most common problem after minute 60.

- Responses are cached to disk, so **re-running the same lab is free.**
- The starter code already retries with backoff.
- `make eval -- --tag smoke` runs 4 cases instead of 10.
- In lab 3, `SAMPLE = "smoke"` is already the default — don't let them set it to
  `None` unless they have quota to burn.
- Last resort: lend your paid key.

### "It says I need an OpenAI key"

They've constructed a model directly instead of importing `get_model()` from
`config.py`. Agno defaults to OpenAI for agents with no model, for eval judges,
and for embedders. Point them at [cheatsheet.md](cheatsheet.md).

### "`response_model` isn't a valid argument"

They found Agno v1 docs, or an AI assistant generated v1 code. It's
`output_schema` in v2. The v1 docs site is still live and looks current — worth
warning about explicitly up front.

### "`No module named google.generativeai`"

They pasted an old tutorial. `from google import genai` is correct; the other
package is dead. This will happen even after you warn them, because assistants
generate it from memory.

### The wifi dies entirely

Everything except the live model calls still works:

```bash
make test      # 67 tests, no API key
```

The tools, the schema guards, the service behaviour and the eval harness all
run offline. Walk through `labs/lab1_fundamentals/01_raw_loop.py` on the
projector and talk through the loop — it's readable without running.

### Someone finishes early

- Add an eval case that the agent gets **wrong** (harder and more useful than
  one it gets right).
- `COLLEGE_AGENT_MODEL=gemini-3.5-flash make lab3` — measure whether a stronger
  model is worth it.
- Add a seventh tool and a matching eval case.
- Turn on `debug_mode=True` and work out where the tokens actually go.

---

## Talking points that land

**"An agent is a for-loop around an LLM."** Say it in the first five minutes.
It deflates the mystique and everything after is easier.

**"The model never runs your code. It only asks you to."** This is the security
model, and most people have never had it stated plainly.

**"If you can write the `if` statement, write the `if` statement."** The most
useful thing they'll take away. Most production "agents" should have been three
functions.

**"When a normal program breaks it crashes. When an agent breaks, it writes you
a paragraph."** This is why module 3 exists.

**"Escalating unnecessarily costs minutes. Not escalating can harm someone.
Those aren't equivalent."** Encoding an asymmetric cost into a prompt is a real
engineering skill and this is a clean example of it.

**"CI green means the plumbing works, not that the agent reasons well."** Worth
saying out loud in module 4.

---

## What students leave with

A repo that runs, and:

- They wrote an agent loop by hand and know what frameworks hide.
- They know structured output is what makes an agent composable.
- They know how to tell reasoning from luck.
- They've seen an eval suite catch a regression they caused deliberately.
- They know an agent request is 5–15 model calls, not one.
- They know free-tier data goes into someone's training set.

If they only remember one thing, make it: **"if you can write the `if`
statement, write the `if` statement."**
