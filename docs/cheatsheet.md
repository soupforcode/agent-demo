# Cheatsheet — the things that will bite you

Keep this open during the labs.

---

## Agno v1 → v2

Agno v2 renamed most of v1's API. **Every blog post, most Stack Overflow
answers, and almost every AI coding assistant will give you v1 code**, because
that's what's in their training data.

`docs-v1.agno.com` is also still online and looks perfectly current.

| v1 — wrong | v2 — current |
|---|---|
| `response_model=` | **`output_schema=`** |
| `storage=`, `table_name=` | **`db=`**, `session_table=` |
| `from agno.storage.sqlite import SqliteStorage` | `from agno.db.sqlite import SqliteDb` |
| `RunResponse` | **`RunOutput`** (`from agno.run.agent`) |
| `knowledge.load()` | `knowledge.insert()` |
| `context=` | `dependencies=` |
| `AgentKnowledge` | `Knowledge` |
| `mode="route"` (string) | `mode=TeamMode.route` |
| `Playground` | `AgentOS` |
| `stream_intermediate_steps=` | `stream_events=` |
| `await agent.arun(...)` streaming | `async for event in agent.arun(...)` |
| metrics: `prompt_tokens`, `time` | `input_tokens`, `duration` |

**How to tell instantly:** if the snippet says `response_model=`, it's v1. Stop
reading it.

---

## Agno's silent defaults

Agno reaches for OpenAI in three places when you didn't ask it to.

The problem was never OpenAI — it's a supported provider here, see below. The
problem is a default you didn't choose, firing silently, and demanding a key you
may not have.

| Where | What it defaults to | Fix |
|---|---|---|
| `Agent(model=None)` | `OpenAIResponses` | always pass `model=` |
| `AccuracyEval`, `AgentAsJudgeEval` | `OpenAIChat` | pass `model=get_model()` |
| `ChromaDb`, `LanceDb` embedder | `OpenAIEmbedder` | pass `embedder=...` |

In this repo, **`src/college_agent/config.py` is the only file that builds a
model**. Import `get_model()` from there and you can't hit any of these.

If you see `openai.OpenAIError` while on the google provider, you've constructed
something directly.

## Choosing a provider

```bash
COLLEGE_AGENT_PROVIDER=google    # default — free tier, no card
COLLEGE_AGENT_PROVIDER=openai    # PAID ONLY, no free tier
```

Everything follows automatically — agent, team, API, and the eval suite's judge.
That's the whole point of building every model in one file: adding a second
provider was a branch in one function, not a refactor.

## API keys

```bash
GOOGLE_API_KEY=...     # what Agno reads for the google provider
GEMINI_API_KEY=...     # what Google's docs tell you — Agno ignores it
OPENAI_API_KEY=...     # for the openai provider
```

If both Google vars are set, the raw Google SDK prefers `GOOGLE_API_KEY`. Keep
them identical or just set `GOOGLE_API_KEY`.

`make preflight` checks the key for whichever provider you selected, and tells
you if you've set the other one by mistake.

---

## The SDK

```python
from google import genai              # correct
import google.generativeai as genai   # DEAD — repo renamed "deprecated-..."
```

---

## Gemini's schema limits

Gemini rejects large or deeply nested schemas, with unhelpful errors.

**Do:**
```python
class TriageResult(BaseModel):
    department: Literal["accounts", "hostel"]   # Literal inlines
    urgency: str
    needs_human: bool
```

**Don't:**
```python
class TriageResult(BaseModel):
    routing: RoutingDetails          # nested model -> $defs -> rejected
    department: DepartmentEnum       # Enum class -> $defs -> rejected
    notes: Optional[str] = None      # known Agno bug: may be marked required
```

Use `Literal[...]` rather than an `Enum` class — `Literal` inlines into the
schema, `Enum` creates a `$defs` entry.

`tests/test_schemas.py` enforces all of this, so you'll find out at test time
rather than at demo time.

---

## Rate limits

- Limits are **per project**, not per key or per IP.
- An agent run is 5–15 model calls.
- Daily quota resets **midnight US Pacific ≈ 12:30 PM IST**.
- Google no longer publishes free-tier numbers — check yours at
  <https://aistudio.google.com/rate-limit>.

Already handled for you in `config.py`: retry with exponential backoff,
response caching to disk, a `tool_call_limit`, and a capped `max_output_tokens`.

To stop caching (you want fresh responses):

```bash
COLLEGE_AGENT_CACHE=false make lab2
# or
make clean
```

---

## Debugging an agent

```python
agent = build_triage_agent(debug=True)
```

Shows every message sent to the model, the raw response, each tool call and
result, and token counts.

This is the highest-value thing in the framework. The first time an agent does
something you didn't expect, turn it on rather than guessing — the gap between
what you assume happened and what actually happened is usually the bug.

```bash
export AGNO_DEBUG=true    # same thing, globally
```

---

## Commands

```bash
make preflight    # check your setup
make test         # tests — no API key needed
make eval         # full eval suite — needs a key
make eval -- --tag smoke   # cheaper subset
make serve        # http://localhost:8000/docs
make clean        # wipe the database and the response cache
```

---

## Where things live

| I want to change… | Edit |
|---|---|
| what the agent is told to do | `src/college_agent/agent.py` → `INSTRUCTIONS` |
| what it can do | `src/college_agent/tools.py` |
| what it must return | `src/college_agent/schemas.py` |
| which provider, model, retries, caching | `src/college_agent/config.py` |
| the student data | `src/college_agent/data/seed.py` |
| the policy documents | `src/college_agent/kb/*.md` |
| the eval cases | `evals/cases.py` |
