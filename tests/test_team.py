"""Tests for the routing team.

These exist because of a bug this repo actually shipped. `Team` was built
without `output_schema`, so the leader returned the right JSON as a *string*
and lab 2's second half died with

    AttributeError: 'str' object has no attribute 'department'

The members each had the schema. The team did not, and nothing anywhere said
so — the single-agent path was covered, the team path was not, and the gap sat
there until a person ran it.

Everything below is structural: no API key, no model call, milliseconds. That
is the level at which "did you wire it up correctly" belongs. Whether the
router picks the *right* specialist is a different question, and it lives in
`evals/`, because it needs a model to answer.
"""

from __future__ import annotations

import pytest
from agno.team.mode import TeamMode

from college_agent.schemas import TriageResult
from college_agent.team import (
    build_accounts_agent,
    build_examinations_agent,
    build_hostel_agent,
    build_triage_team,
)

SPECIALISTS = (build_accounts_agent, build_examinations_agent, build_hostel_agent)


@pytest.fixture
def team(monkeypatch):
    """A real Team object. Constructing one costs nothing — no call is made."""
    monkeypatch.setenv("GOOGLE_API_KEY", "dummy-no-call-is-made")
    return build_triage_team()


class TestTheContract:
    def test_the_team_itself_has_the_output_schema(self, team):
        """The regression. Members having it is not enough — the leader answers."""
        assert team.output_schema is TriageResult

    @pytest.mark.parametrize("build", SPECIALISTS, ids=lambda f: f.__name__)
    def test_every_specialist_has_it_too(self, build, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "dummy-no-call-is-made")
        assert build().output_schema is TriageResult


class TestTheShape:
    def test_it_routes_rather_than_collaborates(self, team):
        """`route` is what makes this one extra call, not several."""
        assert team.mode == TeamMode.route

    def test_three_specialists(self, team):
        assert len(team.members) == 3

    def test_members_are_named(self, team):
        """The router picks by name, so an unnamed member is unroutable."""
        for member in team.members:
            assert member.name

    def test_specialists_carry_fewer_tools_than_the_single_agent(self, team, monkeypatch):
        """The whole justification for splitting.

        If a specialist ends up holding every tool, the split bought nothing
        and you are paying an extra model call for the privilege.
        """
        monkeypatch.setenv("GOOGLE_API_KEY", "dummy-no-call-is-made")
        from college_agent.agent import TRIAGE_TOOLS

        for member in team.members:
            assert 0 < len(member.tools or []) < len(TRIAGE_TOOLS)
