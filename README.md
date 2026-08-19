# Architecting Autonomous Intelligence

A 4-hour hands-on workshop. You will build a **college administration triage
agent** — the thing that reads "I paid my fees last week but the portal still
says pending, and I can't get my hall ticket" and decides what actually needs to
happen.

By the end you'll have a working agent, a test suite that proves it works, and a
deployed HTTP service. Not a toy.

```
┌─────────────┐     ┌───────────────┐     ┌──────────────┐     ┌────────────┐
│  1. Agent   │ ──► │ 2. Workflow   │ ──► │ 3. Evaluate  │ ──► │ 4. Deploy  │
│ fundamentals│     │    design     │     │              │     │            │
└─────────────┘     └───────────────┘     └──────────────┘     └────────────┘
  what an agent       tools, routing,       does it actually     ship it as
  actually is         structured output     work? prove it.      a service
```

---

## The hands-on half runs in Colab — nothing to install

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/soupforcode/agent-demo/blob/main/notebooks/workshop.ipynb)

No Python, no `uv`, no `make`, no WSL. Works the same on Windows, macOS and a
borrowed laptop. All you need is a free Gemini API key.

The notebook walks the seven-step branch series below, showing you the diff
between each step before it runs anything.

**Prefer to work locally?** Everything below still applies — but note the
Makefile is POSIX-only, so on Windows you need WSL or Git Bash with `make`
installed separately.

---

## Before the workshop (do this a week early — it takes 10 minutes)

You need a free Gemini API key. Do **not** leave this to the day. (On Colab
this is the *only* thing you need.)

1. **Get a key** — go to <https://aistudio.google.com/apikey>, sign in with any
   Google account, click *Create API key*. No credit card required.

   > **Create your own key.** Rate limits are counted per Google Cloud project,
   > not per key. Thirty students with thirty keys = thirty independent quotas.
   > Thirty students sharing one key = about sixteen requests each, and the lab
   > dies in ten minutes.

2. **Install** — you need Python 3.10–3.12 and [uv](https://docs.astral.sh/uv/).

   ```bash
   git clone https://github.com/soupforcode/agent-demo.git
   cd agent-demo
   make setup
   ```

3. **Add your key**

   ```bash
   cp .env.example .env
   # open .env and paste your key after GOOGLE_API_KEY=
   ```

4. **Prove it works**

   ```bash
   make preflight
   ```

   This checks your Python version, that you have the *right* Google SDK, that
   your key is set and valid, and makes one real call. If it prints
   `PREFLIGHT PASSED`, you're ready. If it doesn't, it tells you exactly what to
   fix.

### ⚠️ Two things that will waste your time if nobody warns you

**The variable is `GOOGLE_API_KEY`, not `GEMINI_API_KEY`.** Google's own
quickstart tells you to set `GEMINI_API_KEY`. Agno only reads `GOOGLE_API_KEY`.
Set the wrong one and you get a confusing model-provider error rather than a
clear "no API key".

**Don't paste personal data into these labs.** Free-tier Gemini input and output
is used to improve Google's products and *may be read by human reviewers* —
that's in [Google's terms](https://ai.google.dev/gemini-api/terms). All the data
in this repo is synthetic. Don't test it on your actual roll number, your resume,
or your internship code.

---

## The workshop

Each module is 30 minutes of theory then 30 minutes of hands-on.

| # | Module | You'll learn | You'll build |
|---|--------|--------------|--------------|
| 1 | [Agent fundamentals](docs/01-fundamentals.md) | What an agent actually is, underneath the framework | The agent loop by hand, then the same thing in 10 lines of Agno |
| 2 | [Workflow design](docs/02-workflow-design.md) | Tools, structured output, routing, when *not* to use an agent | The real triage agent, plus a team that routes to specialists |
| 3 | [Evaluation](docs/03-evaluation.md) | How to know it works — and catch it when it stops working | A test suite: tool-call reliability, answer accuracy, LLM-as-judge |
| 4 | [Deployment](docs/04-deployment.md) | Turning a script into a service people can use | A FastAPI service, a Docker image, and CI that runs your evals |

**Instructors**: see [docs/instructor-guide.md](docs/instructor-guide.md) for
timings, checkpoints, and what to do when the wifi dies.

**Stuck on an error?** [docs/cheatsheet.md](docs/cheatsheet.md) has the traps —
especially if you pasted code from a blog post or an AI assistant, which will
almost certainly give you the *old* Agno API.

---

## Commands

```bash
make setup       # create the venv and install everything
make preflight   # verify your key and SDK work — run this first
make lab1        # run each lab
make lab2
make lab3
make lab4
make test        # the test suite — works with NO API key
make eval        # the full eval suite — needs a key
make serve       # run the API at http://localhost:8000
make docker      # build and run the container
make clean       # delete generated databases and caches
```

`make test` passing without an API key is deliberate, not a shortcut — it's what
lets the CI pipeline in module 4 actually mean something.

---

## What's in here

```
src/college_agent/     the actual application
  config.py            every model is built here, and nowhere else (see below)
  tools.py             what the agent can do: look up students, fees, hostel, policy
  schemas.py           TriageResult — the contract the agent must fill in
  agent.py             the triage agent
  team.py              specialists + a router
  api.py               the FastAPI service
  data/                synthetic college database
  kb/                  policy documents the agent searches
labs/                  the hands-on exercises, one folder per module
evals/                 the eval suite and recorded fixtures
tests/                 pytest — runs offline
docs/                  theory notes, slides, cheatsheet, instructor guide
```

### Why every model is built in one file

Agno silently falls back to **OpenAI** in three separate places: an `Agent` with
no model, both of the eval judges, and vector-store embedders. Everything looks
fine right up until something abruptly demands a key you didn't plan for.

So `config.py` is the only place in this repo that constructs a model, and
everything else imports from it. That's a real pattern worth stealing — pin your
providers in one place, because your dependencies have opinions about defaults
that you probably don't share.

It also paid for itself: supporting a **second provider** is a branch in one
function. Set `COLLEGE_AGENT_PROVIDER=openai` in `.env` and the agent, the team,
the API and the eval suite's judge all follow, with no other file touched.
(Gemini is the default — it has a free tier; OpenAI does not.)

---

## Licence

MIT — use it, fork it, teach it.
