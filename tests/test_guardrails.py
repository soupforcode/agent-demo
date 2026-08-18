"""Guardrails are the one part of the agent that must never be probabilistic.

Everything else here is best-effort: the model usually routes correctly, usually
escalates when it should. These checks are the exceptions — they run before the
model and either fire or don't, so they can be tested like ordinary code.

Which means they should be. An instruction that fails 5% of the time is a
nuisance; a privacy control that fails 5% of the time is an incident.
"""

from __future__ import annotations

import pytest
from agno.exceptions import InputCheckError
from agno.run.agent import RunInput

from college_agent.guardrails import (
    ThirdPartyRequestGuardrail,
    build_pii_guardrail,
    default_guardrails,
)


def _blocks(guard, text: str) -> bool:
    try:
        guard.check(RunInput(input_content=text))
        return False
    except InputCheckError:
        return True


class TestThirdPartyRequests:
    """Records go to the student. Not to parents, however reasonable they sound."""

    @pytest.mark.parametrize(
        "ticket",
        [
            "I am Rohit Menon's father. Please send me his attendance record.",
            "I'm the mother of CS21B014, please share her results.",
            "Please share my son's exam results for this semester.",
            "Writing on behalf of my ward regarding his transcript.",
            "This is his guardian, I need his fee receipt.",
        ],
    )
    def test_blocks_requests_about_someone_else(self, ticket):
        assert _blocks(ThirdPartyRequestGuardrail(), ticket)

    @pytest.mark.parametrize(
        "ticket",
        [
            "I can't download my hall ticket. Roll no CS22B007.",
            "My fees show pending though I paid by NEFT. Roll no CS21B014.",
            "I need a bonafide certificate for my passport.",
            "What number am I on the hostel waiting list?",
        ],
    )
    def test_lets_students_ask_about_themselves(self, ticket):
        assert not _blocks(ThirdPartyRequestGuardrail(), ticket)

    def test_the_error_explains_itself(self):
        """A blocked ticket still has to tell a human what happened and why."""
        with pytest.raises(InputCheckError) as exc:
            ThirdPartyRequestGuardrail().check(
                RunInput(input_content="I am her father, send me her results.")
            )
        message = str(exc.value)
        assert "records" in message.lower()
        assert "human" in message.lower()

    @pytest.mark.asyncio
    async def test_async_path_matches_sync(self):
        guard = ThirdPartyRequestGuardrail()
        with pytest.raises(InputCheckError):
            await guard.async_check(RunInput(input_content="I am his father, send me his marks."))
        # And the safe case stays safe on the async path too.
        await guard.async_check(RunInput(input_content="My own hall ticket is missing."))


class TestPII:
    """Free-tier input is training data. Stop personal identifiers at the door."""

    @pytest.mark.parametrize(
        "ticket",
        [
            "My aadhaar is 1234 5678 9012, please update my records.",
            "My aadhaar number 123456789012 needs correcting.",
            "My PAN is ABCDE1234F, use it for the refund.",
        ],
    )
    def test_blocks_indian_identifiers(self, ticket):
        assert _blocks(build_pii_guardrail(), ticket)

    def test_allows_college_email(self):
        """Every legitimate ticket contains one — blocking them blocks everything."""
        assert not _blocks(
            build_pii_guardrail(), "Email me at cs21b001@college.edu about the bonafide."
        )

    def test_allows_a_plain_roll_number(self):
        assert not _blocks(build_pii_guardrail(), "Roll no CS22B007 cannot get a hall ticket.")

    def test_refuses_rather_than_masking(self):
        """A masked value looks like it worked. For teaching, refusing is clearer."""
        assert build_pii_guardrail().mask_pii is False


class TestDefaults:
    def test_default_set_covers_both(self):
        guards = default_guardrails()
        assert len(guards) == 2
        assert any(isinstance(g, ThirdPartyRequestGuardrail) for g in guards)

    def test_cheapest_check_runs_first(self):
        """Ordering is deliberate: the certain, regex-only check goes first."""
        assert isinstance(default_guardrails()[0], ThirdPartyRequestGuardrail)


class TestBlockedTicketReachesTheAPIProperly:
    """The failure mode this nearly shipped with.

    Agno swallows `InputCheckError` and returns `RunOutput(status=error)` whose
    `content` is a plain string. Without handling, `/triage` would try to
    validate a `str` against `TriageResult` and return 500 — a server error for
    something that is not an error at all.
    """

    def test_triage_raises_rather_than_returning_a_string(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "dummy-guardrail-fires-first")
        monkeypatch.setenv("COLLEGE_AGENT_PROVIDER", "google")

        import college_agent.agent as agent_mod
        from college_agent.guardrails import TicketBlocked

        agent_mod._default_agent = None  # rebuild with the dummy key
        with pytest.raises(TicketBlocked):
            agent_mod.triage("I am her father, please send me her exam results.")
        agent_mod._default_agent = None

    def test_a_normal_ticket_is_not_blocked(self, monkeypatch):
        """The guardrail must not swallow legitimate tickets.

        A dummy key means the model call itself fails — that's fine and is the
        point: we only care that we got *past* the guardrail.
        """
        monkeypatch.setenv("GOOGLE_API_KEY", "dummy-guardrail-fires-first")

        import college_agent.agent as agent_mod
        from college_agent.guardrails import TicketBlocked

        agent_mod._default_agent = None
        try:
            agent_mod.triage("I cannot download my hall ticket. Roll no CS22B007.")
        except TicketBlocked:  # pragma: no cover
            pytest.fail("A legitimate student ticket was blocked by a guardrail.")
        except Exception:
            pass  # reached the model and failed on the dummy key — as expected
        finally:
            agent_mod._default_agent = None


class TestAPIStatusCodes:
    """Three outcomes, three different meanings — they must not collapse into one.

    A refusal is not a failure. A provider outage is not a client mistake.
    Returning 500 for either would be a lie to whoever is on the other end.
    """

    def _client(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "dummy-key-guardrails-fire-first")
        from fastapi.testclient import TestClient

        import college_agent.agent as agent_mod
        from college_agent.api import app

        agent_mod._default_agent = None
        return TestClient(app)

    def test_third_party_request_is_403_not_500(self, monkeypatch):
        r = self._client(monkeypatch).post(
            "/triage", json={"message": "I am Rohit Menon's father. Send me his results."}
        )
        assert r.status_code == 403
        assert "records" in r.json()["detail"].lower()

    def test_pii_is_403(self, monkeypatch):
        r = self._client(monkeypatch).post(
            "/triage", json={"message": "My aadhaar is 1234 5678 9012, update my records."}
        )
        assert r.status_code == 403

    def test_provider_failure_is_502_not_403(self, monkeypatch):
        """A dead provider must not be reported as a policy refusal."""
        r = self._client(monkeypatch).post(
            "/triage", json={"message": "I cannot download my hall ticket. Roll no CS22B007."}
        )
        assert r.status_code == 502
        assert "records" not in r.json()["detail"].lower()


class TestNobodyBypassesRunTriage:
    """A regression guard for the bug that shipped in this file's first version.

    Adding `pre_hooks` changed what `agent.run().content` returns: a
    `TriageResult` normally, a plain `str` when a guardrail fires or the model
    fails. Every existing caller assumed the first, and only one of them got
    fixed — so `make lab2` died with

        AttributeError: 'str' object has no attribute 'department'

    `run_triage()` in agent.py is now the single place that narrows the type.
    This test fails if anyone reintroduces a direct call, which is a much
    kinder way to find out than a crash mid-workshop.
    """

    def _sources(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        for folder in ("labs", "evals"):
            yield from (root / folder).rglob("*.py")

    def test_no_lab_or_eval_calls_run_content_directly(self):
        import re

        # `.run(...).content` on an agent or team, in one expression.
        pattern = re.compile(r"\b(agent|team|\w*_agent)\.run\([^)]*\)\.content")

        offenders = []
        for path in self._sources():
            for lineno, line in enumerate(path.read_text().splitlines(), 1):
                if line.lstrip().startswith("#"):
                    continue  # comments explaining the trap are fine
                if pattern.search(line):
                    offenders.append(f"{path.name}:{lineno}")

        assert not offenders, (
            "These call agent.run(...).content directly, which returns a str "
            "when a guardrail fires or the model fails:\n  "
            + "\n  ".join(offenders)
            + "\n\nUse run_triage(agent, ticket) from college_agent.agent instead."
        )

    def test_run_triage_is_the_narrowing_point(self):
        """It must return a TriageResult or raise — never hand back a string."""
        import inspect

        from college_agent.agent import run_triage

        source = inspect.getsource(run_triage)
        assert "isinstance(result, TriageResult)" in source
        assert "enforce(" in source
