"""The service must behave when it's misconfigured.

Every test here runs with no API key, which is the interesting case. Anyone can
make a service work when everything is present; what separates a deployable
service from a script is what it does when something is missing.
"""

from __future__ import annotations

import pytest


def _any_key_set() -> bool:
    """True if the *selected* provider has a key — whichever provider that is."""
    from college_agent.config import api_key_present

    return api_key_present()


pytestmark = pytest.mark.skipif(
    _any_key_set(),
    reason=(
        "These assert on the no-API-key path; unset the selected provider's key "
        "(GOOGLE_API_KEY or OPENAI_API_KEY) to run them."
    ),
)


class TestHealth:
    def test_health_responds(self, client):
        assert client.get("/health").status_code == 200

    def test_health_reports_degraded_without_a_key(self, client):
        from college_agent.config import PROVIDERS, get_provider

        body = client.get("/health").json()
        assert body["status"] == "degraded"
        assert body["api_key_configured"] is False
        # Names the key for the *selected* provider, not a hard-coded one.
        assert PROVIDERS[get_provider()]["env_var"] in body["detail"]

    def test_health_does_not_call_the_model(self, client, monkeypatch):
        """A health check that costs an API request is a liability.

        It drains quota, and it reports your *provider* being down as *you*
        being down. This asserts it never constructs a model at all.
        """
        import college_agent.config as config

        def explode(*args, **kwargs):
            raise AssertionError("/health must not build a model")

        monkeypatch.setattr(config, "get_model", explode)
        assert client.get("/health").status_code == 200


class TestTriageWithoutKey:
    def test_returns_503_not_500(self, client):
        """Missing configuration is 'unavailable', not 'internal error'."""
        response = client.post("/triage", json={"message": "I need help with fees"})
        assert response.status_code == 503

    def test_the_error_explains_the_fix(self, client):
        from college_agent.config import PROVIDERS, get_provider

        spec = PROVIDERS[get_provider()]
        detail = client.post("/triage", json={"message": "help"}).json()["detail"]
        assert spec["env_var"] in detail
        assert spec["signup"] in detail  # tells you where to go

    def test_no_stack_trace_leaks(self, client):
        detail = client.post("/triage", json={"message": "help"}).json()["detail"]
        assert "Traceback" not in detail
        assert ".py" not in detail


class TestValidation:
    """Rejecting bad input at the edge costs nothing. Finding out from the model costs a call."""

    def test_rejects_an_empty_message(self, client):
        assert client.post("/triage", json={"message": ""}).status_code == 422

    def test_rejects_a_missing_message(self, client):
        assert client.post("/triage", json={}).status_code == 422

    def test_rejects_an_oversized_message(self, client):
        assert client.post("/triage", json={"message": "x" * 5000}).status_code == 422

    def test_validation_happens_before_the_agent(self, client):
        """422 rather than 503 proves nothing reached the agent."""
        assert client.post("/triage", json={"message": ""}).status_code == 422


class TestDiscovery:
    def test_root_points_somewhere_useful(self, client):
        assert "/docs" in str(client.get("/").json())

    def test_openapi_schema_is_generated(self, client):
        schema = client.get("/openapi.json").json()
        assert "/triage" in schema["paths"]

    def test_triage_response_is_documented(self, client):
        """The schema is the contract — it belongs in the API docs."""
        schema = client.get("/openapi.json").json()
        assert "TriageResult" in str(schema["paths"]["/triage"])
