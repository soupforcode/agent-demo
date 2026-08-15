"""Tests for the evaluation machinery itself.

Two different things get checked here, and both run without an API key.

**The golden dataset is internally consistent.** Every case references a
student who exists, a department that's real, and tools that are actually
attached to the agent. A typo in `cases.py` produces an eval case that can
never pass, and you'd waste an hour blaming the agent for it.

**The reliability harness works.** Tool-call evaluation runs against a recorded
`RunOutput`, so it needs no model at all — which is exactly why it's the check
CI can afford to run on every push.

What this file does *not* do
----------------------------
It doesn't test whether the agent is any good. That needs a real model and
lives in `make eval`. Being honest about the boundary matters: a green CI badge
here means the plumbing is sound, not that the agent reasons well.
"""

from __future__ import annotations

from agno.eval.reliability import ReliabilityEval
from agno.models.response import ToolExecution
from agno.run.agent import RunOutput

from cases import CASES, by_name, by_tag
from college_agent.schemas import TriageResult


def _fake_run(tool_names: list[str], **kwargs) -> RunOutput:
    """A recorded agent run, without running an agent.

    This is the trick that makes tool-call evaluation free: `ReliabilityEval`
    inspects a RunOutput, and a RunOutput is just data. Record real ones with
    `evals/record_fixtures.py`, or hand-build them like this to test the
    harness.
    """
    return RunOutput(
        run_id="test-run",
        content="triaged",
        tools=[
            ToolExecution(tool_name=name, tool_args=kwargs.get(name, {}), result="ok")
            for name in tool_names
        ],
    )


class TestDatasetIntegrity:
    """A broken eval case is worse than a missing one — it fails for the wrong reason."""

    def test_every_case_has_a_unique_name(self):
        names = [c.name for c in CASES]
        assert len(names) == len(set(names)), f"Duplicate case names: {names}"

    def test_every_expected_department_is_real(self):
        from typing import get_args

        valid = set(get_args(TriageResult.model_fields["department"].annotation))
        for case in CASES:
            assert case.expected_department in valid, (
                f"Case {case.name!r} expects department "
                f"{case.expected_department!r}, which isn't one of {sorted(valid)}."
            )

    def test_every_expected_tool_exists(self):
        from college_agent.tools import TRIAGE_TOOLS

        available = {fn.__name__ for fn in TRIAGE_TOOLS}
        for case in CASES:
            for tool in case.expected_tools:
                assert tool in available, (
                    f"Case {case.name!r} expects tool {tool!r}, which the agent "
                    f"doesn't have. Available: {sorted(available)}"
                )

    def test_every_referenced_student_exists(self):
        """A case citing a roll number that isn't in the database can never pass."""
        import re

        from college_agent.tools import lookup_student

        for case in CASES:
            for roll_no in re.findall(r"\b[A-Z]{2}\d{2}[A-Z]\d{3}\b", case.ticket):
                assert "No student found" not in lookup_student(roll_no), (
                    f"Case {case.name!r} references {roll_no}, who is not in the seeded database."
                )

    def test_every_case_has_judge_criteria(self):
        for case in CASES:
            assert case.criteria.strip(), f"Case {case.name!r} has no criteria for the judge."

    def test_every_case_explains_itself(self):
        """The `note` is the teaching content — an undocumented case is a mystery later."""
        for case in CASES:
            assert case.note.strip(), f"Case {case.name!r} has no note explaining why it exists."

    def test_the_dataset_covers_both_outcomes(self):
        """A dataset where everything escalates teaches the agent to always escalate."""
        escalates = [c for c in CASES if c.expected_needs_human]
        assert escalates, "No case expects escalation."
        assert len(escalates) < len(CASES), "Every case expects escalation — no negative examples."

    def test_smoke_subset_exists(self):
        """`--tag smoke` is what you run when quota is tight. It must not be empty."""
        assert len(by_tag("smoke")) >= 3

    def test_lookup_helpers(self):
        assert by_name("refund_needs_human").expected_needs_human is True


class TestReliabilityHarness:
    """The tool-call check works with no model and no API key."""

    def test_passes_when_the_required_tool_was_called(self):
        result = ReliabilityEval(
            name="t",
            agent_response=_fake_run(["lookup_student", "check_fee_status"]),
            expected_tool_calls=["check_fee_status"],
            allow_additional_tool_calls=True,
            telemetry=False,
        ).run(print_results=False)

        assert result.eval_status == "PASSED"
        assert not result.missing_tool_calls

    def test_fails_when_the_agent_skipped_the_lookup(self):
        """The failure this whole check exists to catch: a right answer, guessed."""
        result = ReliabilityEval(
            name="t",
            agent_response=_fake_run(["search_policy"]),
            expected_tool_calls=["check_fee_status"],
            allow_additional_tool_calls=True,
            telemetry=False,
        ).run(print_results=False)

        assert result.eval_status == "FAILED"
        assert "check_fee_status" in result.missing_tool_calls

    def test_fails_when_no_tools_were_called_at_all(self):
        result = ReliabilityEval(
            name="t",
            agent_response=_fake_run([]),
            expected_tool_calls=["lookup_student"],
            telemetry=False,
        ).run(print_results=False)

        assert result.eval_status == "FAILED"

    def test_extra_tool_calls_are_allowed_when_permitted(self):
        """There's usually more than one reasonable path. Don't over-specify it."""
        result = ReliabilityEval(
            name="t",
            agent_response=_fake_run(
                ["lookup_student", "check_fee_status", "check_exam_status", "search_policy"]
            ),
            expected_tool_calls=["check_fee_status"],
            allow_additional_tool_calls=True,
            telemetry=False,
        ).run(print_results=False)

        assert result.eval_status == "PASSED"

    def test_assert_passed_raises_on_failure(self):
        """This is what makes the harness usable from pytest and from CI."""
        import pytest

        result = ReliabilityEval(
            name="t",
            agent_response=_fake_run([]),
            expected_tool_calls=["lookup_student"],
            telemetry=False,
        ).run(print_results=False)

        with pytest.raises(AssertionError):
            result.assert_passed()


class TestSuiteWiring:
    """The suite must not silently reach for an OpenAI key."""

    def test_suite_builds_without_calling_openai(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key-not-used")

        from suite import build_cases

        cases = build_cases()
        assert len(cases) == len(CASES)

    def test_every_case_has_at_least_one_check(self, monkeypatch):
        """Agno rejects a Case with no criteria, no tools and no scorer."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key-not-used")

        from suite import build_cases

        for case in build_cases():
            assert case.criteria or case.expected_tool_calls or case.scorer
