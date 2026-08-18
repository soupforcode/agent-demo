#!/usr/bin/env python3
"""Build the step-1..step-7 teaching branch series.

One linear chain of commits, a branch pointing at each, ending with a tree
identical to main. Built in a detached worktree so the real working directory
is untouched.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Paths are derived from this file's location so the script works from any
# clone, which is the point of it living in the repo rather than in a scratch
# directory somewhere. Only the build's own temporaries go outside it.
REPO = Path(__file__).resolve().parents[1]
VARIANTS = Path(__file__).resolve().parent / "step_variants"
BUILD = Path(tempfile.gettempdir()) / "agent-demo-stepbuild"
SNAP = BUILD / "snap"
WT = BUILD / "stepbuild"


def run(*args, cwd=None, check=True):
    return subprocess.run(args, cwd=cwd or WT, check=check, capture_output=True, text=True)


# ---------------------------------------------------------------- file sets
CONST = [
    ".gitignore",
    ".dockerignore",
    ".env.example",
    "pyproject.toml",
    "Makefile",
    "README.md",
    "docs",
    "scripts",
    "src/college_agent/__init__.py",
    "src/college_agent/config.py",
    "tests/conftest.py",
]

STEPS = [
    {
        "branch": "step-1-agent",
        "title": "An agent",
        # No labs here. Every lab1 script imports college_agent.tools to
        # demonstrate tool calling, and tools do not exist until step 3 — so
        # they ship there. `make lab1` on this branch hits the Makefile's
        # `needs` guard and points at step-3-tools, which is the behaviour
        # you want anyway: this step is "an agent with no tools".
        "adds": [
            "tests/test_config.py",
        ],
        "agent": "agent_step1.py",
        "new": "A model, some instructions, and nothing else. No tools, no schema.",
        "run": "python -m college_agent.agent",
        "look": [
            "It answers in prose — readable, but no system can route on it.",
            "It has no way to look up CS22B007, so anything it says about that",
            "student is invented. Both problems get fixed, one per step.",
        ],
    },
    {
        "branch": "step-2-structured",
        "title": "A contract",
        "adds": ["src/college_agent/schemas.py", "tests/test_schemas.py"],
        "agent": "agent_step2.py",
        "new": "output_schema=TriageResult — one parameter.",
        "run": "python -m college_agent.agent",
        "look": [
            "You now get a validated object you could route, count and test.",
            "It is also still invented — the agent has no tools yet. Structure",
            "buys parseability, not truth, and it makes a wrong answer look",
            "considerably more authoritative than prose did.",
        ],
    },
    {
        "branch": "step-3-tools",
        "title": "Tools",
        "adds": [
            "src/college_agent/tools.py",
            "src/college_agent/data",
            "src/college_agent/kb",
            "tests/test_tools.py",
            "labs/lab1_fundamentals",
            "labs/lab2_workflow/01_structured_triage.py",
        ],
        "agent": "main-no-guardrails",
        "new": "Six tools over the college database, and the agent that uses them.",
        "run": "make lab2",
        "look": [
            "Now it looks things up. The hall-ticket ticket should route to",
            "accounts, not examinations — the block is unpaid fees, and only",
            "the tool call reveals that.",
            "Read the docstrings in tools.py: they are prompt text, not comments.",
        ],
    },
    {
        "branch": "step-4-guardrails",
        "title": "Guardrails",
        "adds": ["src/college_agent/guardrails.py", "tests/test_guardrails.py"],
        "agent": "main",
        "new": "Checks that run before the model — PII, and third-party record requests.",
        "run": "make test",
        "look": [
            "An instruction is advice; a guardrail is a rule. The agent was",
            "already told to refuse third-party requests. Now it cannot comply",
            "even if a cleverly worded ticket talks it into trying.",
            "They run before the API call, so a blocked ticket costs zero quota.",
        ],
    },
    {
        "branch": "step-5-team",
        "title": "One agent, or several",
        "adds": [
            "src/college_agent/team.py",
            "tests/test_team.py",
            "labs/lab2_workflow/02_routing_team.py",
        ],
        "agent": "main",
        "new": "A router in front of three specialists.",
        "run": "make lab2",
        "look": [
            "This is a comparison, not an upgrade. The team roughly doubles",
            "your model calls — router, then specialist.",
            "Ask honestly whether it did better, or just cost more. For six",
            "tools and one domain, one agent is usually enough.",
        ],
    },
    {
        "branch": "step-6-evals",
        "title": "Proving it works",
        "adds": [
            "evals",
            "tests/test_evals.py",
            "tests/test_scorer.py",
            "labs/lab3_eval",
        ],
        "agent": "main",
        "new": "Ten golden cases, tool-call reliability, and a deliberate sabotage.",
        "run": "make lab3",
        "look": [
            "Reliability first: did it look things up, or get lucky? That check",
            "is free and deterministic, and catches what accuracy scoring cannot.",
            "Then break the agent on purpose. If the score does not move, your",
            "eval suite is decoration.",
        ],
    },
    {
        "branch": "step-7-deploy",
        "title": "Shipping it",
        "adds": [
            "src/college_agent/api.py",
            "tests/test_api.py",
            "labs/lab4_deploy",
            "Dockerfile",
            ".github",
        ],
        "agent": "main",
        "new": "A FastAPI service, AgentOS mounted onto it, a Dockerfile and CI.",
        "run": "make lab4",
        "look": [
            "/health never calls the model — a health check that costs an API",
            "request reports your provider being down as you being down.",
            "The service starts with no API key and reports itself degraded",
            "rather than crash-looping.",
            "Three outcomes, three codes: 403 refused, 502 provider down, 200 ok.",
        ],
    },
]


def step_md(i: int, spec: dict) -> str:
    n = i + 1
    nxt = STEPS[i + 1]["branch"] if i + 1 < len(STEPS) else None
    prev = STEPS[i - 1]["branch"] if i > 0 else None

    head = [
        "",
        f"  STEP {n} of {len(STEPS)} — {spec['title']}",
        "",
        f"  New here:  {spec['new']}",
        f"  Run:       {spec['run']}",
        "",
    ]
    if nxt:
        head.append(f"  Next:      git switch {nxt}")
    else:
        head.append("  Next:      nothing — this is the finished app (same as main)")
    head.append("")

    body = [
        "---",
        "",
        f"# Step {n} — {spec['title']}",
        "",
        f"**{spec['new']}**",
        "",
        "## What to look at",
        "",
    ]
    body += [f"- {line}" for line in spec["look"]]
    body += [
        "",
        "## Commands",
        "",
        "```bash",
        f"{spec['run']}",
        "make test        # the tests that exist at this step, no API key needed",
        "make diff        # exactly what this step changed vs the previous one",
        "make step        # this summary again",
        "```",
        "",
    ]
    if prev:
        body += [
            "## Where this came from",
            "",
            "```bash",
            f"git diff {prev} {spec['branch']} -- src",
            "```",
            "",
            "That diff is the lesson. Everything else is unchanged.",
            "",
        ]
    body += [
        "## Getting unstuck",
        "",
        "Nothing here is precious. If you break something:",
        "",
        "```bash",
        "git checkout .                  # undo your edits, keep the step",
        f"git switch {spec['branch']}    # or jump back to a clean copy",
        "git switch main                 # or straight to the finished app",
        "```",
        "",
    ]
    return "\n".join(head + body)


def drop_class(source: str, name: str) -> str:
    """Remove one top-level `class <name>:` block, leaving the rest intact."""
    lines = source.splitlines(keepends=True)
    start = next((i for i, ln in enumerate(lines) if ln.startswith(f"class {name}")), None)
    if start is None:
        return source
    end = next(
        (j for j in range(start + 1, len(lines)) if lines[j].startswith(("class ", "def "))),
        len(lines),
    )
    # Take the blank lines that separated it with it, so spacing stays PEP 8.
    while start > 0 and lines[start - 1].strip() == "":
        start -= 1
    kept = lines[:start] + ["\n\n"] + lines[end:] if end < len(lines) else lines[:start]
    return "".join(kept).rstrip() + "\n"


def copy_paths(paths: list[str]) -> None:
    for rel in paths:
        src, dst = SNAP / rel, WT / rel
        if not src.exists():
            sys.exit(f"missing from snapshot: {rel}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)


def _cut(text: str, start_marker: str, end_marker: str) -> str:
    """Remove everything from start_marker up to (not including) end_marker."""
    a = text.index(start_marker)
    b = text.index(end_marker, a)
    return text[:a] + text[b:]


STEP3_RUN_TRIAGE = '''def run_triage(agent, ticket: str) -> TriageResult:
    """Run one ticket through `agent` and return a TriageResult. Never a string.

    Use this instead of `agent.run(ticket).content` — everywhere.

    `Agent.run()` does not have the return type you would expect. Its
    `.content` is a `TriageResult` on the happy path, but a plain `str` when
    the model call fails, and sometimes valid JSON that simply hasn\'t been
    parsed. Code that assumes the happy path gets

        AttributeError: \'str\' object has no attribute \'department\'

    at some unrelated line, which is a miserable thing to debug.

    So the narrowing happens here, once, and callers get either a real
    TriageResult or a clear exception.

    Args:
        agent: A triage agent, or a Team — both work.
        ticket: What the student wrote.
    """
    result = agent.run(ticket).content

    if isinstance(result, str):
        # Some paths hand back the right JSON as *text* rather than a parsed
        # model — a Team whose leader answers directly is the one you\'ll meet
        # here. If it validates, take it.
        try:
            return TriageResult.model_validate_json(result)
        except ValidationError:
            pass

    if not isinstance(result, TriageResult):
        raise RuntimeError(f"The agent did not return a TriageResult: {str(result)[:300]}")

    return result


'''


def agent_for(kind: str) -> str:
    if kind == "main":
        return (SNAP / "src/college_agent/agent.py").read_text()
    if kind == "main-no-guardrails":
        s = (SNAP / "src/college_agent/agent.py").read_text()

        # imports
        s = s.replace("from .guardrails import default_guardrails, enforce\n", "")

        # the build_triage_agent parameter, its docstring entry, and the hook
        s = s.replace("    guardrails: bool = True,\n", "")
        s = _cut(s, "        guardrails: Run the pre-flight checks", "        debug: Print")
        s = _cut(
            s,
            "        # Checks that run BEFORE the model does",
            "        # A hard stop.",
        )

        # run_triage exists at step 3, but with nothing to enforce yet: replace
        # the whole function rather than unpicking a docstring about guardrails.
        s = _cut(s, "def run_triage(", "\n# A ready-built agent")
        s = s.replace("# A ready-built agent", STEP3_RUN_TRIAGE + "\n# A ready-built agent", 1)

        assert "guardrail" not in s.lower(), "guardrail references survived the strip"
        assert "enforce(" not in s
        return s

    return (VARIANTS / kind).read_text()


def main() -> None:
    # fresh snapshot of main
    if SNAP.exists():
        shutil.rmtree(SNAP)
    SNAP.mkdir(parents=True)
    subprocess.run(f"git archive main | tar -x -C {SNAP}", shell=True, cwd=REPO, check=True)

    # clean worktree
    if WT.exists():
        subprocess.run(["git", "worktree", "remove", "--force", str(WT)], cwd=REPO, check=False)
        shutil.rmtree(WT, ignore_errors=True)
    subprocess.run(["git", "worktree", "add", "--detach", str(WT), "main"], cwd=REPO, check=True)

    run("git", "checkout", "--orphan", "step-build")
    run("git", "rm", "-rf", "--cached", ".")
    for entry in WT.iterdir():
        if entry.name == ".git":
            continue
        shutil.rmtree(entry) if entry.is_dir() else entry.unlink()

    cumulative: list[str] = list(CONST)

    for i, spec in enumerate(STEPS):
        cumulative += spec["adds"]
        # rebuild the tree from scratch each step: guarantees exact contents
        for entry in WT.iterdir():
            if entry.name == ".git":
                continue
            shutil.rmtree(entry) if entry.is_dir() else entry.unlink()
        copy_paths(cumulative)

        (WT / "src/college_agent/agent.py").write_text(agent_for(spec["agent"]))
        (WT / "STEP.md").write_text(step_md(i, spec))

        # TestAPIStatusCodes needs api.py, which arrives at step 7. Drop that
        # one class — by name, not by truncating the rest of the file.
        #
        # It used to truncate at the marker, which silently took everything
        # below it too. TestNobodyBypassesRunTriage lives further down and
        # needs nothing but run_triage (step 4), so four branches lost the
        # test guarding the exact bug it was written for. Removing a named
        # class says what it means and cannot over-reach.
        tg = WT / "tests/test_guardrails.py"
        if tg.exists() and not (WT / "src/college_agent/api.py").exists():
            tg.write_text(drop_class(tg.read_text(), "TestAPIStatusCodes"))

        # The stitched agent.py variants leave stray blank lines, so step-3
        # used to fail `ruff format --check` while every other branch passed.
        # Format the generated tree rather than chase it after the fact.
        subprocess.run(
            [
                str(REPO / ".venv/bin/ruff"),
                "format",
                "-q",
                "src",
                "labs",
                "evals",
                "tests",
                "scripts",
            ],
            cwd=WT,
            check=False,
        )

        run("git", "add", "-A")
        run(
            "git",
            "-c",
            "user.email=subash21annadurai@gmail.com",
            "-c",
            "user.name=Subash Annadurai",
            "commit",
            "-q",
            "-m",
            f"Step {i + 1}: {spec['title']}\n\n{spec['new']}",
        )
        run("git", "branch", "-f", spec["branch"])
        print(f"  built {spec['branch']}")

    run("git", "checkout", "--detach", "HEAD")
    run("git", "branch", "-D", "step-build")
    print("\nchain built")


if __name__ == "__main__":
    main()
