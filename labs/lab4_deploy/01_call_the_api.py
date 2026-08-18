"""LAB 4 — From a script to a service.

    make lab4        (or: python labs/lab4_deploy/01_call_the_api.py)

Everything so far has been a script you run. Nobody uses a script you run. This
lab exercises the same agent through HTTP — the form it would actually ship in.

It runs the app in-process so you don't need a second terminal. Everything you
see here is the real application from `src/college_agent/api.py`; nothing is
mocked.

What to notice
--------------
**`/health` never calls the model.** A health check that costs an API request
is one that drains your quota and reports *your provider* being down as *you*
being down. It answers from configuration alone.

**Errors don't leak.** A rate limit, a refused schema, an agent that won't stop
calling tools — all of them become an HTTP status and a sentence, not a stack
trace on someone's screen.

**The service starts without an API key.** It reports itself degraded and
returns 503 from `/triage`. That's deliberate: a container that crashes at
import because a config value is missing dies in a restart loop and never gets
to tell anyone why.

**AgentOS came free.** Eighty-odd endpoints for runs, sessions, memory and
evals, mounted onto the same app, because we passed `base_app=`. We wrote one
endpoint; the rest is infrastructure we didn't have to build.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from fastapi.testclient import TestClient  # noqa: E402
from rich.console import Console  # noqa: E402

from college_agent.api import agent_os, app  # noqa: E402
from college_agent.config import (  # noqa: E402
    PROVIDERS,
    api_key_present,
    get_provider,
)


def key_var() -> str:
    """The env var the selected provider actually reads."""
    return PROVIDERS[get_provider()]["env_var"]


console = Console()

TICKET = {
    "message": (
        "I can't download my hall ticket, the portal shows an error. My exam is on Monday."
    ),
    "student_id": "CS22B007",
}


def main() -> None:
    client = TestClient(app)

    # --- 1. health -------------------------------------------------------
    console.print("\n[bold]GET /health[/bold]  [dim](no model call — free, instant)[/dim]")
    health = client.get("/health")
    console.print(f"  [dim]{health.status_code}[/dim] {json.dumps(health.json(), indent=2)}")

    # api_key_present() rather than a named variable: it asks config.py which
    # provider is selected and checks that one's key. Never raises, which is
    # what you want for a branch that only decides how to phrase an outcome.
    has_key = api_key_present()

    # --- 2. the endpoint that matters ------------------------------------
    console.print("\n[bold]POST /triage[/bold]")
    console.print(f"  [dim]request:[/dim] {json.dumps(TICKET)}")

    with console.status("[dim]triaging…[/dim]"):
        response = client.post("/triage", json=TICKET)

    if response.status_code == 200:
        console.print(f"  [green]{response.status_code}[/green]")
        console.print(f"  {json.dumps(response.json(), indent=2)}")
    else:
        console.print(f"  [yellow]{response.status_code}[/yellow]")
        console.print(f"  {json.dumps(response.json(), indent=2)}")
        if not has_key:
            console.print(
                "\n  [dim]That 503 is the service behaving correctly without a key:\n"
                "  it started, it's serving, and it's telling you precisely what's\n"
                f"  missing. Set {key_var()} and run again for a real triage.[/dim]"
            )

    # --- 3. validation ---------------------------------------------------
    console.print("\n[bold]POST /triage[/bold]  [dim](empty message — should be rejected)[/dim]")
    bad = client.post("/triage", json={"message": ""})
    console.print(f"  [dim]{bad.status_code}[/dim] — FastAPI rejected it before the agent ran.")
    console.print(
        "  [dim]Validation at the edge is free. Letting a bad request reach the\n"
        "  model costs you an API call to find out what Pydantic knew already.[/dim]"
    )

    # --- 4. what AgentOS added -------------------------------------------
    console.print("\n[bold]What AgentOS mounted[/bold]")
    if agent_os is not None:
        paths = sorted({getattr(r, "path", "") for r in agent_os.get_routes()})
        console.print(f"  [green]{len(paths)} endpoints[/green], including:")
        for p in [
            p for p in paths if any(k in p for k in ("/agents", "/sessions", "/eval", "/knowledge"))
        ][:8]:
            console.print(f"    [dim]{p}[/dim]")
        console.print("  [dim]We wrote /triage. Everything above came from base_app=.[/dim]")
    else:
        console.print(
            "  [dim]Not mounted — needs an API key to build the agents.\n"
            "  The core service works regardless, which is the point.[/dim]"
        )

    # --- what's next -----------------------------------------------------
    console.print(
        "\n[dim]" + "─" * 68 + "\n"
        "Now run it properly:\n"
        "\n"
        "  make serve                    then open http://localhost:8000/docs\n"
        "\n"
        "  curl -X POST localhost:8000/triage \\\n"
        "       -H 'Content-Type: application/json' \\\n"
        '       -d \'{"message": "I need a bonafide certificate", "student_id": "CE22B012"}\'\n'
        "\n"
        "Then containerise it:\n"
        "\n"
        "  make docker                   builds the image and runs it on :8000\n"
        "\n"
        "Then let CI hold the line:\n"
        "\n"
        "  .github/workflows/ci.yml runs the tests and the keyless evals on every\n"
        "  push. Add GOOGLE_API_KEY or OPENAI_API_KEY as a repository secret and\n"
        "  it runs the live\n"
        "  eval suite too — so a prompt change that quietly breaks routing fails\n"
        "  the build instead of reaching users.\n"
        "\n"
        "Try this:\n"
        "  · Open /docs and call /triage from the browser.\n"
        "  · Break something in agent.py, run `make test`, watch CI-style checks\n"
        "    fail locally before you push.\n"
        "  · Look at what /health does NOT do. Then think about what your own\n"
        "    health checks call.[/dim]\n"
    )


if __name__ == "__main__":
    main()
