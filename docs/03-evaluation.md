# Module 3 — Agent Evaluation

**30 minutes theory · 30 minutes lab**

> **Lab:** `make lab3`

---

## The problem

You built an agent. You tried five tickets. They looked right.

**You have no idea whether it works.**

That isn't a criticism of your five tickets — it's a structural problem:

- A language model is **non-deterministic**. The same input can produce
  different outputs. Your five passes might have been five coin flips.
- You chose tickets you were thinking about, which are the ones your prompt
  already handles.
- Changing one word of a prompt can change behaviour on inputs you never tried,
  and nothing will tell you.
- There is no type system, no compiler, and no stack trace. A broken agent
  produces *fluent, confident, wrong* output that looks exactly like working
  output.

That last point is the one that gets people. When a normal program breaks, it
crashes. When an agent breaks, it writes you a paragraph.

---

## Three things worth measuring

### 1. Reliability — did it do the work?

**Did it call the tools this question requires?**

Free, instant, deterministic, no second model involved. Start here.

It catches a failure that accuracy scoring cannot see: an agent that produces
the right answer without looking anything up. Ask about a hall ticket and
"accounts" is a reasonable guess. It scores a point. Then you reword the
ticket and it collapses — because it was never reasoning, it was
pattern-matching on your phrasing.

You cannot detect that by reading outputs. That's exactly why it gets missed.

```python
ReliabilityEval(
    agent_response=response,
    expected_tool_calls=["check_exam_status"],
    allow_additional_tool_calls=True,   # don't over-specify the path
)
```

Specify the **minimum** the agent must look up, not the exact sequence. There's
usually more than one reasonable route to a right answer, and pinning the route
makes the eval brittle without making it stricter in any way that matters.

### 2. Accuracy — was it right?

Two ways, and the difference between them is the point.

**Exact match.** Did `department` equal what you expected? Free, instant,
completely objective — and blind to everything that isn't a field. It cannot
tell you the agent leaked the waiting-list position while routing correctly.

**LLM-as-judge.** A second model reads the answer against written criteria.
Catches what fields can't. Costs an API call per case, and is itself fallible.

Use both: exact match for everything expressible as a field, a judge only for
what genuinely isn't.

### 3. Cost — what did it take?

Latency and tokens. An agent that's 5% more accurate and three times slower may
or may not be worth it — but you can't have that conversation without the
numbers.

In module 4 this becomes a real constraint: an endpoint has a timeout.

---

## Where judges let you down

LLM-as-judge is genuinely useful and routinely over-trusted. Know its failure
modes:

**It rewards fluency.** A confident, well-written wrong answer scores better
than a hesitant right one. Judges have the same bias a tired human reviewer
has, for the same reason.

**It drifts.** Run the same eval twice and scores differ. So a one-point
"improvement" after a prompt change is noise, not evidence.

**It's weakest where you need it most.** On clear-cut cases it agrees with you
and adds nothing. On borderline cases — the ones you actually want judged — the
written criteria stop being crisp and it starts guessing.

**It shares the blind spots of the thing it's judging.** Same architecture,
often the same model family. If the agent misunderstands a policy, the judge
frequently misunderstands it the same way.

**Use it as evidence, not a verdict.** Read the failures yourself.

### A false negative, from this repo's own CI

Worth walking through, because it looks exactly like a real failure until you
read it.

The refund case. The agent called three tools, routed to accounts, set
`needs_human: true`, named no figure, and suggested escalating to the Accounts
Officer. That is the correct answer in full. The judge failed it:

> "It frames the case as if the refund eligibility is already determined and
> suggests an approval path... too close to calculating/deciding the refund
> outcome."

The criterion it was judging against was:

> "Does not promise, approve or calculate a final refund amount as if it were
> decided."

One forbidden thing — *deciding an amount* — written as three verbs sharing an
object. The judge took `promise` and `approve` on their own, detached them from
"a final refund amount", and expanded them until describing an escalation
*route* counted as approving. It also marked "roll number verified; fees are
fully paid" as an unsupported claim, when both came from tool calls in the same
run.

Two things to take from it:

- **Write criteria as observables, not judgements.** "Does not approve" asks
  the judge to interpret. "Does not state a rupee amount or percentage, and
  does not say the refund is approved or granted" asks it to look. The second
  is checkable; the first is an invitation to reason.
- **Say what is explicitly allowed.** This is the part people skip. Left
  unstated, a judge derives new prohibitions from the ones you wrote — here,
  "don't approve it" quietly became "don't mention approval at all". The fixed
  criterion ends by naming citing policy, reporting the fee record, and
  recommending a named officer as correct.

The failure was in the *dataset*, not the agent — the same conclusion module 2's
base-rate story reaches by a different route. When an eval fails, the claim it
encodes is a suspect too.

---

## The golden dataset

Nine tickets with known-correct answers, in `evals/cases.py`. The most valuable
file in the repo and the least impressive-looking, which is true of most test
data.

### How to choose cases

Not at random, and not by sampling your queue — a real queue is mostly easy
cases, and your agent will pass those by accident.

Each case should encode a **specific way it goes wrong**:

| Case | What it catches |
|---|---|
| `hall_ticket_blocked_by_fees` | routing on symptom instead of cause |
| `hall_ticket_blocked_by_attendance` | the *mirror* — stops "always blame accounts" passing |
| `neft_reconciliation_window` | escalating a non-problem, wasting a human's time |
| `waiting_list_position_withheld` | following a policy that conflicts with being helpful |
| `refund_needs_human` | money movement must always escalate |
| `third_party_request` | a sympathetic requester who must still be refused |
| `revaluation_deadline` | arithmetic on a deadline, not just retrieval |

Notice cases 1 and 2 are the **same symptom with different causes**. An agent
using a shortcut passes exactly one of them. A dataset without that pair can't
tell reasoning from luck.

Include easy cases too — without them you can't distinguish an agent that's
correct from one that's merely cautious.

Ten well-chosen cases beat a hundred sampled ones.

---

## Breaking it on purpose

Here's the part people skip.

**A number on its own means nothing.** "7 out of 10" — is that good? You don't
know, and neither does anyone reading your slide.

An eval suite is useful only if it can **detect a regression**. So test the
suite: damage the agent deliberately and check the score moves.

`03_break_it.py` runs four variants:

| Variant | Damage | Typical failure |
|---|---|---|
| baseline | none | — |
| no lookups | the "look it up first" instruction removed | invents plausible answers |
| no tools | fee and exam tools removed | confident guesses instead of "I don't know" |
| lazy prompt | one vague sentence | inconsistent between runs |

**If you break the agent and the score doesn't move, your suite is
decoration.** Better to find that out now.

Watch *how* each variant fails, not just how often. "No tools" is the one that
should worry you — an agent that physically cannot know the answer, and commits
to a guess rather than saying so, is the exact failure that reaches production.

---

## Regression testing

Once your suite detects damage, it can guard against it:

```bash
make eval                      # everything
make eval -- --tag smoke       # the cheap subset
python evals/suite.py --json-output evals/results/today.json
```

Exit code 0 on pass, non-zero on fail — which is what lets CI gate on it in
module 4.

Run it **before and after every prompt change**. Prompts get edited casually
("just tidying the wording") and no type checker will ever catch what that
breaks.

---

## In the lab

1. `01_reliability.py` — free, instant, deterministic. Did it look things up?
2. `02_accuracy.py` — exact match and judge, side by side. Where they disagree
   is the interesting part.
3. `03_break_it.py` — sabotage your own agent and watch the numbers move.

---

## Things worth trying

- Add a case of your own. Find a ticket it gets **wrong** — far more useful
  than one it gets right.
- `COLLEGE_AGENT_MODEL=gemini-3.5-flash make lab3` — does a stronger model score
  better? By enough to justify the cost?
- Run `02_accuracy.py` twice without changing anything. Note that the scores
  differ. Then reconsider any benchmark you've ever seen quoted to one decimal
  place.

---

**Next:** [Module 4 — Deployment](04-deployment.md)
