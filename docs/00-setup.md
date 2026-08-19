# Setup — do this a week before the workshop

Ten minutes, done at home. Not on the day.

There is a reason for the insistence. Google account verification sometimes
takes hours, campus wifi is slow when thirty people install at once, and the
deprecated-SDK trap below has cost more workshop time than any other single
thing. None of that is interesting to debug in a room with a clock running.

---

## The easy path: Colab

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/soupforcode/agent-demo/blob/main/notebooks/workshop.ipynb)

Open that, and setup is finished. No Python install, no `uv`, no `make`, no
WSL — it runs in the browser and works identically on Windows, macOS and
Linux. **This is the recommended path**, and the only thing you still need
from this page is an API key (section 1 below) — Gemini or OpenAI, the
notebook reads whichever you put in Colab's secrets panel, and prefers
Gemini if you have both so the workshop cannot quietly cost you money.

Everything after section 1 is for running locally instead, which you are very
welcome to do.

> **Local setup on Windows:** the `Makefile` is POSIX-only, and `make` ships
> with neither Windows nor Git Bash. You would need WSL (`wsl --install` in an
> admin PowerShell, then follow the Linux steps unchanged), or Git Bash with
> `make` installed separately. If that sounds like an evening you would rather
> not have, use Colab.

---

## Which provider?

This workshop uses **Google Gemini** by default, because it has a free tier and
needs no credit card. Follow the steps below and you'll be fine.

**OpenAI also works**, if you'd rather use it and already have credits:

```bash
# in .env
COLLEGE_AGENT_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

> **OpenAI has no free tier.** You need paid credits on your account. If you're
> a student without them, use Gemini — everything in the workshop works
> identically either way.

---

## 1. Get a Gemini API key

Go to **<https://aistudio.google.com/apikey>**, sign in with any Google account,
and click *Create API key*.

- No credit card.
- Free tier.
- Available in India.

### Create your own key. Don't share one.

Rate limits are counted **per Google Cloud project**, not per key. So:

| | Daily requests each |
|---|---|
| 30 students, 30 keys | full quota each |
| 30 students, 1 shared key | roughly 16 |

An agent uses 5–15 model calls to handle **one** ticket. On a shared key the
lab dies in about ten minutes. This is not a rule to be polite about.

---

## 2. Install

You need **Python 3.10–3.12** and **[uv](https://docs.astral.sh/uv/)**.

```bash
# install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

git clone https://github.com/soupforcode/agent-demo.git
cd agent-demo
make setup
```

---

## 3. Add your key

```bash
cp .env.example .env
```

Open `.env` and paste your key:

```
GOOGLE_API_KEY=AIza...your-key-here
```

> ### The variable is `GOOGLE_API_KEY`, not `GEMINI_API_KEY`
>
> Google's own quickstart tells you to set `GEMINI_API_KEY`. Agno only ever
> reads `GOOGLE_API_KEY`.
>
> Set the wrong one and you don't get "no API key" — you get a confusing error
> about the model provider, several layers down, that looks like a bug in your
> code.
>
> `make preflight` detects this specific mistake and tells you.

---

## 4. Prove it works

```bash
make preflight
```

You want:

```
PREFLIGHT PASSED — you're ready for the workshop.
```

It checks your Python version, that you have the right SDK, that your key is
set and valid, that the database builds, that the tools run, and it makes one
real call to Gemini. If anything is wrong it prints the fix, not just the
failure.

**If it fails, fix it now, not on the day.**

---

## Things that go wrong

### `ModuleNotFoundError: No module named 'google.generativeai'`

You've pasted code from an old tutorial. That package is **dead** — its GitHub
repo is literally renamed `deprecated-generative-ai-python`.

```python
from google import genai            # correct, current
import google.generativeai as genai # dead, from 2024 tutorials
```

This is the single most common error in this workshop, and it will keep
happening because most tutorials — and most AI coding assistants — still
generate the old import from memory.

### `Agent.__init__() got an unexpected keyword argument 'response_model'`

You've found Agno **v1** documentation. Agno v2 renamed a lot. See
[cheatsheet.md](cheatsheet.md) for the full translation table.

Check you're reading **docs.agno.com**, not **docs-v1.agno.com** — the old site
is still live and looks current.

### `openai.OpenAIError: The api_key client option must be set`

Something asked for OpenAI. Agno silently defaults to OpenAI for agents with no
model, for eval judges, and for embedders.

In this repo, every model comes from `src/college_agent/config.py`. If you see
this error you've constructed something directly — import from `config` instead.

### `429 RESOURCE_EXHAUSTED`

You've hit your rate limit. Your key is fine.

- The starter code already retries with backoff, so brief limits handle themselves.
- Responses are cached to disk, so re-running the same thing while debugging is free.
- Daily quota resets at midnight US Pacific — about **12:30 PM IST**.
- If you're truly out: `make clean` won't help, but waiting will.

### The model ID doesn't exist (404)

Google retires model IDs. Set a different one in `.env`:

```
COLLEGE_AGENT_MODEL=gemini-3.5-flash
```

`make preflight` lists the known-good alternatives when this happens.

---

## Before you start: what not to type into these labs

Free-tier Gemini input and output is **used to improve Google's products** and
**may be read by human reviewers**. That's in
[Google's terms](https://ai.google.dev/gemini-api/terms), not speculation.

So don't paste:

- your actual roll number, or anyone else's
- your resume, or personal details
- code from a private repository or an internship
- API keys or credentials
- anything under an NDA

Every student, fee record and policy document in this repo is invented. Use
those. If you want to test on something real, use the paid tier, where Google
states it does not train on your data.

This is worth taking seriously — the instinct to test on your own data is
strong, and it is the wrong instinct here.

---

## Ready

```bash
make lab1
```

See you at the workshop.
