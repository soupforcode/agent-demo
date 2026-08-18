"""Tests for the deterministic half of the eval suite.

The whole argument for `TriageFieldScorer` is that a field check is certain
where a judge is not. That argument only holds if the check itself is right, so
it gets tested — with no API key, in milliseconds, on every commit.

Which is the same argument one level up. A test suite that tests your test
suite sounds absurd until you remember that these assertions are what tell you
whether the agent works.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "evals"))

from scorer import TriageFieldScorer  # noqa: E402

from cases import CASES, by_name  # noqa: E402
from college_agent.schemas import TriageResult  # noqa: E402


@dataclass
class FakeRun:
    """Stands in for an Agno RunOutput. The scorer only reads `.content`."""

    content: object


def a_result(**overrides) -> TriageResult:
    fields = {
        "department": "accounts",
        "urgency": "normal",
        "summary": "Refund request after withdrawal.",
        "student_id": "ME21B027",
        "suggested_action": "Escalate to the Accounts Officer.",
        "needs_human": True,
        "reasoning": "Money movement needs a person.",
    }
    fields.update(overrides)
    return TriageResult(**fields)


@pytest.fixture
def scorer() -> TriageFieldScorer:
    return TriageFieldScorer()


@pytest.fixture
def refund():
    return by_name("refund_needs_human")


class TestFieldComparison:
    def test_both_fields_right_passes(self, scorer, refund):
        score = scorer.score(FakeRun(a_result()), refund)
        assert score.passed is True
        assert score.value == 1.0

    def test_wrong_department_fails(self, scorer, refund):
        score = scorer.score(FakeRun(a_result(department="hostel")), refund)
        assert score.passed is False
        assert "department" in score.reason

    def test_wrong_escalation_fails(self, scorer, refund):
        """The assertion two CI runs couldn't get a straight answer on."""
        score = scorer.score(FakeRun(a_result(needs_human=False)), refund)
        assert score.passed is False
        assert "needs_human" in score.reason

    def test_partial_credit_is_partial(self, scorer, refund):
        """One of two wrong scores 0.5 — a total failure and a near miss differ."""
        both_wrong = scorer.score(FakeRun(a_result(department="hostel", needs_human=False)), refund)
        one_wrong = scorer.score(FakeRun(a_result(department="hostel")), refund)
        assert both_wrong.value == 0.0
        assert one_wrong.value == 0.5
        assert both_wrong.passed is one_wrong.passed is False

    def test_the_reason_names_both_sides(self, scorer, refund):
        """A failure you have to re-run to understand is half a failure report."""
        score = scorer.score(FakeRun(a_result(department="hostel")), refund)
        assert "hostel" in score.reason and "accounts" in score.reason


class TestBrokenContracts:
    def test_json_text_is_accepted(self, scorer, refund):
        """Some paths hand back the JSON as a string. It still counts."""
        score = scorer.score(FakeRun(a_result().model_dump_json()), refund)
        assert score.passed is True

    def test_prose_is_a_hard_fail(self, scorer, refund):
        """No schema, no answer — not a partial score."""
        score = scorer.score(FakeRun("I'd route this to accounts, I think."), refund)
        assert score.passed is False
        assert score.value == 0.0

    def test_no_expected_value_fails_loudly(self, scorer):
        """Never silently green a case that was configured wrong."""
        assert scorer.score(FakeRun(a_result()), None).passed is False


class TestEveryCaseIsScorable:
    @pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
    def test_the_golden_answer_scores_itself(self, scorer, case):
        """Feed each case its own expected answer; it must pass.

        Catches a typo'd department in the dataset — a `Literal` the schema
        rejects, or an expectation no valid TriageResult could ever satisfy.
        """
        perfect = a_result(
            department=case.expected_department,
            needs_human=case.expected_needs_human,
        )
        assert scorer.score(FakeRun(perfect), case).passed is True
