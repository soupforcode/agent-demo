"""Model configuration — the *only* place in this repo that builds a model.

Why one file?
-------------
Agno quietly falls back to OpenAI in three places:

  1. `Agent(model=None)`                       -> OpenAIResponses
  2. `AccuracyEval` / `AgentAsJudgeEval` judge -> OpenAIChat
  3. `ChromaDb` / `LanceDb` embedder           -> OpenAIEmbedder

None of those are wrong of Agno — they're just a different default than ours.
The problem was never OpenAI; it's that a default you didn't choose fires
silently, usually halfway through a lab, and demands a key nobody has.

So: nothing else in this repo constructs a model. Everything imports
`get_model()` from here.

That decision is what makes this file's second job cheap. Supporting a whole
second provider is a branch in one function — every other module, including the
eval suite's judge, follows along without a single edit. That's the payoff for
centralising, and it's worth showing students.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from agno.models.base import Model
from agno.models.google import Gemini
from agno.models.openai import OpenAIChat
from dotenv import load_dotenv

# Load .env from the repo root, wherever we're invoked from.
REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")

# The Google SDK logs a scary-looking warning the first time anything reads
# `.text` on a response that contains tool calls:
#
#   "Warning: there are non-text parts in the response: ['function_call'] ..."
#
# Agno reads `.text`, so this fires on the first tool-calling turn of every run.
# It is harmless — Agno reads the function calls correctly from `.parts` — but
# it appears at exactly the moment a student's first agent works, which makes
# a success look like a failure. Silenced here rather than explained ten times.
logging.getLogger("google_genai.types").setLevel(logging.ERROR)


# --------------------------------------------------------------------------
# Providers
# --------------------------------------------------------------------------
# Pick with COLLEGE_AGENT_PROVIDER in .env. Defaults to google, because that's
# the one with a free tier and therefore the one the workshop is built around.
#
#   google  free tier, no card required   <- the workshop default
#   openai  PAID ONLY, no free tier       <- needs credits on your account
DEFAULT_PROVIDER = "google"

PROVIDERS: dict[str, dict] = {
    "google": {
        "env_var": "GOOGLE_API_KEY",
        "signup": "https://aistudio.google.com/apikey",
        # flash-lite is cheapest and fastest with the most generous free-tier
        # limits. That matters more than raw capability here: an agent makes
        # 5-15 model calls to answer *one* ticket, so the limit you hit first
        # is requests-per-minute, not intelligence.
        "default_model": "gemini-3.5-flash-lite",
        # Known-good alternatives, roughly by capability. If the default ever
        # 404s (providers retire model IDs), `make preflight` points you here.
        "fallbacks": (
            "gemini-3.5-flash-lite",
            "gemini-3.5-flash",
            "gemini-3.6-flash",
            "gemini-2.5-flash",
            "gemini-2.0-flash",
        ),
        "free_tier": True,
    },
    "openai": {
        "env_var": "OPENAI_API_KEY",
        "signup": "https://platform.openai.com/api-keys",
        "default_model": "gpt-5.4-mini",
        "fallbacks": ("gpt-5.4-mini", "gpt-5.4", "gpt-4o-mini", "gpt-4o"),
        "free_tier": False,
    },
}

# Kept for backwards compatibility — some docs and scripts import these.
DEFAULT_MODEL = PROVIDERS[DEFAULT_PROVIDER]["default_model"]
FALLBACK_MODELS = PROVIDERS[DEFAULT_PROVIDER]["fallbacks"]

# Where cached model responses live. Caching is on by default: re-running the
# same prompt while you're debugging then costs zero quota, which is the
# difference between finishing the lab and running out of requests.
CACHE_DIR = REPO_ROOT / ".cache" / "model"


class MissingAPIKeyError(RuntimeError):
    """Raised when the selected provider's key isn't usable, with a real fix."""


class UnknownProviderError(RuntimeError):
    """Raised when COLLEGE_AGENT_PROVIDER isn't one we support."""


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def get_provider() -> str:
    """Which provider is selected. Validated, so a typo fails clearly."""
    provider = (os.getenv("COLLEGE_AGENT_PROVIDER") or DEFAULT_PROVIDER).strip().lower()
    if provider not in PROVIDERS:
        raise UnknownProviderError(
            f"COLLEGE_AGENT_PROVIDER is set to {provider!r}, which isn't supported.\n"
            f"\n"
            f"  Use one of: {', '.join(sorted(PROVIDERS))}\n"
            f"  Or remove the line from .env to use the default ({DEFAULT_PROVIDER}).\n"
        )
    return provider


def get_model_id(provider: str | None = None) -> str:
    """The model that will actually be used, without building anything."""
    provider = provider or get_provider()
    return os.getenv("COLLEGE_AGENT_MODEL") or PROVIDERS[provider]["default_model"]


def api_key_present(provider: str | None = None) -> bool:
    """Is the selected provider's key set? Never raises — for health checks."""
    try:
        provider = provider or get_provider()
    except UnknownProviderError:
        return False
    return bool(os.getenv(PROVIDERS[provider]["env_var"], "").strip())


def check_api_key(provider: str | None = None) -> str:
    """Return the API key for the selected provider, or explain how to fix it.

    Agno's model classes *log* a missing key rather than raising, so without
    this you'd meet the problem several layers down as a confusing
    ModelProviderError. Better to fail here and say why.
    """
    provider = provider or get_provider()
    spec = PROVIDERS[provider]
    env_var = spec["env_var"]

    key = os.getenv(env_var, "").strip()
    if key:
        return key

    # The single most common setup mistake on Google. Their own quickstart
    # tells you to set GEMINI_API_KEY; Agno only ever reads GOOGLE_API_KEY.
    if provider == "google" and os.getenv("GEMINI_API_KEY", "").strip():
        raise MissingAPIKeyError(
            "You've set GEMINI_API_KEY, but Agno only reads GOOGLE_API_KEY.\n"
            "\n"
            "  Google's quickstart says GEMINI_API_KEY. Agno disagrees. Agno wins,\n"
            "  because Agno is what's making the call.\n"
            "\n"
            "  Fix: rename it in your .env file:\n"
            "      GOOGLE_API_KEY=<your key>\n"
        )

    # Point at the *other* provider if its key happens to be the one that's set.
    other = "openai" if provider == "google" else "google"
    other_var = PROVIDERS[other]["env_var"]
    hint = ""
    if os.getenv(other_var, "").strip():
        hint = (
            f"\n  You do have {other_var} set. To use that provider instead, put\n"
            f"  this in .env:\n"
            f"      COLLEGE_AGENT_PROVIDER={other}\n"
        )

    paid = (
        ""
        if spec["free_tier"]
        else "  Note: this provider has no free tier — you need paid credits.\n"
    )

    raise MissingAPIKeyError(
        f"{env_var} is not set (provider: {provider}).\n"
        f"\n"
        f"  1. Get a key at {spec['signup']}\n"
        f"{paid}"
        f"  2. cp .env.example .env\n"
        f"  3. Paste your key after {env_var}= in .env\n"
        f"  4. Re-run `make preflight`\n"
        f"{hint}"
    )


def get_model(
    model_id: str | None = None,
    *,
    temperature: float = 0.1,
    max_output_tokens: int = 2048,
    cache: bool | None = None,
    provider: str | None = None,
) -> Model:
    """Build the model. This is the only place that does.

    Args:
        model_id: Override the model. Defaults to $COLLEGE_AGENT_MODEL, then the
            selected provider's default.
        temperature: Low by default. This agent makes routing decisions, and we
            want the same ticket to get the same answer twice — that's what
            makes module 3's evaluation meaningful at all.
        max_output_tokens: A ceiling, not a target. Rate limits count tokens per
            minute as well as requests, and a runaway response eats quota the
            next student needs. Translated per provider below.
        cache: Cache responses to disk, keyed by request. Defaults to
            $COLLEGE_AGENT_CACHE, then on.
        provider: Override the provider. Defaults to $COLLEGE_AGENT_PROVIDER.
    """
    provider = provider or get_provider()
    api_key = check_api_key(provider)

    model_id = model_id or get_model_id(provider)
    use_cache = cache if cache is not None else _env_flag("COLLEGE_AGENT_CACHE", True)

    if use_cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Everything here lives on Agno's shared `Model` base class, so it applies
    # identically whichever provider you picked.
    shared = {
        "id": model_id,
        "api_key": api_key,
        "temperature": temperature,
        # --- Surviving a rate limit ---------------------------------------
        # An agent loop is 5-15 calls back to back. Against a free-tier
        # requests-per-minute ceiling that 429s almost immediately, so retry
        # with backoff isn't an optimisation, it's the difference between the
        # code working and not.
        "retries": 5,
        "delay_between_retries": 2,
        "exponential_backoff": True,
        # Same prompt -> same cached answer, no network, no quota. Delete
        # .cache/ (or `make clean`) when you want fresh responses.
        "cache_response": use_cache,
        "cache_dir": str(CACHE_DIR) if use_cache else None,
        "cache_ttl": 60 * 60 * 24,  # a day is plenty for a workshop
        # Don't let a slow call hang the whole lab.
        "timeout": 60,
    }

    # The one place the two providers genuinely disagree: Gemini caps output
    # with `max_output_tokens`, OpenAI with `max_completion_tokens`. Same idea,
    # different spelling — and passing the wrong one is a TypeError, not a
    # silent no-op, which is the good kind of incompatibility.
    if provider == "google":
        return Gemini(max_output_tokens=max_output_tokens, **shared)
    return OpenAIChat(max_completion_tokens=max_output_tokens, **shared)


def describe_config() -> str:
    """One-line summary of the active setup, for banners and debugging."""
    try:
        provider = get_provider()
    except UnknownProviderError:
        return "provider=INVALID (check COLLEGE_AGENT_PROVIDER in .env)"

    cache = "on" if _env_flag("COLLEGE_AGENT_CACHE", True) else "off"
    telemetry = "off" if not _env_flag("AGNO_TELEMETRY", False) else "on"
    return (
        f"provider={provider}  model={get_model_id(provider)}  "
        f"cache={cache}  agno-telemetry={telemetry}"
    )
