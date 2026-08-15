"""LAB 3, PART 2 — Was the answer right?

    python labs/lab3_eval/02_accuracy.py

Part 1 checked the *path*. This checks the *answer*, two different ways, and
the difference between them is the point of the lab.

**Exact-match scoring.** Did `department` equal what we expected? Free,
instant, completely objective, and blind to everything that isn't a field —
it cannot tell you whether the agent leaked the waiting-list position while
routing the ticket correctly.

**LLM-as-judge.** A second model reads the answer against a written standard.
It catches everything exact-match misses, and it costs an API call per case and
is itself fallible.

Use both. Exact-match on everything you can express as a field, a judge only
for what you genuinely can't.

Where judges let you down
-------------------------
They are lenient about confident-sounding wrong answers — fluency reads as
correctness to a language model, same as it does to a tired human. They drift
between runs. And they're weakest exactly where you need them most, on
borderline cases, because that's where the written criteria stop being crisp.

So: read the failures yourself. A judge is evidence, not a verdict.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "evals"))

from agno.eval.agent_as_judge import AgentAsJudgeEval  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

from cases import CASES  # noqa: E402
from college_agent.agent import build_triage_agent  # noqa: E402
from college_agent.config import describe_config, get_model  # noqa: E402

console = Console()


def main() -> None:
    if not os.getenv("GOOGLE_API_KEY", "").strip():
        console.print("\n[red]GOOGLE_API_KEY is not set.[/red] Run `make preflight`.\n")
        raise SystemExit(1)

    console.print(f"\n[bold]Accuracy: was it right?[/bold]  [dim]{describe_config()}[/dim]\n")

    agent = build_triage_agent()

    table = Table(show_lines=False, expand=True)
    table.add_column("Case", ratio=3)
    table.add_column("Dept", ratio=2)
    table.add_column("Human?", ratio=2)
    table.add_column("Judge", ratio=1)

    exact_hits = 0
    judge_hits = 0

    for case in CASES:
        with console.status(f"[dim]{case.name}…[/dim]"):
            result = agent.run(case.ticket).content

            # --- exact match: free and objective ---------------------------
            dept_ok = result.department == case.expected_department
            human_ok = result.needs_human == case.expected_needs_human
            exact_hits += dept_ok and human_ok

            # --- the judge: catches what fields can't ----------------------
            # NOTE the explicit model. Agno's default judge is OpenAI, and
            # without this line the suite would demand a key nobody has.
            judge = AgentAsJudgeEval(
                name=case.name,
                criteria=case.criteria,
                model=get_model(temperature=0.0),
                scoring_strategy="binary",
                telemetry=False,
            )
            verdict = judge.run(input=case.ticket, output=str(result.model_dump()))
            judged_ok = bool(verdict and verdict.results and verdict.results[0].passed)
            judge_hits += judged_ok

        table.add_row(
            case.name,
            f"[green]{result.department}[/green]"
            if dept_ok
            else f"[red]{result.department}[/red] [dim]want {case.expected_department}[/dim]",
            ("yes" if result.needs_human else "no")
            if human_ok
            else f"[red]{'yes' if result.needs_human else 'no'}[/red] "
            f"[dim]want {'yes' if case.expected_needs_human else 'no'}[/dim]",
            "[green]pass[/green]" if judged_ok else "[red]fail[/red]",
        )

    console.print(table)
    total = len(CASES)
    console.print(
        f"\n  exact match  [bold]{exact_hits}/{total}[/bold]"
        f"      judge  [bold]{judge_hits}/{total}[/bold]\n"
    )

    console.print(
        "[dim]"
        "Where the two columns disagree is the interesting part. A case that\n"
        "passes exact-match but fails the judge usually means the right\n"
        "department for the wrong reason. The reverse usually means your\n"
        "criteria are looser than your expected field.\n"
        "\n"
        "Run this twice. The scores will probably differ slightly — same code,\n"
        "same data, different numbers. That is normal and it is why a single\n"
        "eval run is not evidence of an improvement.\n"
        "\n"
        "Try this:\n"
        "  · Add a case of your own to evals/cases.py. Find a ticket the agent\n"
        "    gets wrong — that is a more useful contribution than one it gets\n"
        "    right.\n"
        "  · Swap the model: COLLEGE_AGENT_MODEL=gemini-3.5-flash make lab3\n"
        "    Does a stronger model score better? By enough to justify being\n"
        "    slower and costing more? Measure it rather than assuming.\n"
        "\n"
        "Next: 03_break_it.py — the part where you sabotage your own agent.[/dim]\n"
    )


if __name__ == "__main__":
    main()
