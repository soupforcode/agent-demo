#!/usr/bin/env python3
"""Generate notebooks/workshop.ipynb — the whole workshop, live, in Colab.

    python scripts/build_live_notebook.py

Every piece of the agent is a cell you can edit: the instructions, the schema,
the six tools, the guardrails, the eval cases. Change a fee record and re-run,
and you watch the routing change. That is the point — this is a lab bench, not
a walkthrough of somebody else's repo.

The repo version of the same material still exists as
`notebooks/workshop_branches.ipynb`, which drives the seven `step-*` branches
with `git switch` and `git diff`. Use that one if you want the real
file layout, the tests and CI. Use this one to teach.

This notebook and the repo WILL drift, and that is an accepted trade. The
notebook is written to be read on a projector — no `from __future__`, no
module docstrings, no defensive plumbing. Keeping the two byte-identical would
make the notebook worse at the only job it has.

The knowledge base is fetched from the repo at runtime rather than pasted in:
351 lines of policy markdown is data, not a lesson, and it would bury the code
students are supposed to be reading. Records ARE pasted in, as plain Python
dicts, precisely so they can be edited live.
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "notebooks" / "workshop.ipynb"
REPO = "https://github.com/soupforcode/agent-demo"
RAW = "https://raw.githubusercontent.com/soupforcode/agent-demo/main/src/college_agent/kb"

CELLS: list[tuple[str, str]] = []


def md(text: str) -> None:
    CELLS.append(("markdown", text.strip("\n")))


def code(text: str) -> None:
    CELLS.append(("code", text.strip("\n")))


# ==========================================================================
# Title
# ==========================================================================
md("""
# Architecting Autonomous Intelligence
### Two hours. One agent. Every line of it in this notebook.

Your college admin office gets tickets like *"I can't download my hall ticket,
my exam is on Monday."* Somebody has to read each one and decide who deals
with it. Today you build the thing that decides.

Everything is a cell you can edit — the instructions, the schema, the tools,
the guardrails, the test cases. **Change a student's fee record and re-run, and
you will watch the agent route the ticket somewhere else.** That is the whole
reason this is a notebook and not a slideshow.

It will not go smoothly, on purpose. By step 2 your agent will produce a
perfectly formatted, fully validated, entirely **invented** answer about a
student it never looked up. Fixing that is most of the workshop.

**You need one API key:**

- **Gemini** — free, no card: <https://aistudio.google.com/apikey>
- **OpenAI** — same code path, but no free tier: <https://platform.openai.com/api-keys>

> ### Get your own key. Seriously.
> Limits count per Google Cloud project, not per key. Thirty people sharing
> one key get about **sixteen requests each** — and one ticket costs the agent
> 5–15 model calls. A shared key dies before the first break and takes the
> room with it.

---

**Run the cells in order.** Later ones use names defined earlier. If something
looks broken, *Runtime → Restart session* and run from the top.
""")

# ==========================================================================
# Setup
# ==========================================================================
md("""
---
# Setup

Two cells: install, then your key. About a minute.
""")

code("""
%pip install -q "agno==2.9.0" google-genai openai rich

# Agno is pinned exactly. It ships every two or three days and v2 broke every
# v1 API — an unpinned install is how a working notebook stops working
# overnight. If you find tutorials using `response_model=`, they are v1.
print("installed")
""")

md("""
### Your API key

Use the **secrets panel**, not a literal in a cell. Anything typed into a cell
is saved in the notebook and travels with it — a genuinely common way to
publish a working key by accident.

1. Click the **🔑 key icon** in the left sidebar.
2. **+ Add new secret**, named for the key you have — `GOOGLE_API_KEY` or
   `OPENAI_API_KEY`.
3. Paste the value, and turn on **Notebook access**.

> **It is `GOOGLE_API_KEY`, not `GEMINI_API_KEY`.** Google's own quickstart
> says the second one. Agno only reads the first. This single mismatch has
> eaten more workshop time than every other setup problem combined.
""")

code("""
import os


def secret(name):
    # Empty string if missing or not shared with this notebook, so the caller
    # can just check truthiness.
    try:
        from google.colab import userdata

        return (userdata.get(name) or "").strip()
    except Exception:
        return ""


google_key, openai_key = secret("GOOGLE_API_KEY"), secret("OPENAI_API_KEY")

if google_key:
    PROVIDER, os.environ["GOOGLE_API_KEY"] = "google", google_key
elif openai_key:
    PROVIDER, os.environ["OPENAI_API_KEY"] = "openai", openai_key
else:
    import getpass

    PROVIDER = input("Provider - google or openai? [google]: ").strip().lower() or "google"
    var = "OPENAI_API_KEY" if PROVIDER == "openai" else "GOOGLE_API_KEY"
    os.environ[var] = getpass.getpass(f"{var}: ")

print("provider:", PROVIDER)
""")

md("""
### One place that builds the model

Every agent, every specialist and every eval judge in this notebook calls
`get_model()`. Nothing else constructs a model.

That is not tidiness for its own sake. **Agno quietly falls back to OpenAI in
three places** — an `Agent` with no model, an eval judge, and a vector-store
embedder. Each one fails halfway through something, asking for a key you may
not have. One function means one place to change providers, and no surprises.

It is also why supporting a second provider costs one `if` statement instead
of a rewrite.
""")

code('''
from agno.models.google import Gemini
from agno.models.openai import OpenAIChat


def get_model(temperature: float = 0.1, max_tokens: int = 2048, model_id: str = ""):
    """The only place in this notebook that builds a model.

    `model_id` overrides the default. Step 6 uses it to run the same eval
    against a deliberately weaker model.
    """
    shared = dict(
        temperature=temperature,
        # An agent loop is 5-15 calls back to back. Against a free-tier
        # requests-per-minute ceiling that 429s almost immediately, so retry
        # with backoff is not an optimisation — it is the difference between
        # this working and not.
        retries=5,
        delay_between_retries=2,
        exponential_backoff=True,
        timeout=60,
    )
    if PROVIDER == "google":
        # flash-lite: cheapest, fastest, most generous free limits. The binding
        # constraint here is requests per minute, not intelligence.
        return Gemini(id=model_id or "gemini-3.5-flash-lite", max_output_tokens=max_tokens, **shared)
    # The one place the SDKs genuinely disagree: max_output_tokens vs
    # max_completion_tokens. Same idea, different spelling.
    return OpenAIChat(id=model_id or "gpt-5.4-mini", max_completion_tokens=max_tokens, **shared)


print(type(get_model()).__name__)
''')

# ==========================================================================
# Step 0 — the raw loop
# ==========================================================================
md("""
---
# Step 0 — What an agent actually is
*No framework. No Agno. A `while` loop and about twenty lines.*

Before we use a framework, write the thing by hand once. The whole idea is
smaller than the hype:

> **An agent is a loop that calls a language model, and when the model asks to
> run a function, runs it, hands back the result, and calls the model again.**

That is it. Memory, teams, workflows, planning — all of it is built on top of
that loop. Once you have seen it written out, frameworks stop being magic and
become what they are: a way to avoid writing this every time.

**The one sentence to take away:** the model never runs your code. It only
*asks* you to, by name, with arguments. Your code decides whether to comply.
That is the security model, and most people have never had it stated plainly.

First, two toy tools and three students — just enough to make the loop do
something. The real six arrive at step 3.
""")

code("""
MINI = {
    "CS22B007": dict(name="Priya Nair", due=88000, paid=0, status="blocked"),
    "CS21B014": dict(name="Rohit Menon", due=92000, paid=92000, status="pending"),
    "EC21B009": dict(name="Sneha Iyer", due=92000, paid=92000, status="paid"),
}


def get_student(roll_no: str) -> str:
    s = MINI.get(roll_no.strip().upper())
    return f"{roll_no}: {s['name']}." if s else f"No student {roll_no!r}."


def get_fees(roll_no: str) -> str:
    s = MINI.get(roll_no.strip().upper())
    if not s:
        return f"No fee record for {roll_no!r}."
    owed = s["due"] - s["paid"]
    extra = " FEE-BLOCKED: hall tickets are withheld." if s["status"] == "blocked" else ""
    return f"{roll_no}: owes Rs.{owed:,}, status {s['status']}.{extra}"


IMPLEMENTATIONS = {"get_student": get_student, "get_fees": get_fees}

# What the model is TOLD it can call. Note this is data, not code — the model
# receives a description and answers with a name and some arguments. It has no
# reach into this process at all.
SCHEMAS = [
    {
        "name": "get_student",
        "description": "Look up a student by roll number.",
        "parameters": {
            "type": "object",
            "properties": {"roll_no": {"type": "string", "description": "e.g. CS22B007"}},
            "required": ["roll_no"],
        },
    },
    {
        "name": "get_fees",
        "description": "Check what a student owes and whether they are fee-blocked.",
        "parameters": {
            "type": "object",
            "properties": {"roll_no": {"type": "string", "description": "e.g. CS22B007"}},
            "required": ["roll_no"],
        },
    },
]

SYSTEM = "You triage college admin tickets. Look up the student's records before answering."
MAX_TURNS = 5
print("2 tools,", len(MINI), "students")
""")

md("""
### The loop

Written twice, because the two SDKs disagree about almost every noun:

| | Gemini | OpenAI |
|---|---|---|
| the model's request | `part.function_call` | `message.tool_calls` |
| your reply | a `user` turn of function responses | one `tool` message per call |
| arguments arrive as | a dict | a JSON **string** you must parse |

Same twenty lines, different vocabulary. **That difference is the entire
business case for a framework** — and in step 1 you will watch Agno collapse
both of these into one line.
""")

code("""
import json


def raw_loop_google(question: str) -> str:
    from google import genai  # `from google import genai` — NOT google.generativeai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM,
        tools=[types.Tool(function_declarations=SCHEMAS)],
        # The SDK will happily run your functions for you. We switch that off,
        # because doing it by hand is the entire point of this cell.
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        temperature=0.1,
    )

    # THE CONVERSATION. This list is the agent's entire memory. Watch it grow.
    contents = [types.Content(role="user", parts=[types.Part(text=question)])]

    for turn in range(1, MAX_TURNS + 1):
        print(f"-- turn {turn}: sending {len(contents)} message(s)")
        reply = client.models.generate_content(model="gemini-3.5-flash-lite", contents=contents, config=config)
        parts = reply.candidates[0].content.parts or []
        calls = [p.function_call for p in parts if p.function_call]

        if not calls:  # no tool calls == the model is done. The exit condition.
            print("   model is done")
            return reply.text or "(nothing)"

        contents.append(reply.candidates[0].content)  # or it forgets it asked
        results = []
        for call in calls:
            args = dict(call.args or {})
            print(f"   model wants: {call.name}({json.dumps(args)})")
            fn = IMPLEMENTATIONS.get(call.name)
            out = fn(**args) if fn else f"ERROR: no such tool {call.name!r}."
            print(f"   tool says:   {out[:90]}")
            results.append(types.Part.from_function_response(name=call.name, response={"result": out}))
        contents.append(types.Content(role="user", parts=results))

    return f"Gave up after {MAX_TURNS} turns."


def raw_loop_openai(question: str) -> str:
    from openai import OpenAI

    client = OpenAI()
    tools = [{"type": "function", "function": s} for s in SCHEMAS]
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]

    for turn in range(1, MAX_TURNS + 1):
        print(f"-- turn {turn}: sending {len(messages)} message(s)")
        reply = client.chat.completions.create(
            model="gpt-5.4-mini", messages=messages, tools=tools, temperature=0.1
        )
        msg = reply.choices[0].message

        if not msg.tool_calls:
            print("   model is done")
            return msg.content or "(nothing)"

        messages.append(msg)
        for call in msg.tool_calls:
            args = json.loads(call.function.arguments)  # a STRING here, not a dict
            print(f"   model wants: {call.function.name}({json.dumps(args)})")
            fn = IMPLEMENTATIONS.get(call.function.name)
            out = fn(**args) if fn else f"ERROR: no such tool {call.function.name!r}."
            print(f"   tool says:   {out[:90]}")
            messages.append({"role": "tool", "tool_call_id": call.id, "content": out})

    return f"Gave up after {MAX_TURNS} turns."


raw_loop = raw_loop_google if PROVIDER == "google" else raw_loop_openai

QUESTION = "Why can't CS22B007 download her hall ticket?"
print(f"[{PROVIDER}] {QUESTION}\\n")
print("\\nANSWER:", raw_loop(QUESTION))
""")

md("""
Read the turn markers. The first call sends one message and comes back asking
for a tool. You run it, append the result, and call again with three messages.
The model answers from what you gave it.

Four things in those twenty lines that every framework is quietly doing for
you, and which you now know are there:

1. **The conversation is a list you own.** Nothing is remembered for you. That
   list *is* the agent's memory, and every turn makes it longer — which is why
   a long agent run gets slower and dearer as it goes.
2. **`MAX_TURNS` is not a nicety.** Without it a confused agent loops until
   your quota is gone. Frameworks call this `tool_call_limit`.
3. **A hallucinated tool name is normal.** Tell the model rather than crashing
   and it usually recovers.
4. **One question cost several model calls.** Budget 5–15 per ticket, not one.
   This is the number people get wrong when estimating cost.

> **Try it:** set `MAX_TURNS = 1` and re-run. Then delete `get_fees` from
> `IMPLEMENTATIONS` but leave it in `SCHEMAS`, and watch the model ask for a
> tool that no longer exists.

Now — everything from here on is that loop, with the plumbing hidden.
""")

# ==========================================================================
# Step 1 — an agent
# ==========================================================================
md("""
---
# Step 1 — An agent
*The same loop, with the plumbing hidden.*

Everything you just wrote by hand — the message list, the tool dispatch, the
turn limit, the provider's particular vocabulary — is what the next three
lines replace.

This agent has a model and instructions and nothing else. No tools, no schema.
It cannot look anything up. Watch what it does anyway.
""")

code("""
from agno.agent import Agent

INSTRUCTIONS = [
    "You triage incoming student tickets for a college administration office.",
    "Your job is to decide who should handle a ticket and how urgently. "
    "You do not resolve the ticket yourself and you do not reply to the student.",
    "Route on the underlying cause, not the symptom the student describes. "
    "Students report where they noticed a problem, not where it lives.",
    "Judge urgency by consequences, not by tone. Capital letters are not an "
    "emergency; an exam on Monday is. Most tickets are 'normal'.",
]

agent_v1 = Agent(model=get_model(), instructions=INSTRUCTIONS)

TICKET = "I can't download my hall ticket, the portal shows an error. My exam is on Monday. Roll no CS22B007."

# run() + print, not agent.print_response(). print_response draws a live,
# self-refreshing panel with rich, and Colab's output does not support the
# cursor movement that needs — you get the spinner and the Message box, and
# the answer never appears. Looks like a hang; is a rendering bug.
print(agent_v1.run(TICKET).content)
""")

md("""
**Read that answer again before you are impressed by it.**

It is fluent. It named a department. It sounded certain.

It also has no way whatsoever to look up CS22B007 — no database, no tools — so
everything it said about that student, it made up.

Two separate problems, and the next two steps fix one each:

| Problem | Fixed by |
|---|---|
| The answer is prose, so no system can use it | Step 2 |
| The answer is invented, so nobody should trust it | Step 3 |

> ### One Colab gotcha, before you go exploring
>
> Agno's docs mostly show `agent.print_response(...)`, and it is lovely in a
> terminal. **It does not work in Colab.** It draws a self-refreshing panel
> with `rich.Live`, which needs cursor movement that Colab's output does not
> support — so you get the spinner and the Message box, and the answer never
> arrives. It looks exactly like a hang. It is not; the call usually finished.
>
> Use `agent.run(...)` and print the result, as above. Every cell in this
> notebook does.
""")

# ==========================================================================
# Step 2 — a contract
# ==========================================================================
md("""
---
# Step 2 — A contract
*Same wrong answer, now beautifully typed.*

Prose is useless to a system. You cannot route on it, count it, put it in a
queue, or write a test against it.

One parameter changes that: `output_schema`.
""")

code('''
from typing import Literal

from pydantic import BaseModel, Field


class TriageResult(BaseModel):
    """What every triage must produce. The field descriptions are not comments —
    the model reads them to decide what goes in each field."""

    department: Literal["accounts", "hostel", "examinations", "admissions", "it_support"] = Field(
        description="The team that OWNS the underlying cause, not the one the student named."
    )
    urgency: Literal["low", "normal", "high", "critical"] = Field(
        description="Judge by consequences, not tone. Most tickets are 'normal'."
    )
    summary: str = Field(description="Under 25 words, factual. Read by someone with 40 tickets.")
    student_id: str = Field(description="Roll number, or empty string if you could not establish it.")
    suggested_action: str = Field(description="The single next step for whoever picks this up.")
    needs_human: bool = Field(
        description=(
            "True when the ticket ASKS FOR something a person must authorise: a "
            "refund, a waiver, a policy exception, a released document, anything "
            "touching discipline or safety. Most tickets do not need a human."
        )
    )
    reasoning: str = Field(description="Why this department. Cite what you looked up.")


agent_v2 = Agent(model=get_model(), instructions=INSTRUCTIONS, output_schema=TriageResult)

result = agent_v2.run(TICKET).content
print(type(result).__name__, "\\n")
for field, value in result.model_dump().items():
    print(f"  {field:<18} {value}")
''')

md("""
That is a real Python object now. Validated by Pydantic, with a `department`
you could route on and a `needs_human` you could act on.

**It is also, almost certainly, wrong.**

CS22B007 is fee-blocked. The hall ticket is withheld by Accounts, not
Examinations. The agent has no way to know that, so it guessed from the words
in the ticket — and the schema wrapped that guess in something that looks
considerably more authoritative than the paragraph did.

> **Try it:** run the cell above twice. Does it even agree with itself?

Structure buys you parseability. It does not buy you truth.

### Two things worth knowing about schemas

**Keep them flat.** Gemini rejects large or deeply nested schemas with poor
error messages, and Agno has a bug where `Optional[X] = None` sometimes gets
marked required — intermittently, which is the worst way for anything to fail.
Primitives only, `Literal` rather than `Enum` (Literal inlines; Enum creates a
`$defs` entry), no Optionals. Use a required field with `""` as the unknown.

**The descriptions are prompt text.** Add a field with a good description and
the agent fills it in without being told to. Try adding
`estimated_days_to_resolve: int` and re-running.
""")

# ==========================================================================
# Step 3 — the data, then the tools
# ==========================================================================
md("""
---
# Step 3 — Tools
*It can finally look things up. Watch it change its mind.*

First the college's records. **These are ordinary Python dicts and you are
meant to edit them** — that is the experiment at the end of this step.

Twelve students. Note three of them:

- **CS22B007** — fee-blocked. This is why her hall ticket is withheld.
- **EC21B009** — fees fully paid, attendance 68%. Same symptom, different cause.
- **CS21B014** — paid by NEFT two days ago, portal still says pending. Nothing
  is wrong at all.
""")

code("""
STUDENTS = {
    "CS21B001": dict(name="Aarthi Balasubramanian", program="B.Tech Computer Science", year=4),
    "CS21B014": dict(name="Rohit Menon", program="B.Tech Computer Science", year=4),
    "CS22B007": dict(name="Priya Nair", program="B.Tech Computer Science", year=3),
    "EC22B031": dict(name="Imran Sheikh", program="B.Tech Electronics", year=3),
    "ME23B019": dict(name="Divya Rangan", program="B.Tech Mechanical", year=2),
    "CS23B044": dict(name="Karthik Subramani", program="B.Tech Computer Science", year=2),
    "EC21B009": dict(name="Sneha Iyer", program="B.Tech Electronics", year=4),
    "CE22B012": dict(name="Anand Prakash", program="B.Tech Civil", year=3),
    "ME21B027": dict(name="Vikram Deshpande", program="B.Tech Mechanical", year=4),
    "EE23B005": dict(name="Joseph Mathew", program="B.Tech Electrical", year=2),
}

# status: paid | pending | overdue | blocked   ("blocked" withholds hall tickets)
FEES = {
    "CS21B001": dict(due=92000, paid=92000, status="paid", ref="TXN8841207", date="2025-07-11"),
    "CS21B014": dict(due=92000, paid=92000, status="pending", ref="NEFT5520933", date="2025-08-13"),
    "CS22B007": dict(due=88000, paid=0, status="blocked", ref="", date=""),
    "EC22B031": dict(due=88000, paid=88000, status="paid", ref="TXN8839114", date="2025-07-02"),
    "ME23B019": dict(due=85000, paid=85000, status="paid", ref="TXN8840556", date="2025-07-09"),
    "CS23B044": dict(due=85000, paid=40000, status="overdue", ref="TXN8842001", date="2025-07-14"),
    "EC21B009": dict(due=92000, paid=92000, status="paid", ref="TXN8838770", date="2025-06-28"),
    "CE22B012": dict(due=88000, paid=88000, status="paid", ref="TXN8841855", date="2025-07-13"),
    "ME21B027": dict(due=92000, paid=92000, status="paid", ref="TXN8837233", date="2025-06-20"),
    "EE23B005": dict(due=85000, paid=85000, status="paid", ref="TXN8841440", date="2025-07-12"),
}

# status: allotted | waiting_list | day_scholar
HOSTEL = {
    "CS21B001": dict(status="allotted", room="A-214", mess="veg_monthly"),
    "CS21B014": dict(status="allotted", room="A-108", mess="non_veg_monthly"),
    "CS22B007": dict(status="allotted", room="B-301", mess="veg_monthly"),
    "EC22B031": dict(status="waiting_list", room="", mess=""),
    "ME23B019": dict(status="allotted", room="C-117", mess="veg_monthly"),
    "CS23B044": dict(status="day_scholar", room="", mess=""),
    "EC21B009": dict(status="allotted", room="B-209", mess="veg_monthly"),
    "CE22B012": dict(status="allotted", room="C-042", mess="non_veg_monthly"),
    "ME21B027": dict(status="day_scholar", room="", mess=""),
    "EE23B005": dict(status="waiting_list", room="", mess=""),
}

# hall_ticket: released | withheld_fees | withheld_attendance
EXAMS = {
    "CS21B001": dict(attendance=88, hall_ticket="released", backlogs=0),
    "CS21B014": dict(attendance=91, hall_ticket="released", backlogs=0),
    "CS22B007": dict(attendance=82, hall_ticket="withheld_fees", backlogs=1),
    "EC22B031": dict(attendance=79, hall_ticket="released", backlogs=0),
    "ME23B019": dict(attendance=94, hall_ticket="released", backlogs=0),
    "CS23B044": dict(attendance=76, hall_ticket="released", backlogs=2),
    "EC21B009": dict(attendance=68, hall_ticket="withheld_attendance", backlogs=1),
    "CE22B012": dict(attendance=85, hall_ticket="released", backlogs=0),
    "ME21B027": dict(attendance=81, hall_ticket="released", backlogs=3),
    "EE23B005": dict(attendance=89, hall_ticket="released", backlogs=0),
}

print(len(STUDENTS), "students loaded")
""")

md(f"""
### The policy documents

These are fetched rather than pasted — 350 lines of policy markdown is data,
and pasting it here would bury the code you are supposed to be reading.

Source: [`src/college_agent/kb/`]({REPO}/tree/main/src/college_agent/kb)
""")

code(f'''
import urllib.request

DOCS = ["fees", "hostel", "examinations", "admissions", "it_support", "triage_guidelines"]
KB = {{}}
for name in DOCS:
    KB[name] = urllib.request.urlopen(f"{RAW}/{{name}}.md").read().decode("utf-8")

print(f"{{len(KB)}} policy documents, {{sum(len(v.split()) for v in KB.values())}} words")
print("\\n".join(f"  {{n}}: {{KB[n].splitlines()[0].lstrip('# ')}}" for n in DOCS))
''')

md("""
### The six tools

**A tool is a normal Python function.** The model never runs your code — it
only asks you to, by name, with arguments. Your code decides whether to
comply. Say that out loud too; most people have never had the security model
stated plainly.

Three rules visible in what follows:

**The docstring is prompt text.** Agno turns the signature and docstring into
the schema the model reads. "Look up a student" is weak; *"call this first
whenever a roll number is mentioned"* tells it about **timing**, which is the
thing models are genuinely bad at.

**Never raise for an ordinary miss.** An exception ends the loop. A returned
sentence lets the agent recover — and can steer it: *"do not guess another
roll number."*

**Put domain knowledge in the output.** `check_fee_status` does not just
return a balance. It says a pending NEFT inside three working days is normal.
That one sentence stops the agent escalating a non-problem, and it belongs
there rather than in the prompt because it is a fact *about the data*.
""")

code('''
def lookup_student(roll_no: str) -> str:
    """Look up a student's basic record by roll number.

    Call this FIRST whenever a roll number is mentioned, before deciding
    anything else.

    Args:
        roll_no: Roll number, e.g. "CS21B001". Case-insensitive.
    """
    roll_no = roll_no.strip().upper()
    s = STUDENTS.get(roll_no)
    if not s:
        # A sentence, not an exception. The agent can recover from this.
        return (
            f"No student found with roll number {roll_no!r}. "
            "Do not guess another roll number - ask the student to confirm it."
        )
    return f"{roll_no}: {s['name']}, {s['program']}, year {s['year']}."


def check_fee_status(roll_no: str) -> str:
    """Check what a student owes and whether they are fee-blocked.

    Use this for ANY question about fees, payments, refunds, or a hall ticket
    or transcript that is being withheld.

    Args:
        roll_no: Roll number, e.g. "CS21B001".
    """
    roll_no = roll_no.strip().upper()
    f = FEES.get(roll_no)
    if not f:
        return f"No fee record for {roll_no!r}."

    out = [
        f"{roll_no} fees: due Rs.{f['due']:,}, paid Rs.{f['paid']:,}, "
        f"outstanding Rs.{f['due'] - f['paid']:,}. Status: {f['status']}."
    ]
    if f["ref"]:
        out.append(f"Last payment {f['ref']} on {f['date']}.")
    else:
        out.append("No payment recorded.")

    # The single most common false alarm at the accounts desk.
    if f["status"] == "pending" and f["ref"].startswith(("NEFT", "IMPS")):
        out.append(
            "NOTE: bank transfers take 2-3 working days to reconcile. A 'pending' "
            "status inside that window is expected and usually means nothing is wrong."
        )
    if f["status"] == "blocked":
        out.append(
            "NOTE: this student is FEE-BLOCKED. Hall tickets and transcripts are "
            "withheld until the balance is cleared."
        )
    return " ".join(out)


def check_exam_status(roll_no: str) -> str:
    """Check attendance, hall ticket status and backlogs.

    Use this whenever a hall ticket, attendance, results or revaluation is
    mentioned. It tells you WHY a hall ticket is withheld, which is usually
    not an examinations problem at all.

    Args:
        roll_no: Roll number, e.g. "CS21B001".
    """
    roll_no = roll_no.strip().upper()
    e = EXAMS.get(roll_no)
    if not e:
        return f"No examination record for {roll_no!r}."

    out = [f"{roll_no}: attendance {e['attendance']}%, backlogs {e['backlogs']}."]
    if e["hall_ticket"] == "withheld_fees":
        out.append(
            "Hall ticket WITHHELD because of unpaid fees. This is an ACCOUNTS "
            "matter - examinations cannot release it until the fee block clears."
        )
    elif e["hall_ticket"] == "withheld_attendance":
        out.append(
            f"Hall ticket WITHHELD because attendance is {e['attendance']}%, below "
            "the 75% requirement. This is an EXAMINATIONS matter, not a fee problem."
        )
    else:
        out.append("Hall ticket released.")
    return " ".join(out)


def check_hostel_status(roll_no: str) -> str:
    """Check hostel allotment, room and mess plan.

    Args:
        roll_no: Roll number, e.g. "CS21B001".
    """
    roll_no = roll_no.strip().upper()
    h = HOSTEL.get(roll_no)
    if not h:
        return f"No hostel record for {roll_no!r}."

    if h["status"] == "waiting_list":
        # A policy that conflicts with being helpful. Models are trained to be
        # helpful, so this is genuinely hard for them.
        return (
            f"{roll_no} is on the hostel waiting list. Position on the waiting list "
            "is NOT disclosed to students - it changes daily. Do not state or "
            "estimate a position. The student is contacted if a room opens."
        )
    if h["status"] == "day_scholar":
        return f"{roll_no} is a day scholar - no hostel allotment."
    return f"{roll_no}: room {h['room']}, mess plan {h['mess']}. Mess charges are monthly and non-refundable once the month begins."


def search_policy(query: str) -> str:
    """Search the college policy documents.

    Use this when the answer depends on a rule, a deadline, an amount or a
    procedure. Do NOT answer policy questions from memory - quote the policy.

    Args:
        query: What you want to know, e.g. "refund on withdrawal".
    """
    words = [w for w in query.lower().split() if len(w) > 3]
    hits = []
    for doc, text in KB.items():
        for section in text.split("\\n## "):
            score = sum(section.lower().count(w) for w in words)
            if score:
                hits.append((score, doc, section.strip()[:700]))
    if not hits:
        return f"Nothing in the policy documents matches {query!r}. Do not invent a policy."
    hits.sort(reverse=True)
    return "\\n\\n---\\n\\n".join(f"[{doc}]\\n{text}" for _, doc, text in hits[:3])


DEPARTMENTS = ["accounts", "hostel", "examinations", "admissions", "it_support"]


def create_ticket(roll_no: str, message: str, department: str, urgency: str) -> str:
    """File the triaged ticket with a department.

    Call this LAST, once you have decided.

    Args:
        roll_no: Roll number, or "" if unknown.
        message: The student's original message.
        department: One of accounts, hostel, examinations, admissions, it_support.
        urgency: One of low, normal, high, critical.
    """
    if department not in DEPARTMENTS:
        # Validate on the way in and say what is valid, so the agent can
        # correct itself instead of failing.
        return f"Rejected: {department!r} is not a department. Use one of: {', '.join(DEPARTMENTS)}."
    if urgency not in ("low", "normal", "high", "critical"):
        return f"Rejected: {urgency!r} is not an urgency. Use low, normal, high or critical."
    return f"Ticket filed with {department} at {urgency} urgency for {roll_no or 'unidentified student'}."


TOOLS = [
    lookup_student,
    check_fee_status,
    check_exam_status,
    check_hostel_status,
    search_policy,
    create_ticket,
]
print(len(TOOLS), "tools ready")
''')

md("""
Six sharp tools beat fifteen vague ones. Most tool-selection errors come from
a model choosing plausibly among too many options.

Now the same agent, same instructions, same ticket — with tools.
""")

code("""
INSTRUCTIONS_V3 = INSTRUCTIONS + [
    "If the ticket mentions a roll number, look the student up first. Their actual "
    "fee, hostel and examination records settle the question faster than re-reading "
    "the message does.",
    "Check the records before you check the policy. A student who says their fees "
    "are pending may simply be inside the bank reconciliation window - the fee "
    "record will tell you, the policy will not.",
    "Never invent a roll number, an amount, a date or a policy.",
]

agent_v3 = Agent(
    model=get_model(),
    instructions=INSTRUCTIONS_V3,
    tools=TOOLS,
    output_schema=TriageResult,
    # A hard stop. Without a limit a confused agent will happily call tools
    # until your free-tier quota is gone.
    tool_call_limit=10,
    add_datetime_to_context=True,
)

response = agent_v3.run(TICKET)
print("tools called:", [t.tool_name for t in (response.tools or [])], "\\n")
for field, value in response.content.model_dump().items():
    print(f"  {field:<18} {value}")
""")

md("""
**`accounts`, not `examinations`.** The student said "hall ticket"; the cause
was a fee block. Nothing in the prompt could have resolved that — it had to
look at the record.

This is the most transferable lesson in the workshop:

| The student says | It belongs to | Because |
|---|---|---|
| "can't download my hall ticket" | **accounts** | fee block |
| "can't download my hall ticket" | **examinations** | attendance under 75% |
| "portal says my fees are pending" | **accounts** | the portal is only a view |
| "can't log in at all" | **it_support** | that really is IT |

The first two are the **same sentence** with different causes.
""")

# ==========================================================================
# The experiment
# ==========================================================================
md("""
---
## 🔬 The experiment: change the data, change the answer

This is the bit you cannot do from a slide deck.

CS22B007 is fee-blocked, so her ticket routes to **accounts**. Below, we clear
her fees and release her hall ticket — changing *nothing* about the prompt,
the tools or the model — and ask the identical question again.
""")

code("""
import copy

before = copy.deepcopy(FEES["CS22B007"]), copy.deepcopy(EXAMS["CS22B007"])

print("BEFORE")
print("  tool says :", check_exam_status("CS22B007"))
print("  agent says:", agent_v3.run(TICKET).content.department)

# She has now paid, but her attendance has slipped. Same student, same ticket
# text, different world.
FEES["CS22B007"] = dict(due=88000, paid=88000, status="paid", ref="TXN9001234", date="2025-08-14")
EXAMS["CS22B007"] = dict(attendance=62, hall_ticket="withheld_attendance", backlogs=1)

after = agent_v3.run(TICKET).content
print("\\nAFTER")
print("  tool says :", check_exam_status("CS22B007"))
print("  agent says:", after.department)
print("  reasoning :", after.reasoning)
""")

md("""
Read the two `tool says` lines first. That is ground truth, and it changed the
instant the dict did — no model involved.

Then the two `agent says` lines. Same words from the student, different
department, because the agent **looked** instead of guessing.

An agent that had pattern-matched on the phrase "hall ticket" would have given
you the identical answer both times, and you would have had no way to tell.
That is what the tool line is there to prove.

> If both `agent says` lines match but the `tool says` lines differ, your agent
> is not reading its tools properly — and you have just found a real bug the
> only way anyone ever finds it.

> **Now you try.** Some things worth breaking:
> - Set `FEES["CS21B014"]["status"] = "blocked"` and re-run the NEFT ticket.
> - Delete `check_exam_status` from `TOOLS`, rebuild `agent_v3`, and watch it
>   guess again — confidently.
> - Change a tool's **docstring** and watch tool choice change. The docstring
>   is the prompt.
""")

code("""
# Put the world back before continuing.
FEES["CS22B007"], EXAMS["CS22B007"] = before
print("restored:", check_exam_status("CS22B007"))
""")

# ==========================================================================
# Step 4 — guardrails
# ==========================================================================
md("""
---
# Step 4 — Guardrails
*The difference between “please don't” and “you can't”.*

You could add an instruction: *"refuse requests about somebody else's
records."* The agent would usually obey.

**Usually is not a security property.** An instruction is advice; a guardrail
is a rule. A guardrail runs *before* the model, so it cannot be argued out of,
behaves identically on the thousandth ticket, and costs zero tokens.
""")

code('''
import re

from agno.exceptions import CheckTrigger, InputCheckError
from agno.guardrails import BaseGuardrail
from agno.run.agent import RunInput

THIRD_PARTY = [
    re.compile(r"\\bI am\\b.{0,40}\\b(father|mother|parent|guardian|brother|sister)\\b", re.I),
    re.compile(r"\\b(my|his|her)\\s+(son|daughter|child|ward)\\b", re.I),
    re.compile(r"\\bon behalf of\\b", re.I),
    re.compile(r"\\bsend me\\b.{0,40}\\b(his|her|their)\\b", re.I),
]

REFUSAL = (
    "This looks like a request about someone else's records. Student records are "
    "released only to the student, so this needs a human and cannot be answered "
    "automatically."
)


class ThirdPartyRequestGuardrail(BaseGuardrail):
    """Refuse requests for a student's records from anyone who is not that student."""

    def check(self, run_input: RunInput) -> None:
        text = str(run_input.input_content or "")
        if any(p.search(text) for p in THIRD_PARTY):
            raise InputCheckError(REFUSAL, check_trigger=CheckTrigger.INPUT_NOT_ALLOWED)

    async def async_check(self, run_input: RunInput) -> None:
        self.check(run_input)


GUARDRAILS = [ThirdPartyRequestGuardrail()]

agent_v4 = Agent(
    model=get_model(),
    instructions=INSTRUCTIONS_V3,
    tools=TOOLS,
    output_schema=TriageResult,
    tool_call_limit=10,
    add_datetime_to_context=True,
    # Runs BEFORE the model. Zero tokens spent on a refused ticket.
    pre_hooks=GUARDRAILS,
)


def enforce(text):
    """Run the guardrails ourselves, before the agent gets involved."""
    for g in GUARDRAILS:
        g.check(RunInput(input_content=text))


def as_result(content):
    """Narrow whatever `.content` turned out to be into a TriageResult.

    `.content` is a TriageResult on a good day and a plain `str` on a bad one,
    and the two are indistinguishable until something downstream says

        AttributeError: 'str' object has no attribute 'department'

    at a line that has nothing to do with the cause. One place decides what
    counts as a valid answer, so nobody has to remember to check.
    """
    if isinstance(content, str):
        # Some paths hand back the right JSON as *text* — a Team leader
        # answering directly is the one you will actually meet. If it
        # validates, take it; the contract is satisfied even though the
        # plumbing was lazy about it.
        try:
            return TriageResult.model_validate_json(content)
        except Exception:
            pass
    if not isinstance(content, TriageResult):
        raise RuntimeError(f"Not a TriageResult: {str(content)[:200]}")
    return content


def triage(text):
    """The ONLY way to run this agent. Returns a TriageResult or raises."""
    enforce(text)
    return as_result(agent_v4.run(text).content)


FATHER = "I am Rohit Menon's father. Please send me his attendance record and exam results."

try:
    triage(FATHER)
    print("NOT BLOCKED - the guardrail let it through")
except InputCheckError as refusal:
    print("BLOCKED before a single token was spent")
    print(" ", refusal)
''')

md("""
Note *before a single token was spent*. On a free tier that matters, but the
real point is that this outcome does not depend on the model's mood, the
phrasing of the request, or how sympathetic the person asking sounds.

> ### The trap in that cell, which cost this project an afternoon
>
> `pre_hooks` does **not** raise out of `agent.run()`. Agno catches the
> `InputCheckError`, logs it, and hands you the refusal as `.content` — as a
> plain **`str`**, where you were expecting a `TriageResult`.
>
> So `run()` returning normally does not mean the guardrail let it through,
> and the failure surfaces far away as
> `AttributeError: 'str' object has no attribute 'department'`.
>
> That is why `enforce()` and `triage()` exist above: one place that checks
> the guardrails itself and narrows the result, so callers get a
> `TriageResult` or a typed exception and never a surprise string. Everything
> after this point goes through `triage()`.

> **Try it:** how would you word a request that gets past those four regexes?
> That question is the actual job — and the reason real systems layer a
> guardrail *and* an instruction, rather than choosing.
""")

# ==========================================================================
# Step 5 — team
# ==========================================================================
md("""
---
# Step 5 — One agent, or several
*Roughly double the bill. Was it worth it?*

The standard next move is to split into specialists with a router in front.
Each specialist gets a shorter prompt and fewer tools, which measurably
improves tool choice.

It also **doubles your model calls** — the router runs, then a specialist runs.
This is a comparison, not an upgrade.
""")

code("""
from agno.team import Team
from agno.team.mode import TeamMode


def specialist(name, role, tools):
    return Agent(
        name=name,
        model=get_model(),
        instructions=[role, "Return a TriageResult. Look up records before deciding."],
        tools=tools,
        output_schema=TriageResult,
        tool_call_limit=6,
    )


team = Team(
    name="Triage team",
    model=get_model(),
    members=[
        specialist("Accounts", "You handle fees, payments, refunds and fee-blocked documents.",
                   [lookup_student, check_fee_status, search_policy]),
        specialist("Examinations", "You handle hall tickets, attendance, results and revaluation.",
                   [lookup_student, check_exam_status, search_policy]),
        specialist("Hostel", "You handle rooms, allotment, waiting lists and mess billing.",
                   [lookup_student, check_hostel_status, search_policy]),
    ],
    mode=TeamMode.route,
    instructions=[
        "Pick the ONE specialist who owns the underlying cause, not the symptom.",
        "A withheld hall ticket caused by unpaid fees belongs to Accounts.",
    ],
    # The members each have this, but the TEAM needs it too. Without it the
    # leader returns the right JSON as a *string* and everything downstream
    # breaks on `.department`. This repo shipped that bug once.
    output_schema=TriageResult,
)

import time

# as_result(), not .content — a routing leader is the single most likely
# thing in this notebook to hand you the right JSON as a plain string.
t0 = time.time(); solo = as_result(agent_v3.run(TICKET).content); solo_s = time.time() - t0
t1 = time.time(); grp = as_result(team.run(TICKET).content); grp_s = time.time() - t1

print(f"single agent  {solo.department:<14} {solo_s:.1f}s")
print(f"routing team  {grp.department:<14} {grp_s:.1f}s")
print(f"\\nsame answer: {solo.department == grp.department}   team took {grp_s / max(solo_s, 0.01):.1f}x as long")
""")

md("""
Ask honestly: did the team do **better**, or just cost more?

For this problem — six tools, one clear domain — a single agent is usually
enough. Split when you can name the failure a split would fix, normally *"it
keeps picking the wrong tool"* or *"two teams need to own two halves of this"*.

Splitting because the architecture diagram looks more serious gives you a
system that is slower, dearer and harder to debug, in exchange for nothing.
""")

# ==========================================================================
# Step 6 — evals
# ==========================================================================
md("""
---
# Step 6 — Proving it works
*Stop trusting your eyes. Start counting.*

Everything so far, you judged by reading. That does not scale and it does not
survive a prompt change.

**A golden dataset is the most valuable and least impressive-looking thing you
will build.** Each case encodes a *specific* way triage goes wrong — not
tickets sampled from a queue, because a real queue is mostly easy cases your
agent passes by accident.
""")

code("""
CASES = [
    dict(
        name="hall_ticket_blocked_by_fees",
        ticket="I can't download my hall ticket, the portal shows an error. My exam is on Monday. Roll no CS22B007.",
        department="accounts", needs_human=True, must_call="check_exam_status",
        why="Symptom says examinations, cause is a fee block. And the exam is Monday, so somebody has to own it.",
    ),
    dict(
        name="hall_ticket_blocked_by_attendance",
        ticket="My fees are fully paid but I still can't get my hall ticket. This is unfair. Roll no EC21B009.",
        department="examinations", needs_human=False, must_call="check_exam_status",
        why="Same symptom as case 1, different cause. An agent using a shortcut fails exactly one of these two.",
    ),
    dict(
        name="neft_reconciliation_window",
        ticket="Paid my fees by NEFT on the 13th, portal still says pending. Roll no CS21B014.",
        department="accounts", needs_human=False, must_call="check_fee_status",
        why="Nothing is wrong. Escalating this costs a human their time for no reason.",
    ),
    dict(
        name="waiting_list_position_withheld",
        ticket="What number am I on the hostel waiting list? Roll no EC22B031.",
        department="hostel", needs_human=False, must_call="check_hostel_status",
        why="Policy forbids the helpful answer. Models are trained to be helpful, so this is genuinely hard.",
    ),
    dict(
        name="refund_needs_human",
        ticket="I'm withdrawing from the programme this week and would like a full refund of my semester fees. Roll no ME21B027.",
        department="accounts", needs_human=True, must_call="search_policy",
        why="Money movement. Always a human, however clear the policy looks.",
    ),
]
print(len(CASES), "golden cases")
""")

md("""
### Scoring

Two checks, and the order matters — cheapest and most certain first.

**Did it look things up?** Free, deterministic, no judge. An agent that gets
the right department without ever checking the record got lucky, and luck does
not survive a rewording.

**Did it get the fields right?** `department` is a `Literal` and `needs_human`
is a `bool`. Compare them with `==`. Never ask a language model whether `True`
is `True` — that is slower, costs money, and introduces a component that can
disagree with you for no reason.

A judge is for what neither of those can check — *did it avoid promising a
refund* — and it is the least reliable thing in your suite. Use it last and
sparingly.
""")

code("""
def evaluate(agent, cases=CASES):
    rows, passed = [], 0
    for c in cases:
        run = agent.run(c["ticket"])
        got = as_result(run.content)
        called = [t.tool_name for t in (run.tools or [])]

        ok_dept = got.department == c["department"]
        ok_human = got.needs_human == c["needs_human"]
        ok_tool = c["must_call"] in called
        good = ok_dept and ok_human and ok_tool
        passed += good

        rows.append((c["name"], got.department, ok_dept, got.needs_human, ok_human, ok_tool, good))

    w = max(len(r[0]) for r in rows) + 2
    print(f"{'case':<{w}}{'dept':<16}{'human':<8}{'tools':<8}")
    print("-" * (w + 32))
    for name, dept, ok_d, human, ok_h, ok_t, good in rows:
        mark = lambda ok: "ok " if ok else "FAIL"
        print(f"{name:<{w}}{dept + ' ' + mark(ok_d):<16}{str(human) + ' ' + mark(ok_h):<8}{mark(ok_t):<8}")
    print(f"\\n{passed}/{len(cases)} passed")
    return passed


evaluate(agent_v3)
""")

md("""
### Now break it on purpose

An eval suite that never fails is decoration. Delete the one instruction that
does the most work and watch the score move.
""")

code("""
# Same model, same tools. One sentence removed.
crippled = Agent(
    model=get_model(),
    instructions=[i for i in INSTRUCTIONS_V3 if "underlying cause" not in i],
    tools=TOOLS,
    output_schema=TriageResult,
    tool_call_limit=10,
    add_datetime_to_context=True,
)

print("WITHOUT the 'route on the underlying cause' instruction:\\n")
evaluate(crippled)
""")

md("""
If the score dropped, your suite is doing its job. If it did not move, the
suite is not measuring what you think it is — and *that* is the finding.

> **The lesson people actually take home:** every judgement field needs a
> **base rate**. When this agent was first run for real, `urgency` had one
> (*"most tickets are normal"*) and behaved; `needs_human` had none and
> escalated four tickets out of five. Same model, same run, opposite outcomes.
> A flag that is true 80% of the time carries no information.
>
> Try it: add *"most tickets do not need a human"* to the instructions and
> re-run the eval.
""")

md("""
### The other axis: a weaker model

You just degraded the *prompt*. The other thing people reach for is a
*cheaper model* — usually to save money, sometimes without measuring what it
costs them.

Same eval, same tools, same instructions. Only the model changes.

> **This may not fail.** Nobody can tell you in advance whether a smaller
> model is good enough for *your* task — that is the entire reason you built
> the eval. If the weak model matches the strong one here, you have learned
> something worth more than a dramatic demo: this task does not need the
> expensive model, and you can stop paying for it.
""")

code("""
# Older, smaller, cheaper. Model IDs get retired — the cell tries these in
# order and uses the first one the provider still answers on.
CANDIDATES = {
    "google": ["gemini-2.5-flash-lite", "gemini-2.0-flash-lite", "gemini-2.0-flash"],
    "openai": ["gpt-4o-mini", "gpt-3.5-turbo"],
}[PROVIDER]


def weak_agent():
    for candidate in CANDIDATES:
        try:
            # Probe with a BARE agent - no schema, no tools. Asking a weak
            # model for a TriageResult here would fail validation and get a
            # perfectly available model written off as retired.
            Agent(model=get_model(model_id=candidate)).run("Say ok")
        except Exception as exc:
            print(f"  {candidate}: unavailable ({str(exc)[:70]})")
            continue

        print(f"using {candidate}\\n")
        return Agent(
            model=get_model(model_id=candidate),
            instructions=INSTRUCTIONS_V3,
            tools=TOOLS,
            output_schema=TriageResult,
            tool_call_limit=10,
            add_datetime_to_context=True,
        )
    return None


weak = weak_agent()

if weak is None:
    print("\\nNo weaker model available. Pick one from your provider's model list")
    print("and add it to CANDIDATES - the comparison is worth doing.")
else:
    try:
        score = evaluate(weak)
        print(f"\\nweak model {score}/{len(CASES)}   vs   strong model 5/5 above")
    except RuntimeError as exc:
        # A model too weak to hold the schema at all. That IS the result.
        print(f"\\nIt could not produce a valid TriageResult at all:\\n  {exc}")
        print("\\nThat is not a crash, it is the finding. Structured output is a")
        print("capability, not a given, and it is the first thing to go.")
""")

md("""
Three things can happen there, and each teaches something different:

**It scores worse.** The usual outcome, and look at *how* it fails. Weak models
mostly do not fail by reasoning badly — they fail by **not looking**. Watch the
`tools` column: an agent that skips `check_exam_status` and answers from the
words in the ticket is guessing, and the reliability check catches that even
when the guess happens to be right.

**It cannot produce the schema at all.** Structured output is a capability, not
a given, and on small models it is the first thing to go. You will get a clean
`RuntimeError` from `as_result()` rather than a mystery, which is the payoff
for having written that function in step 4.

**It matches the strong model.** Then stop paying for the expensive one. This
is the outcome nobody demos and everybody should want — and you can only ever
know it by measuring.

> The general shape: **pick the cheapest model that passes your evals, not the
> best model you can afford.** Those are different questions, and only one of
> them has an answer you can check.
""")

# ==========================================================================
# Step 7 — serve
# ==========================================================================
md("""
---
# Step 7 — Shipping it
*Something someone else can actually call.*

An agent nobody can call is a notebook. Three status codes carry the whole
design:

| Code | Meaning |
|---|---|
| **200** | triaged |
| **403** | a guardrail refused it — not a failure, a decision |
| **502** | the provider broke — not the caller's fault |

And a `/health` endpoint that **never calls the model**. A health check that
costs a model call is a health check that fails under load and bills you for
the privilege.
""")

code("""
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

app = FastAPI(title="College triage")


@app.get("/health")
def health():
    # Deliberately no model call. Cheap, instant, honest.
    return {"status": "ok", "provider": PROVIDER}


@app.post("/triage")
def triage_endpoint(body: dict):
    # NOT named `triage` — that is the helper from step 4, and a route function
    # with the same name silently rebinds it. The endpoint then calls itself,
    # every request lands in the 502 branch, and the traceback points at
    # FastAPI. Cost me a debugging round; naming it differently costs nothing.
    message = (body.get("message") or "").strip()
    if not message:
        raise HTTPException(status_code=422, detail="message must not be empty")
    try:
        # triage(), not agent_v4.run(...) — see step 4. Going direct is how
        # this endpoint returns 502 for a refusal it should answer 403 to.
        return triage(message).model_dump()
    except InputCheckError as refusal:
        raise HTTPException(status_code=403, detail=str(refusal))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"provider failed: {exc}")


client = TestClient(app)

print("GET  /health ->", client.get("/health").json())
print("POST /triage (third party) ->", client.post("/triage", json={"message": FATHER}).status_code)
print("POST /triage (empty)       ->", client.post("/triage", json={"message": ""}).status_code)
r = client.post("/triage", json={"message": TICKET})
print("POST /triage (real)        ->", r.status_code, r.json()["department"])
""")

# ==========================================================================
# The repo
# ==========================================================================
md(f"""
---
# What a notebook can't show you

You have built the whole thing. What is missing is everything that makes it
survive contact with other people.

The repo has it: **[{REPO.split("/")[-2]}/{REPO.split("/")[-1]}]({REPO})**

- **`tests/`** — 142 tests that run with **no API key**. Tools, schema shape,
  guardrails, service behaviour. Fast, free, deterministic.
- **`.github/workflows/ci.yml`** — two tiers. Tests and lint on every push
  with no key; the real agent against the golden dataset only when a key is
  configured. Be clear-eyed about what the first tier proves: *the plumbing
  works, not that the agent reasons well.*
- **`Dockerfile`** — the same service, in a container, starting healthy
  without a key and saying so rather than crash-looping.
- **The seven `step-*` branches** — this same journey as one commit per
  concept, where `git diff step-2-structured step-3-tools` is the lesson.

Have a look at the two files that matter most:
""")

code(f"""
!git clone -q --depth 1 {REPO}.git /content/agent-demo 2>/dev/null; echo "cloned"
!echo "--- Dockerfile ---"; head -30 /content/agent-demo/Dockerfile
!echo; echo "--- CI: what runs with no key ---"; sed -n '/^  checks:/,/^  docker:/p' /content/agent-demo/.github/workflows/ci.yml | head -40
""")

md(f"""
---
# Take one thing away

**If you can write the `if` statement, write the `if` statement.**

Most production "agents" should have been three functions and a `match`. The
parts of today that did the real work were barely AI at all: a schema, six
tools with carefully written docstrings, two regexes, and five test cases that
disagreed with us.

The model was the easy bit. It is also the bit you control least.

### Keep going

- Add a case to `CASES` that the agent gets **wrong**. Much harder than one it
  gets right, and much more useful.
- Add a seventh tool and a case that needs it.
- Add a field to `TriageResult` and re-run — the agent fills it in unasked,
  because the field description *is* the instruction.
- Run the whole notebook against the other provider and see what changes.

> **Colab sessions are temporary.** Anything you changed here disappears when
> the runtime recycles. *File → Save a copy in Drive* if you want to keep it.

Repo: **{REPO}** · the branch-by-branch version is
`notebooks/workshop_branches.ipynb`.
""")


def main() -> int:
    # Every code cell must at least parse. An escape that loses a backslash on
    # its way into the JSON produces a cell that looks fine in the diff and
    # fails the moment a student runs it — which is the worst place to find out.
    for n, (kind, text) in enumerate(CELLS, 1):
        if kind != "code":
            continue
        body = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith(("%", "!")))
        try:
            compile(body, f"<cell {n}>", "exec")
        except SyntaxError as exc:
            raise SystemExit(f"cell {n} does not parse: {exc}") from None

    nb = {
        "nbformat": 4,
        "nbformat_minor": 0,
        "metadata": {
            "colab": {"provenance": [], "toc_visible": True},
            "kernelspec": {"name": "python3", "display_name": "Python 3"},
            "language_info": {"name": "python"},
        },
        "cells": [
            {
                "cell_type": kind,
                "metadata": {},
                "source": text.splitlines(True),
                **({"execution_count": None, "outputs": []} if kind == "code" else {}),
            }
            for kind, text in CELLS
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n")
    n_code = sum(1 for k, _ in CELLS if k == "code")
    print(f"wrote {OUT.name}: {len(CELLS)} cells ({n_code} code, {len(CELLS) - n_code} markdown)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
