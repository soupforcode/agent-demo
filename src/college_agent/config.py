"""Model configuration — the *only* place in this repo that builds a model.

Why one file?
-------------
Agno quietly falls back to OpenAI in three separate places:

  1. `Agent(model=None)`            -> OpenAIResponses
  2. `AccuracyEval` / `AgentAsJudgeEval` judge -> OpenAIChat
  3. `ChromaDb` / `LanceDb` embedder -> OpenAIEmbedder

None of those are wrong of Agno — they're just a different default than ours.
But in a Gemini-only setup they're nasty, because everything *looks* configured
right up until something abruptly demands OPENAI_API_KEY, usually halfway
through a lab.

So: nothing else in this repo constructs a model. Everything imports
`get_model()` from here. That's a pattern worth stealing for real projects —
pin your providers in one place, because your dependencies have opinions about
defaults that you probably don't share.
"""

from __future__ import annotations

import os
from pathlib import Path

from agno.models.google import Gemini
from dotenv import load_dotenv

# Load .env from the repo root, wherever we're invoked from.
REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")

# --------------------------------------------------------------------------
# Model choice
# --------------------------------------------------------------------------
# flash-lite is the cheapest and fastest Gemini, and has the most generous
# free-tier rate limits. That matters more than raw capability here: an agent
# makes 5-15 model calls to answer *one* ticket, so the limit you hit first is
# requests-per-minute, not intelligence.
#
# Module 3 has you swap this for a stronger model and *measure* what changes,
# rather than taking anyone's word for it.
DEFAULT_MODEL = "gemini-3.5-flash-lite"

# Known-good alternatives, in rough order of capability. If the default ever
# 404s on you (Google retires model IDs), `make preflight` will point you here.
FALLBACK_MODELS = (
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
)

# Where cached model responses live. Caching is on by default: re-running the
# same prompt while you're debugging then costs zero quota, which is the
# difference between finishing the lab and running out of requests.
CACHE_DIR = REPO_ROOT / ".cache" / "model"


class MissingAPIKeyError(RuntimeError):
    """Raised when GOOGLE_API_KEY isn't usable, with an actually helpful message."""


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def check_api_key() -> str:
    """Return the API key, or raise with an explanation of how to fix it.

    Agno's Gemini class *logs* a missing key rather than raising, so without
    this you'd discover the problem several layers down as a confusing
    ModelProviderError. We'd rather fail immediately and say why.
    """
    key = os.getenv("GOOGLE_API_KEY", "").strip()
    if key:
        return key

    # The single most common setup mistake. Google's own quickstart tells you
    # to set GEMINI_API_KEY; Agno only ever reads GOOGLE_API_KEY.
    if os.getenv("GEMINI_API_KEY", "").strip():
        raise MissingAPIKeyError(
            "You've set GEMINI_API_KEY, but Agno only reads GOOGLE_API_KEY.\n"
            "\n"
            "  Google's quickstart says GEMINI_API_KEY. Agno disagrees. Agno wins,\n"
            "  because Agno is what's making the call.\n"
            "\n"
            "  Fix: rename it in your .env file:\n"
            "      GOOGLE_API_KEY=<your key>\n"
        )

    raise MissingAPIKeyError(
        "GOOGLE_API_KEY is not set.\n"
        "\n"
        "  1. Get a free key at https://aistudio.google.com/apikey\n"
        "  2. cp .env.example .env\n"
        "  3. Paste your key after GOOGLE_API_KEY= in .env\n"
        "  4. Re-run `make preflight`\n"
    )


def get_model(
    model_id: str | None = None,
    *,
    temperature: float = 0.1,
    max_output_tokens: int = 2048,
    cache: bool | None = None,
) -> Gemini:
    """Build the Gemini model. This is the only place that does.

    Args:
        model_id: Override the model. Defaults to $COLLEGE_AGENT_MODEL, then
            DEFAULT_MODEL.
        temperature: Low by default. This agent makes routing decisions, and we
            want the same ticket to get the same answer twice — that's what
            makes module 3's evaluation meaningful at all.
        max_output_tokens: A ceiling, not a target. Free-tier limits count
            tokens-per-minute as well as requests, and a runaway response eats
            quota that the next student needs.
        cache: Cache responses to disk, keyed by request. Defaults to
            $COLLEGE_AGENT_CACHE, then on.
    """
    check_api_key()

    model_id = model_id or os.getenv("COLLEGE_AGENT_MODEL") or DEFAULT_MODEL
    use_cache = cache if cache is not None else _env_flag("COLLEGE_AGENT_CACHE", True)

    if use_cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    return Gemini(
        id=model_id,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        # --- Surviving the free tier -------------------------------------
        # An agent loop is 5-15 calls back to back. Against a free-tier
        # requests-per-minute ceiling that 429s almost immediately, so retry
        # with backoff isn't an optimisation here, it's the difference between
        # the code working and not.
        retries=5,
        delay_between_retries=2,
        exponential_backoff=True,
        # Same prompt -> same cached answer, no network, no quota. Delete
        # .cache/ (or `make clean`) when you want fresh responses.
        cache_response=use_cache,
        cache_dir=str(CACHE_DIR) if use_cache else None,
        cache_ttl=60 * 60 * 24,  # a day is plenty for a workshop
        # Don't let a slow call hang the whole lab.
        timeout=60,
    )


def describe_config() -> str:
    """One-line summary of the active setup, for banners and debugging."""
    model_id = os.getenv("COLLEGE_AGENT_MODEL") or DEFAULT_MODEL
    cache = "on" if _env_flag("COLLEGE_AGENT_CACHE", True) else "off"
    telemetry = "off" if not _env_flag("AGNO_TELEMETRY", False) else "on"
    return f"model={model_id}  cache={cache}  agno-telemetry={telemetry}"
