"""Deterministic scoring — the half of an eval that needs no judge.

Module 3 states the rule: exact match for anything expressible as a field, a
judge only for what isn't. For a while this suite didn't follow it. Every case
handed `department` and `needs_human` to the LLM judge inside a sentence of
English, and asked it to decide whether a `Literal` and a `bool` were correct.

That is a strange thing to do. `needs_human` is already a boolean by the time
the judge sees it. Comparing it to `True` is `==`. Routing it through a second
language model adds cost, latency, and — the part that actually bit us — a
source of disagreement that has nothing to do with the agent.

It bit us twice in CI on the same case. Both times the agent was right and the
judge invented a reason. The second is the more instructive:

    agent:  "Refunds require Accounts Officer approval and cannot be
             granted automatically."
    judge:  FAIL — "the criteria say the output should avoid any language
             that says the refund is approved, granted, or guaranteed."

Read those together. The agent produced the single safest sentence available
to it, and the judge failed it for containing the word "granted" — matching on
the token while missing the negation in front of it. A judge is a language
model, and language models pattern-match.

So the fields move here, where the check is `==` and cannot drift. What is
left for the judge is what genuinely needs reading: did it refuse to disclose
the waiting list position, did it avoid promising a refund. That is the job a
judge is actually good at, and it does it better with less to weigh.

The wider point, worth making to a room: **an LLM in your test suite is a
dependency with a failure rate.** Use it only for the assertions you cannot
write any other way.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from agno.scorer.base import Score  # noqa: E402

from college_agent.agent import as_triage_result  # noqa: E402


@dataclass(frozen=True)
class TriageFieldScorer:
    """Compares the structured fields of a run against the golden answer.

    Implements Agno's `Scorer` protocol, so `Case(scorer=..., expected=...)`
    runs it in the same pass as the judge and folds the verdict into the case's
    pass/fail. `expected` is the `TriageCase`.

    Note that this scorer is only possible *because* the agent has an
    `output_schema`. Back at step 1 the agent returned prose, and a check like
    this could not have been written at all — you would have had no choice but
    to ask a judge. That is the concrete payoff of structured output, and it
    arrives in the test suite rather than in the application.
    """

    def score(self, run: Any, expected: Any = None) -> Score:
        if expected is None:
            return Score(value=0.0, passed=False, reason="no expected value supplied")

        try:
            result = as_triage_result(run.content)
        except RuntimeError as exc:
            # Not a scoring failure with a partial credit story — the agent
            # broke its own contract, and that is a hard fail.
            return Score(value=0.0, passed=False, reason=str(exc))

        checks = {
            "department": (result.department, expected.expected_department),
            "needs_human": (result.needs_human, expected.expected_needs_human),
        }
        wrong = [
            f"{name}={got!r} (expected {want!r})"
            for name, (got, want) in checks.items()
            if got != want
        ]

        value = (len(checks) - len(wrong)) / len(checks)
        if wrong:
            return self._report(Score(value=value, passed=False, reason="; ".join(wrong)))
        return self._report(
            Score(value=1.0, passed=True, reason="department and needs_human both correct")
        )

    @staticmethod
    def _report(score: Score) -> Score:
        """Print the verdict.

        Agno puts the scorer result in the JSON output but does not render it,
        so without this a field mismatch shows up as a bare `FAIL` in the
        summary with `Judge: PASS` beside it and no stated reason — the worst
        possible thing to meet in front of a room. Cheap to fix here.
        """
        try:
            from rich import print as rprint

            colour = "green" if score.passed else "red"
            verdict = "PASS" if score.passed else "FAIL"
            rprint(f"[{colour}]Fields: {verdict}[/{colour}]  [dim]{score.reason}[/dim]")
        except Exception:  # pragma: no cover - reporting must never fail a run
            pass
        return score

    async def ascore(self, run: Any, expected: Any = None) -> Score:
        # The protocol is async; nothing in here is. Agno awaits this one.
        return self.score(run, expected)
