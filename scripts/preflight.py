#!/usr/bin/env python3
"""Run this before the workshop. It tells you exactly what's broken, if anything.

    make preflight

Every check here exists because it is something that has actually gone wrong
for someone, and each one prints the fix rather than just the failure.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

GREEN, RED, YELLOW, DIM, BOLD, RESET = (
    "\033[32m",
    "\033[31m",
    "\033[33m",
    "\033[2m",
    "\033[1m",
    "\033[0m",
)

failures: list[str] = []
warnings: list[str] = []


def ok(msg: str) -> None:
    print(f"  {GREEN}✓{RESET} {msg}")


def fail(msg: str, fix: str) -> None:
    print(f"  {RED}✗{RESET} {msg}")
    failures.append(f"{msg}\n{fix}")


def warn(msg: str) -> None:
    print(f"  {YELLOW}!{RESET} {msg}")
    warnings.append(msg)


def check_python() -> None:
    major, minor = sys.version_info[:2]
    if (major, minor) < (3, 10):
        fail(
            f"Python {major}.{minor} is too old.",
            "  Install Python 3.10-3.12, then re-run `make setup`.",
        )
    elif (major, minor) >= (3, 13):
        warn(f"Python {major}.{minor} is newer than this workshop was tested on (3.10-3.12).")
    else:
        ok(f"Python {major}.{minor}")


def check_sdk() -> None:
    """The deprecated-package trap.

    `google-generativeai` is dead — its repo is literally renamed
    `deprecated-generative-ai-python`. But it is what every stale tutorial and
    most AI-generated code still reaches for, so students end up with it
    installed and cannot work out why nothing matches the docs.
    """
    if importlib.util.find_spec("google.genai") is None:
        fail(
            "The `google-genai` package is missing.",
            "  Run: make setup",
        )
    else:
        ok("google-genai (the current SDK) is installed")

    if importlib.util.find_spec("google.generativeai") is not None:
        warn(
            "The DEPRECATED `google-generativeai` package is also installed.\n"
            "      It still works, so it will quietly shadow tutorials and confuse you.\n"
            "      Remove it:  uv pip uninstall google-generativeai\n"
            "      Remember: `from google import genai` is right,\n"
            "                `import google.generativeai` is the dead one."
        )

    if importlib.util.find_spec("agno") is None:
        fail("The `agno` package is missing.", "  Run: make setup")
    else:
        import agno

        version = getattr(agno, "__version__", "unknown")
        if version == "2.9.0":
            ok(f"agno {version}")
        else:
            warn(
                f"agno {version} is installed, but this workshop is written against 2.9.0.\n"
                "      Agno v2 broke most of v1's API and ships every few days.\n"
                "      Run `make setup` to get the pinned version."
            )


def check_key() -> None:
    google_key = os.getenv("GOOGLE_API_KEY", "").strip()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()

    if google_key:
        ok(f"GOOGLE_API_KEY is set ({google_key[:6]}…{google_key[-4:]})")
        if gemini_key and gemini_key != google_key:
            warn(
                "GEMINI_API_KEY is also set, to a different value. Agno ignores it, "
                "but the raw Google SDK in lab 1 may not — keep them the same or "
                "unset GEMINI_API_KEY."
            )
        return

    if gemini_key:
        fail(
            "You've set GEMINI_API_KEY, but Agno only reads GOOGLE_API_KEY.",
            "  Google's own quickstart tells you GEMINI_API_KEY. Agno disagrees,\n"
            "  and Agno is what makes the call.\n"
            "  Fix: edit .env and rename it to GOOGLE_API_KEY",
        )
        return

    fail(
        "GOOGLE_API_KEY is not set.",
        "  1. Get a free key: https://aistudio.google.com/apikey\n"
        "  2. cp .env.example .env\n"
        "  3. Paste the key after GOOGLE_API_KEY= in .env\n"
        "  4. Re-run: make preflight",
    )


def check_database() -> None:
    try:
        from college_agent.data.seed import DB_PATH, build

        build(quiet=True)
        ok(f"College database built ({DB_PATH.name})")
    except Exception as exc:  # noqa: BLE001
        fail(f"Could not build the college database: {exc}", "  Run: make clean && make setup")


def check_tools() -> None:
    """Tools are plain Python — they must work with no API key at all."""
    try:
        from college_agent.tools import check_fee_status, search_policy

        assert "CS21B014" in check_fee_status("CS21B014")
        assert "fifteen days" in search_policy("re-evaluation")
        ok("Tools work offline (no API key needed)")
    except Exception as exc:  # noqa: BLE001
        fail(f"Tools are broken: {exc}", "  Run: make clean && make setup")


def check_live_call() -> None:
    """One real call. This is the check that actually proves you're ready."""
    if any("GOOGLE_API_KEY" in f for f in failures):
        print(f"  {DIM}- Skipping the live call — no API key yet.{RESET}")
        return

    from college_agent.config import DEFAULT_MODEL, FALLBACK_MODELS

    model_id = os.getenv("COLLEGE_AGENT_MODEL") or DEFAULT_MODEL

    try:
        import logging as _logging

        # The SDK logs an unrelated suggestion about automatic function calling
        # on every generate_content call. Not useful here, and it makes a clean
        # preflight look like it went wrong.
        _logging.getLogger("google_genai.models").setLevel(_logging.ERROR)

        from google import genai

        client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
        resp = client.models.generate_content(
            model=model_id,
            contents="Reply with exactly one word: ready",
        )
        text = (resp.text or "").strip()
        ok(f'Live call to {model_id} succeeded (it said: "{text[:40]}")')
    except Exception as exc:  # noqa: BLE001
        message = str(exc)
        if "429" in message or "RESOURCE_EXHAUSTED" in message:
            warn(
                f"{model_id} answered with a rate limit (429). Your key works — you've "
                "just used your quota for now. Wait a few minutes and re-run.\n"
                "      Free-tier daily quota resets at midnight US Pacific "
                "(about 12:30 PM IST)."
            )
        elif "404" in message or "NOT_FOUND" in message:
            others = ", ".join(m for m in FALLBACK_MODELS if m != model_id)
            fail(
                f"The model {model_id!r} was not found.",
                "  Google retires model IDs periodically. Set a different one in .env:\n"
                f"      COLLEGE_AGENT_MODEL=<one of: {others}>",
            )
        elif "API_KEY_INVALID" in message or "401" in message or "403" in message:
            fail(
                "Your API key was rejected.",
                "  Generate a fresh one at https://aistudio.google.com/apikey\n"
                "  and paste it into .env — check you didn't copy a trailing space.",
            )
        else:
            fail(f"The live call failed: {type(exc).__name__}: {message[:200]}", "  ")


def main() -> int:
    print(f"\n{BOLD}Pre-flight check{RESET}  {DIM}Architecting Autonomous Intelligence{RESET}\n")

    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")

    for name, check in [
        ("Environment", check_python),
        ("Packages", check_sdk),
        ("API key", check_key),
        ("Data", check_database),
        ("Tools", check_tools),
        ("Model", check_live_call),
    ]:
        print(f"{DIM}{name}{RESET}")
        check()
        print()

    if failures:
        print(f"{RED}{BOLD}PREFLIGHT FAILED{RESET} — {len(failures)} problem(s) to fix:\n")
        for i, f in enumerate(failures, 1):
            print(f"{RED}{i}.{RESET} {f}\n")
        return 1

    if warnings:
        print(f"{GREEN}{BOLD}PREFLIGHT PASSED{RESET} with {len(warnings)} warning(s) above.\n")
    else:
        print(f"{GREEN}{BOLD}PREFLIGHT PASSED{RESET} — you're ready for the workshop.\n")

    print(f"{DIM}Next:  make lab1{RESET}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
