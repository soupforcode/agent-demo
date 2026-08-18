#!/usr/bin/env python3
"""The eval suite — run this to find out whether the agent actually works.

    make eval                          run everything
    python evals/suite.py --list       see the cases without running them
    python evals/suite.py --tag smoke  run a subset
    python evals/suite.py --json-output evals/results/latest.json

Exit code is 0 when everything passes and non-zero when it doesn't, which is
what lets CI use this as a gate rather than as decoration.

Three checks per case, in increasing order of unreliability
----------------------------------------------------------
**Tool calls** — did it look things up, or did it guess? Deterministic, free,
no judge involved. An agent that gets the right department without ever
checking the student's record got lucky, and luck doesn't survive a rewording.

**Fields** — `department` and `needs_human`, compared with `==`. Also
deterministic, also free. See `evals/scorer.py`; these used to be handed to the
judge as a sentence of English, which was a mistake and is a good story.

**Criteria** — an LLM judge reads the answer against a written standard. This
catches what neither of the above can: did it refuse to disclose the waiting
list position, did it avoid promising a refund.

Notice the order. Each check is cheaper, faster and more certain than the one
after it, and every assertion you can move upwards is one that stops flaking.

The judge is not an oracle
--------------------------
It's another language model with the same weaknesses as the one being judged.
It is lenient about confident-sounding wrong answers, and it will occasionally
disagree with itself between runs. Treat a judge score as evidence, not proof,
and read the failures yourself before believing them.

A note on the judge model
-------------------------
Agno defaults to OpenAI for judging. We pass Gemini explicitly — otherwise this
suite would demand an OPENAI_API_KEY that nobody in the workshop has, and it
would only tell you that at the moment you ran it.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "evals"))

from agno.eval import Case, JudgeMode, cli  # noqa: E402
from scorer import TriageFieldScorer  # noqa: E402

from cases import CASES  # noqa: E402
from college_agent.agent import build_triage_agent  # noqa: E402
from college_agent.config import get_model  # noqa: E402


def build_cases(model_id: str | None = None) -> tuple[Case, ...]:
    """Turn the golden dataset into Agno eval cases."""
    agent = build_triage_agent(model_id)

    return tuple(
        Case(
            name=c.name,
            agent=agent,
            input=c.ticket,
            tags=c.tags,
            # --- the deterministic half ---
            expected_tool_calls=c.expected_tools or None,
            # More than one reasonable path usually leads to a right answer.
            # Pinning the exact sequence makes the eval brittle without making
            # it stricter in any way that matters.
            allow_additional_tool_calls=True,
            # --- the exact half ---
            # department and needs_human are a Literal and a bool. They get
            # compared with `==`, in-process, for free. This used to be part of
            # the criteria string below, which meant asking a language model
            # whether True was True — see evals/scorer.py for what that cost us.
            scorer=TriageFieldScorer(),
            expected=c,
            # --- the judged half ---
            # Only what is genuinely prose-shaped survives here: did it refuse
            # to disclose the waiting list position, did it avoid promising a
            # refund. A judge with less to weigh is a judge that disagrees with
            # you less often.
            criteria=c.criteria or None,
            judge_mode=JudgeMode.BINARY,
            timeout_seconds=90,
        )
        for c in CASES
    )


if __name__ == "__main__":
    raise SystemExit(
        cli(
            build_cases(),
            # Explicit, so this never silently asks for an OpenAI key.
            judge_model=get_model(temperature=0.0),
            default_timeout=90,
        )
    )
