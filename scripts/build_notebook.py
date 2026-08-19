#!/usr/bin/env python3
"""Generate notebooks/workshop.ipynb — the hands-on half, in Google Colab.

    python scripts/build_notebook.py

Why a generator rather than a hand-written .ipynb
-------------------------------------------------
The notebook walks the same seven steps as the branch series, so every step
title, one-line summary and "what to look at" note exists in two places. Two
places is where drift lives — this repo has already shipped a banner claiming
ten golden cases when there were nine.

So the notebook is built from `STEPS` in build_steps.py, the same table that
builds the branches. Change a step description once and both follow.

Why Colab at all
----------------
The Makefile is POSIX-only and `make` ships with neither Windows nor Git Bash,
so a Windows student cannot get past `make setup`. Most of the room is on
Windows. Colab removes the entire class of problem: no Python install, no uv,
no make, no WSL, and everybody is on one environment the instructor can
actually debug.

Two Colab-specific things this handles
--------------------------------------
1. Every step runs its command with `!python ...` rather than in-process. A
   subprocess gets a fresh interpreter, which matters twice over: Agno's eval
   `cli()` calls `asyncio.run()`, which raises inside a notebook's already
   running loop, and switching branches mid-notebook would otherwise leave
   stale `college_agent` modules cached in the kernel.
2. The API key comes from Colab's secrets panel, not a pasted literal. A key
   pasted into a cell gets saved into the notebook and shared with it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_steps import STEPS  # noqa: E402

REPO_URL = "https://github.com/soupforcode/agent-demo.git"
CLONE = "/content/agent-demo"
OUT = Path(__file__).resolve().parents[1] / "notebooks" / "workshop.ipynb"


# What the full diff cell shows.
#
# Not just `src`: step 6 adds evals, labs and tests and touches src not at all,
# so a src-only diff rendered *completely empty* for the step whose whole point
# is the eval suite. Verified by running it — the cell produced zero bytes.
#
# The two exclusions are the seed data and the knowledge-base markdown, ~400
# lines of fixture that arrive at step 3 and would bury tools.py, which is the
# actual lesson there. They still show up in the --stat line above the diff.
DIFF_PATHS = "src labs evals tests ':!src/college_agent/data' ':!src/college_agent/kb'"

# One line of colour per step, notebook-only.
#
# Kept out of `STEPS` on purpose: that table also writes STEP.md onto every
# branch, so editing it means rebuilding and force-pushing seven branches.
# A joke is not worth a rewrite of the history.
FLAVOUR = {
    "step-1-agent": "Confidence: total. Evidence: none. We start here so the rest lands.",
    "step-2-structured": "Same wrong answer, now beautifully typed.",
    "step-3-tools": "It can finally look things up. Watch it change its mind.",
    "step-4-guardrails": "The difference between \u201cplease don't\u201d and \u201cyou can't\u201d.",
    "step-5-team": "Four agents instead of one. Roughly double the bill. Was it worth it?",
    "step-6-evals": "Stop trusting your eyes. Start counting.",
    "step-7-deploy": "Something someone else can actually call.",
}


def md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").splitlines(True)}


def code(text: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": text.strip("\n").splitlines(True),
    }


def cells() -> list[dict]:
    out: list[dict] = []

    out.append(
        md(
            f"""
# Architecting Autonomous Intelligence
### Two hours. Seven steps. One agent that starts out very sure of itself.

Your college admin office gets tickets like *"I can't download my hall ticket,
my exam is on Monday."* Somebody has to read each one and decide who deals
with it. Today you build the thing that does the deciding.

It will not go smoothly, and that is the plan. By step 2 your agent will
produce a perfectly formatted, fully validated, entirely **invented** answer
about a student it has never looked up. Fixing that is most of the workshop.

Nothing to install. No Python, no `make`, no "works on my machine". It all
runs here.

**You need exactly one thing:** an API key.

- **Gemini** — free, no card, two minutes: <https://aistudio.google.com/apikey>
- **OpenAI** — works exactly the same, if you already have credits:
  <https://platform.openai.com/api-keys>. No free tier, so it costs real money.

Everything below is provider-agnostic. One line in `config.py` decides which
one you get, and nothing else in the repo knows or cares — which is itself
worth noticing, and is why adding OpenAI took one function rather than a
rewrite.

> ### Get your own key. Seriously.
> Rate limits count per Google Cloud project, not per key. Thirty people on
> one key get about **sixteen requests each** — and a single ticket costs the
> agent 5–15 model calls. Do the arithmetic: a shared key dies before the
> first coffee break, and it takes the whole room with it.

---

## How this works

Each step is a git branch, and each one adds exactly one idea.

The good bit is not any single branch — it is the **diff between two of
them**. One concept, nothing else mixed in, no hunting through a file for the
line that matters. Every step below shows you that diff before it runs
anything. Read them. That is where the workshop actually is.

The whole repo is at <{REPO_URL.removesuffix(".git")}> if you would rather
work locally; see `docs/00-setup.md`.
"""
        )
    )

    out.append(
        md(
            """
---

## Setup — run this once

Clones the repo, installs everything, and builds a small fake college database
— 12 students with their fees, hostel rooms and exam records. All invented,
none of it anybody's real data.

A minute or two. Good time to go and get your API key if you haven't.
"""
        )
    )
    out.append(
        code(
            f"""
# Safe to re-run. "Runtime -> Restart session" clears the Python kernel but
# NOT /content, so the clone survives a restart — and an unguarded clone would
# greet you with a red "fatal: destination path already exists" for no reason.
![ -d {CLONE} ] || git clone -q {REPO_URL} {CLONE}
%cd {CLONE}
%pip install -q -e ".[dev]"
!python -m college_agent.data.seed
"""
        )
    )
    out.append(
        md(
            """
> **If the next cell fails with an import error**, Colab had an older version
> of something already loaded. Go to **Runtime → Restart session**, then run
> the cells again *starting from the API key cell below* — the clone and
> install survive a restart, so you do not need to repeat them.
"""
        )
    )

    out.append(
        md(
            """
### Your API key

Use the **secrets panel**, not a literal in a cell. Anything typed into a cell
is saved inside the notebook and goes wherever the notebook goes — which is a
genuinely common way to publish a working key to the internet by accident.

1. Click the **🔑 key icon** in the left sidebar.
2. **+ Add new secret**, named for whichever provider you have:
   - `GOOGLE_API_KEY` — Gemini. Free tier, no card. **Use this one.**
   - `OPENAI_API_KEY` — works identically, but has no free tier and will
     spend your credits.
3. Paste your key as the value, and turn on **Notebook access**.

Set both and Gemini wins, because the workshop should not cost you money by
accident.

> **It is `GOOGLE_API_KEY`, not `GEMINI_API_KEY`.** Google's own quickstart
> tells you the second one. The framework only ever reads the first. This one
> mismatch has eaten more workshop time than every other setup problem
> combined, and the error it throws points nowhere near the cause.
"""
        )
    )
    out.append(
        code(
            """
import os


def secret(name):
    # Read one Colab secret. Empty string if it is missing or not shared with
    # this notebook, so the caller can just check truthiness.
    try:
        from google.colab import userdata

        return (userdata.get(name) or "").strip()
    except Exception:
        # Not on Colab, secret absent, or notebook access not granted.
        return ""


google, openai = secret("GOOGLE_API_KEY"), secret("OPENAI_API_KEY")

if google:
    # Google first when both exist: it is the free tier, and nobody should
    # discover they spent money by attending a workshop.
    os.environ["COLLEGE_AGENT_PROVIDER"], os.environ["GOOGLE_API_KEY"] = "google", google
elif openai:
    os.environ["COLLEGE_AGENT_PROVIDER"], os.environ["OPENAI_API_KEY"] = "openai", openai
else:
    import getpass

    choice = input("Provider — google or openai? [google]: ").strip().lower() or "google"
    var = "OPENAI_API_KEY" if choice == "openai" else "GOOGLE_API_KEY"
    os.environ["COLLEGE_AGENT_PROVIDER"], os.environ[var] = choice, getpass.getpass(f"{var}: ")

# One line of truth about what is actually configured. Every part of the repo
# builds its model through this same config, so whatever it says here is what
# the agent, the team and the eval judge will all use.
from college_agent.config import describe_config

print(describe_config())
"""
        )
    )

    out.append(
        md(
            "### Check it works\n\nOne real call to the model. If this passes, everything below "
            "will run — and if it doesn't, it names the part that is unhappy instead of "
            "making you guess."
        )
    )
    out.append(code("!python scripts/preflight.py"))

    prev: str | None = None
    for i, spec in enumerate(STEPS, start=1):
        branch = spec["branch"]
        look = "\n".join(f"- {line}" for line in spec["look"])
        out.append(
            md(
                f"""
---

# Step {i} of {len(STEPS)} — {spec["title"]}

*{FLAVOUR[branch]}*

**New here:** {spec["new"]}

{look}
"""
            )
        )

        if prev is None:
            out.append(code(f"!git switch -q {branch}\n!git --no-pager log --oneline -1"))
        else:
            out.append(
                md(
                    f"**The diff is the lesson.** Everything that changed between step "
                    f"{i - 1} and step {i}. The file summary comes first — read that, pick "
                    f"the file that looks interesting, then find it in the diff underneath."
                )
            )
            out.append(
                code(
                    f"!git switch -q {branch}\n"
                    f"!git --no-pager diff --stat {prev} {branch}\n"
                    f"print()\n"
                    f"!git --no-pager diff {prev} {branch} -- {DIFF_PATHS}"
                )
            )

        out.append(code("\n".join(f"!{cmd}" for cmd in spec["colab"])))
        prev = branch

    out.append(
        md(
            """
---

# Done

You built an agent that reads a complaint, looks up the facts, routes on the
cause instead of the symptom, refuses what it should refuse, and can tell you
how often it gets that right. `git switch main` is the same thing with the
whole history behind it.

Worth noticing what actually did the work. Almost none of it was the model.
It was a schema, six tools with well-written docstrings, two guardrails, and
nine test cases that disagreed with you.

### Two things this notebook could not show you

- **Docker.** Step 7 ships a `Dockerfile` and CI, and neither runs in Colab.
  Read `Dockerfile` and `.github/workflows/ci.yml` — they are short, and the
  comments explain the two-tier design: tests with no API key on every push,
  real agent evals only when a key is configured.
- **The AgentOS web UI.** `make serve` runs a real FastAPI service; in Colab
  the lab drives it with `TestClient` instead, which exercises the same code
  but gives you no browser to click in.

### Where to go next

- Add a case to `evals/cases.py` that the agent gets **wrong**. Much harder
  than one it gets right, and much more useful.
- Delete the "route on the underlying cause" line in
  `src/college_agent/agent.py`, re-run step 3, and watch the hall-ticket
  ticket go to the wrong department. One sentence was holding that up.
- Add a field to `TriageResult` and re-run. The agent fills it in without
  being asked, because the field description *is* the instruction.
- Run the same eval against a stronger model, then decide whether the
  difference was worth the money. That question is the job.

> **Your Colab session is temporary.** Anything you changed here disappears
> when the runtime recycles. If you did something you want to keep, download
> it or push it to your own fork now.
"""
        )
    )
    return out


def main() -> int:
    nb = {
        "nbformat": 4,
        "nbformat_minor": 0,
        "metadata": {
            "colab": {"provenance": [], "toc_visible": True},
            "kernelspec": {"name": "python3", "display_name": "Python 3"},
            "language_info": {"name": "python"},
        },
        "cells": cells(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {OUT.relative_to(Path.cwd())}  ({len(nb['cells'])} cells)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
