"""Tests for per-stage model config and API key settings."""


class TestStageConfig:
    def test_fallback_to_global(self):
        """When no per-stage override, returns global config."""
        from backend.config import Settings

        s = Settings(
            model_provider="google",
            google_api_key="gkey",
            google_model="gemini-2.5-flash",
        )
        provider, model, key = s.stage_config("refine")
        assert provider == "google"
        assert model == "gemini-2.5-flash"
        assert key == "gkey"

    def test_per_stage_provider_override(self):
        """Per-stage provider overrides global."""
        from backend.config import Settings

        s = Settings(
            model_provider="google",
            google_api_key="gkey",
            google_model="gemini-2.5-flash",
            anthropic_api_key="akey",
            anthropic_model="claude-sonnet-4-5-20250514",
            refine_provider="anthropic",
        )
        provider, model, key = s.stage_config("refine")
        assert provider == "anthropic"
        assert model == "claude-sonnet-4-5-20250514"
        assert key == "akey"

    def test_per_stage_model_override(self):
        """Per-stage model overrides provider default model."""
        from backend.config import Settings

        s = Settings(
            model_provider="google",
            google_api_key="gkey",
            google_model="gemini-2.5-flash",
            research_provider="google",
            research_model="gemini-2.5-pro",
        )
        provider, model, key = s.stage_config("research")
        assert provider == "google"
        assert model == "gemini-2.5-pro"
        assert key == "gkey"

    def test_mixed_stage_configs(self):
        """Different stages can use different providers."""
        from backend.config import Settings

        s = Settings(
            model_provider="google",
            google_api_key="gkey",
            google_model="gemini-2.5-flash",
            anthropic_api_key="akey",
            openai_api_key="okey",
            refine_provider="anthropic",
            refine_model="claude-opus-4-6",
            write_provider="openai",
            write_model="gpt-4o",
        )
        rp, rm, rk = s.stage_config("refine")
        assert rp == "anthropic" and rm == "claude-opus-4-6" and rk == "akey"

        wp, wm, wk = s.stage_config("write")
        assert wp == "openai" and wm == "gpt-4o" and wk == "okey"

        # Research falls back to global
        resp, resm, resk = s.stage_config("research")
        assert resp == "google" and resm == "gemini-2.5-flash" and resk == "gkey"


class TestAccessTokenSetting:
    def test_access_token_default_empty(self):
        from backend.config import Settings

        s = Settings()
        assert s.access_token == ""
