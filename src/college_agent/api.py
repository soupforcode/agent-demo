"""The agent as an HTTP service.

Two layers, deliberately:

**Your endpoint.** `POST /triage` is ordinary FastAPI — a Pydantic request
model, a Pydantic response model, an error path. Nothing framework-specific.
This is what you'd write for any service, and it's what you'd keep if you
replaced Agno tomorrow.

**AgentOS.** Mounted onto that same app with `base_app=`. It adds ~80 endpoints
for runs, sessions, memory and evals that you didn't have to write. Start the
server and read `/docs` to see what appeared.

The order matters: your endpoint is the product, AgentOS is infrastructure
underneath it. Building it the other way round — starting from the framework's
server and bolting your API on — leaves you unable to change frameworks without
changing your public interface.

One deliberate design choice
----------------------------
This module imports and starts **without** an API key. `/health` works, the app
object exists, the tests can import it. Only `/triage` needs a key, and without
one it returns a clean 503 explaining what's missing.

That is how a service should behave. Crashing at import because a config value
is absent means your container dies in a restart loop and your health check
never gets to tell anyone why.
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from .config import PROVIDERS, MissingAPIKeyError, api_key_present, describe_config, get_provider
from .schemas import TriageRequest, TriageResult

log = logging.getLogger("college_agent.api")

app = FastAPI(
    title="College Administration Triage",
    version="0.1.0",
    description=(
        "Triages incoming student tickets: decides which department owns a ticket, "
        "how urgent it is, and whether a human needs to look at it.\n\n"
        "Built for the *Architecting Autonomous Intelligence* workshop."
    ),
)


# --------------------------------------------------------------------------
# Health
# --------------------------------------------------------------------------


@app.get("/health", tags=["ops"])
def health() -> dict:
    """Liveness and configuration check.

    Deliberately does not call the model. A health check that costs an API
    request is a health check that will exhaust your quota, and one that fails
    when your *provider* is down rather than when *you* are down.
    """
    key_present = api_key_present()
    try:
        env_var = PROVIDERS[get_provider()]["env_var"]
    except Exception:  # noqa: BLE001 - an invalid provider is still a health answer
        env_var = "COLLEGE_AGENT_PROVIDER"
    return {
        "status": "ok" if key_present else "degraded",
        "api_key_configured": key_present,
        "config": describe_config(),
        "detail": ("Ready." if key_present else f"{env_var} is not set — /triage will return 503."),
    }


# --------------------------------------------------------------------------
# The endpoint that matters
# --------------------------------------------------------------------------


@app.post("/triage", response_model=TriageResult, tags=["triage"])
def triage_endpoint(request: TriageRequest) -> TriageResult:
    """Triage one student ticket.

    Returns the structured decision: which department, how urgent, what to do
    next, and whether a human needs to be involved.
    """
    # Imported here rather than at module scope so that importing this module
    # never requires an API key.
    from .agent import triage

    try:
        return triage(request.message, request.student_id)
    except MissingAPIKeyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - deliberately broad, see below
        # An agent can fail in ways a normal service can't: a rate limit, a
        # refused schema, a model that won't stop calling tools. None of those
        # should return a stack trace to whoever is on the other end.
        log.exception("Triage failed")
        raise HTTPException(
            status_code=502,
            detail=f"The agent could not complete this triage: {type(exc).__name__}: {exc}",
        ) from exc


@app.get("/", include_in_schema=False)
def root() -> JSONResponse:
    return JSONResponse(
        {
            "service": "College Administration Triage",
            "try": "POST /triage  ·  GET /health  ·  GET /docs",
        }
    )


# --------------------------------------------------------------------------
# AgentOS — mounted onto the app above
# --------------------------------------------------------------------------
# Skipped when there's no API key, because constructing the agents needs one.
# The service still starts; you just don't get the extra endpoints.

agent_os = None

if api_key_present():
    try:
        from agno.os import AgentOS

        from .agent import build_triage_agent
        from .team import build_triage_team

        agent_os = AgentOS(
            id="college-admin-triage",
            description="College administration ticket triage",
            agents=[build_triage_agent()],
            teams=[build_triage_team()],
            # Add AgentOS's routes to OUR app rather than replacing it.
            base_app=app,
            # If AgentOS ever wants a path we've already defined, ours wins.
            on_route_conflict="preserve_base_app",
        )
        app = agent_os.get_app()
    except Exception:  # noqa: BLE001
        # AgentOS is a bonus. If it can't start, the /triage endpoint — the
        # actual product — should still work.
        log.warning("AgentOS could not be mounted; core endpoints still available", exc_info=True)
else:
    log.warning(
        "No API key for the selected provider — starting without AgentOS. /triage will return 503."
    )


def main() -> None:
    """Entry point for `make serve`."""
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    print(f"\n  College Triage API   http://localhost:{port}")
    print(f"  Interactive docs     http://localhost:{port}/docs")
    print(f"  Health               http://localhost:{port}/health\n")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
