"""Tests for the one file that decides which model everything else gets.

`config.py` is small and boring, which is exactly why it's worth testing: every
other module depends on it, and its failure mode is a confusing error several
layers away from the actual cause.

The error messages get asserted too, not just the exceptions. A wrong key with a
helpful message costs a student thirty seconds; the same wrong key with
`ModelProviderError` costs them the lab.
"""

from __future__ import annotations

import importlib

import pytest

import college_agent.config as config_module

PROVIDER_ENV = ("COLLEGE_AGENT_PROVIDER", "GOOGLE_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY")


@pytest.fixture
def config(monkeypatch):
    """A freshly reloaded config with every provider variable cleared."""

    def _load(**env):
        for name in PROVIDER_ENV:
            monkeypatch.delenv(name, raising=False)
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        return importlib.reload(config_module)

    yield _load
    for name in PROVIDER_ENV:
        monkeypatch.delenv(name, raising=False)
    importlib.reload(config_module)


class TestProviderSelection:
    def test_defaults_to_google(self, config):
        """Google is the default because it's the one with a free tier."""
        assert config().get_provider() == "google"

    def test_honours_the_env_var(self, config):
        assert config(COLLEGE_AGENT_PROVIDER="openai").get_provider() == "openai"

    def test_is_case_and_space_insensitive(self, config):
        assert config(COLLEGE_AGENT_PROVIDER="  OpenAI  ").get_provider() == "openai"

    def test_an_unknown_provider_fails_clearly(self, config):
        cfg = config(COLLEGE_AGENT_PROVIDER="antropic")  # a plausible typo
        with pytest.raises(cfg.UnknownProviderError) as exc:
            cfg.get_provider()
        assert "google" in str(exc.value) and "openai" in str(exc.value)


class TestModelSelection:
    def test_each_provider_has_its_own_default(self, config):
        assert config().get_model_id() == "gemini-3.5-flash-lite"
        assert config(COLLEGE_AGENT_PROVIDER="openai").get_model_id() == "gpt-5.4-mini"

    def test_the_model_override_wins(self, config):
        cfg = config(COLLEGE_AGENT_MODEL="gemini-3.5-flash")
        assert cfg.get_model_id() == "gemini-3.5-flash"

    def test_no_alias_models_in_the_fallback_lists(self, config):
        """`-latest` aliases move under you with two weeks' notice."""
        cfg = config()
        for spec in cfg.PROVIDERS.values():
            for model in spec["fallbacks"]:
                assert "latest" not in model, f"{model} is a moving alias — pin a real id"


class TestKeyChecking:
    def test_returns_the_key_when_set(self, config):
        assert config(GOOGLE_API_KEY="abc123").check_api_key() == "abc123"

    def test_missing_key_names_the_right_variable(self, config):
        cfg = config(COLLEGE_AGENT_PROVIDER="openai")
        with pytest.raises(cfg.MissingAPIKeyError) as exc:
            cfg.check_api_key()
        assert "OPENAI_API_KEY" in str(exc.value)
        assert "GOOGLE_API_KEY" not in str(exc.value).split("You do have")[0]

    def test_catches_the_gemini_api_key_mixup(self, config):
        """Google's own quickstart tells you the wrong variable name."""
        cfg = config(GEMINI_API_KEY="abc123")
        with pytest.raises(cfg.MissingAPIKeyError) as exc:
            cfg.check_api_key()
        assert "GEMINI_API_KEY" in str(exc.value)
        assert "GOOGLE_API_KEY" in str(exc.value)

    def test_points_at_the_other_provider_when_that_key_exists(self, config):
        """If you have an OpenAI key and picked google, say so."""
        cfg = config(COLLEGE_AGENT_PROVIDER="google", OPENAI_API_KEY="sk-abc")
        with pytest.raises(cfg.MissingAPIKeyError) as exc:
            cfg.check_api_key()
        assert "COLLEGE_AGENT_PROVIDER=openai" in str(exc.value)

    def test_warns_that_openai_costs_money(self, config):
        cfg = config(COLLEGE_AGENT_PROVIDER="openai")
        with pytest.raises(cfg.MissingAPIKeyError) as exc:
            cfg.check_api_key()
        assert "free tier" in str(exc.value).lower()

    def test_api_key_present_never_raises(self, config):
        """Health checks call this — it must answer even when misconfigured."""
        cfg = config(COLLEGE_AGENT_PROVIDER="nonsense")
        assert cfg.api_key_present() is False


class TestModelConstruction:
    def test_builds_the_right_class_per_provider(self, config):
        cfg = config(GOOGLE_API_KEY="k")
        assert type(cfg.get_model()).__name__ == "Gemini"

        cfg = config(COLLEGE_AGENT_PROVIDER="openai", OPENAI_API_KEY="k")
        assert type(cfg.get_model()).__name__ == "OpenAIChat"

    def test_token_cap_is_translated_per_provider(self, config):
        """The one place the two SDKs genuinely disagree."""
        cfg = config(GOOGLE_API_KEY="k")
        assert cfg.get_model(max_output_tokens=999).max_output_tokens == 999

        cfg = config(COLLEGE_AGENT_PROVIDER="openai", OPENAI_API_KEY="k")
        assert cfg.get_model(max_output_tokens=999).max_completion_tokens == 999

    @pytest.mark.parametrize(
        "provider,key", [("google", "GOOGLE_API_KEY"), ("openai", "OPENAI_API_KEY")]
    )
    def test_rate_limit_survival_is_on_for_both(self, config, provider, key):
        """Retry and backoff aren't optimisations here — a tool loop 429s without them."""
        cfg = config(COLLEGE_AGENT_PROVIDER=provider, **{key: "k"})
        model = cfg.get_model()
        assert model.retries >= 3
        assert model.exponential_backoff is True
        assert model.timeout is not None

    def test_caching_can_be_turned_off(self, config):
        cfg = config(GOOGLE_API_KEY="k", COLLEGE_AGENT_CACHE="false")
        assert cfg.get_model().cache_response is False

    def test_caching_is_on_by_default(self, config):
        """Re-running the same prompt while debugging should cost zero quota."""
        assert config(GOOGLE_API_KEY="k").get_model().cache_response is True


class TestDescribeConfig:
    def test_names_the_provider_and_model(self, config):
        summary = config(GOOGLE_API_KEY="k").describe_config()
        assert "provider=google" in summary
        assert "gemini-3.5-flash-lite" in summary

    def test_survives_a_bad_provider(self, config):
        """It's used in banners and logs — it must never be the thing that crashes."""
        assert "INVALID" in config(COLLEGE_AGENT_PROVIDER="nope").describe_config()
