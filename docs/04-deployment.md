# Module 4 — Product Deployment

**30 minutes theory · 30 minutes lab**

> **Lab:** `make lab4`

---

## From script to service

Everything so far has been a script you run. Nobody uses a script you run.

Shipping an agent means confronting things a script never had to:

- Many users at once, and no shared state between them
- Requests that must finish, or fail cleanly, in bounded time
- Failures that must not become stack traces on someone's screen
- Costs that scale with usage, in a way you can't see until the bill
- Data you're now responsible for
- Behaviour that can regress from a one-word prompt edit

---

## The shape

```
  client ──► FastAPI ──► agent ──► Gemini
              │           │
              │           └──► tools ──► your database
              │
              └──► AgentOS  (sessions, runs, evals — mounted, not written)
```

Two layers, and the order matters:

**Your endpoint** is ordinary FastAPI. Pydantic in, Pydantic out, an error path.
Nothing framework-specific. This is your product, and it's what you'd keep if
you replaced Agno tomorrow.

**AgentOS** mounts onto that same app with `base_app=`, adding ~80 endpoints
for runs, sessions, memory and evals you didn't write.

```python
app = FastAPI()

@app.post("/triage", response_model=TriageResult)
def triage_endpoint(request: TriageRequest) -> TriageResult:
    ...

agent_os = AgentOS(agents=[...], base_app=app, on_route_conflict="preserve_base_app")
app = agent_os.get_app()
```

Building it the other way round — starting from the framework's server and
bolting your API on — means you can't change frameworks without changing your
public interface.

---

## Five things that separate a service from a script

### 1. Start degraded, don't crash

```python
@app.get("/health")
def health():
    key = bool(os.getenv("GOOGLE_API_KEY", "").strip())
    return {"status": "ok" if key else "degraded", ...}
```

Our app **starts without an API key**. `/health` reports degraded; `/triage`
returns 503 with an explanation.

A container that crashes at import because a config value is missing dies in a
restart loop and never gets to tell anyone why. Start, serve, and report.

### 2. Health checks must be free

`/health` never calls the model. Deliberately.

A health check that costs an API request drains your quota on a schedule, and
reports *your provider* being down as *you* being down — so your orchestrator
kills a perfectly good container because Google had a bad minute.

### 3. Errors don't leak

```python
except Exception as exc:
    log.exception("Triage failed")
    raise HTTPException(502, f"The agent could not complete this triage: {type(exc).__name__}")
```

Agents fail in ways normal services don't: rate limits, refused schemas, a model
that won't stop calling tools. All of them become a status code and a sentence.
The stack trace goes to your logs, not to the user.

### 4. Validate at the edge

```python
class TriageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
```

Rejecting a bad request costs nothing. Letting it reach the model costs an API
call to discover what Pydantic already knew. The length cap matters too — you
don't want to find your input limit by sending 400 kB to a metered API.

### 5. Bound everything

`tool_call_limit`, `max_output_tokens`, `timeout`, retries with backoff. All in
`config.py`.

An unbounded agent is an unbounded bill.

---

## Cost and quota

An agent request is 5–15 model calls, not one. That changes the arithmetic of
everything: rate limits, latency budgets, and cost per user.

Already in this repo:

- **`gemini-3.5-flash-lite`** by default — cheapest, fastest, highest limits
- **Response caching to disk**, so repeated work is free
- **Retry with exponential backoff** for the 429s you *will* hit
- **`tool_call_limit=10`** so a confused agent can't run away with your quota

The first optimisation is almost never a bigger model. It's fewer calls.

---

## Observability

You cannot debug what you cannot see, and an agent's behaviour is invisible by
default.

```python
agent = build_triage_agent(debug=True)   # every message, tool call, token count
```

For production, Agno traces to your database via OpenTelemetry:

```python
from agno.tracing import setup_tracing
setup_tracing(db=db)
```

**What to log:** the run ID, which tools were called with what arguments, token
counts, latency, and the final decision.

**What not to log:** the raw ticket text, if it contains personal data. Which
brings us to the uncomfortable part.

---

## The part that's actually your responsibility

**Free-tier Gemini input and output is used to train Google's models and may be
read by human reviewers.** That's their terms, not a rumour.

If this were a real college system, every student's fee dispute and hostel
complaint would be going into that pipeline. You would need the paid tier at
minimum, and probably a conversation with someone about consent.

The general shape of the obligation:

- Know what leaves your infrastructure and where it lands
- Don't log personal data because logging was convenient
- Decide retention deliberately rather than by default
- An agent that can read a student's fee record can leak a student's fee record

The `third_party_request` eval case exists for this reason. A parent asking
about their child is sympathetic, and the agent must still refuse. That's a
product decision encoded as a test — which is where policy decisions belong.

---

## CI: the safety net

An agent's behaviour lives in its prompt, and prompts get edited casually. No
type checker will catch what that breaks.

Two tiers in `.github/workflows/ci.yml`:

**`checks`** — every push, **no API key**. Tools, schema shape, service
behaviour, eval harness. Fast, free, deterministic.

**`eval`** — the real agent against the golden dataset. Needs a `GOOGLE_API_KEY`
secret, so it skips cleanly on forks.

Be clear-eyed about what the first tier proves: **the plumbing is sound, not
that the agent reasons well.** Only the second tells you that. A green badge
from `checks` alone is not evidence your agent works — and knowing the
difference between "CI is green" and "the system works" is most of what
separates a senior engineer from a junior one.

---

## In the lab

```bash
make lab4       # exercise the API in-process
make serve      # then open http://localhost:8000/docs
make docker     # build and run the container
```

Then push and watch Actions run.

---

## Things worth trying

- Call `/triage` from the `/docs` page.
- Look at what `/health` does **not** do. Then think about what your own health
  checks call.
- Break something in `agent.py`, run `make test`, and watch it fail before you
  push.
- Add `GOOGLE_API_KEY` as a repository secret and watch the eval job gate a
  prompt change.

---

## Where to go next

- **Memory** — `db=SqliteDb(...)` plus `add_history_to_context=True` gives you
  multi-turn sessions.
- **RAG** — this repo uses SQLite full-text search over six policy documents,
  deliberately. For a corpus this size that's the right call: no embedding
  cost, no service to run, explainable results. Reach for a vector store when
  you can *show* keyword search failing, not before.
- **Human-in-the-loop** — Agno's `requires_confirmation` pauses a tool call for
  approval. Worth reading about for anything that moves money.

---

**Back to:** [README](../README.md) · [Cheatsheet](cheatsheet.md)
