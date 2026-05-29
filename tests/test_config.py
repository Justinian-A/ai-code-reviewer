"""Tests for configuration management."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from ai_code_reviewer.config import (
    AIProvider,
    AnalysisConfig,
    AIConfig,
    Config,
    GitHubConfig,
    OutputConfig,
    OutputFormat,
    load_config,
)


class TestEnums:
    """Test enum types."""

    def test_ai_provider_values(self):
        assert AIProvider.DEEPSEEK.value == "deepseek"
        assert AIProvider.CLAUDE.value == "claude"
        assert AIProvider.OPENAI.value == "openai"

    def test_output_format_values(self):
        assert OutputFormat.TERMINAL.value == "terminal"
        assert OutputFormat.MARKDOWN.value == "markdown"
        assert OutputFormat.JSON.value == "json"


class TestGitHubConfig:
    """Test GitHub configuration."""

    def test_default_empty_token(self):
        config = GitHubConfig()
        assert config.token == ""

    def test_token_from_env(self, monkeypatch):
        monkeypatch.setenv("AI_CODE_REVIEWER_GITHUB_TOKEN", "test-token-123")
        config = GitHubConfig()
        assert config.token == "test-token-123"

    def test_explicit_token(self):
        config = GitHubConfig(token="explicit-token")
        assert config.token == "explicit-token"


class TestAIConfig:
    """Test AI configuration."""

    def test_default_values(self):
        config = AIConfig()
        assert config.provider == AIProvider.DEEPSEEK
        assert config.api_key == ""
        assert config.model == "deepseek-v4-flash"
        assert config.max_tokens == 4096

    def test_provider_from_env(self, monkeypatch):
        monkeypatch.setenv("AI_CODE_REVIEWER_AI_PROVIDER", "claude")
        config = AIConfig()
        assert config.provider == AIProvider.CLAUDE

    def test_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("AI_CODE_REVIEWER_AI_API_KEY", "sk-test-key")
        config = AIConfig()
        assert config.api_key == "sk-test-key"

    def test_model_from_env(self, monkeypatch):
        monkeypatch.setenv("AI_CODE_REVIEWER_AI_MODEL", "gpt-4")
        config = AIConfig()
        assert config.model == "gpt-4"

    def test_max_tokens_from_env(self, monkeypatch):
        monkeypatch.setenv("AI_CODE_REVIEWER_AI_MAX_TOKENS", "8192")
        config = AIConfig()
        assert config.max_tokens == 8192

    def test_invalid_provider_raises(self):
        with pytest.raises(ValueError, match="Unsupported AI provider"):
            AIConfig(provider="invalid")

    def test_max_tokens_must_be_positive(self):
        with pytest.raises(ValueError):
            AIConfig(max_tokens=0)

    def test_provider_case_insensitive(self):
        config = AIConfig(provider="CLAUDE")
        assert config.provider == AIProvider.CLAUDE


class TestAnalysisConfig:
    """Test analysis configuration."""

    def test_default_values(self):
        config = AnalysisConfig()
        assert config.enable_ast is True
        assert config.enable_ai is True

    def test_enable_ast_from_env(self, monkeypatch):
        monkeypatch.setenv("AI_CODE_REVIEWER_ENABLE_AST", "false")
        config = AnalysisConfig()
        assert config.enable_ast is False

    def test_enable_ai_from_env(self, monkeypatch):
        monkeypatch.setenv("AI_CODE_REVIEWER_ENABLE_AI", "0")
        config = AnalysisConfig()
        assert config.enable_ai is False

    def test_explicit_values(self):
        config = AnalysisConfig(enable_ast=False, enable_ai=False)
        assert config.enable_ast is False
        assert config.enable_ai is False


class TestOutputConfig:
    """Test output configuration."""

    def test_default_format(self):
        config = OutputConfig()
        assert config.format == OutputFormat.TERMINAL

    def test_format_from_env(self, monkeypatch):
        monkeypatch.setenv("AI_CODE_REVIEWER_OUTPUT_FORMAT", "json")
        config = OutputConfig()
        assert config.format == OutputFormat.JSON

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError, match="Unsupported output format"):
            OutputConfig(format="xml")

    def test_format_case_insensitive(self):
        config = OutputConfig(format="Markdown")
        assert config.format == OutputFormat.MARKDOWN


class TestConfig:
    """Test main Config class."""

    def test_default_config(self):
        config = Config()
        assert config.github.token == ""
        assert config.ai.provider == AIProvider.DEEPSEEK
        assert config.analysis.enable_ast is True
        assert config.output.format == OutputFormat.TERMINAL

    def test_from_yaml_with_valid_file(self, tmp_path):
        yaml_content = {
            "github": {"token": "yaml-token"},
            "ai": {"provider": "openai", "model": "gpt-4"},
            "analysis": {"enable_ast": False},
            "output": {"format": "json"},
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(yaml_content))

        config = Config.from_yaml(config_file)
        assert config.github.token == "yaml-token"
        assert config.ai.provider == AIProvider.OPENAI
        assert config.ai.model == "gpt-4"
        assert config.analysis.enable_ast is False
        assert config.output.format == OutputFormat.JSON

    def test_from_yaml_missing_file(self):
        config = Config.from_yaml("/nonexistent/path.yaml")
        # Should return defaults
        assert config.ai.provider == AIProvider.DEEPSEEK

    def test_from_yaml_partial_config(self, tmp_path):
        yaml_content = {"ai": {"model": "claude-3"}}
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(yaml_content))

        config = Config.from_yaml(config_file)
        assert config.ai.model == "claude-3"
        # Other values should be defaults
        assert config.ai.provider == AIProvider.DEEPSEEK
        assert config.analysis.enable_ast is True

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("AI_CODE_REVIEWER_GITHUB_TOKEN", "env-token")
        monkeypatch.setenv("AI_CODE_REVIEWER_AI_PROVIDER", "claude")

        config = Config.from_env()
        assert config.github.token == "env-token"
        assert config.ai.provider == AIProvider.CLAUDE

    def test_env_overrides_yaml(self, monkeypatch, tmp_path):
        yaml_content = {
            "github": {"token": "yaml-token"},
            "ai": {"provider": "openai"},
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(yaml_content))

        monkeypatch.setenv("AI_CODE_REVIEWER_GITHUB_TOKEN", "env-token")
        monkeypatch.setenv("AI_CODE_REVIEWER_AI_PROVIDER", "claude")

        config = Config.load(config_file)
        # Env should override yaml
        assert config.github.token == "env-token"
        assert config.ai.provider == AIProvider.CLAUDE

    def test_load_with_no_path(self):
        config = Config.load()
        assert isinstance(config, Config)

    def test_load_config_function(self):
        config = load_config()
        assert isinstance(config, Config)


class TestYAMLIntegration:
    """Test YAML file integration."""

    def test_default_yaml_exists(self):
        default_path = Path(__file__).parent.parent / "config" / "default.yaml"
        assert default_path.exists(), f"Default config not found at {default_path}"

    def test_default_yaml_is_valid(self):
        default_path = Path(__file__).parent.parent / "config" / "default.yaml"
        with open(default_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        assert "github" in data
        assert "ai" in data
        assert "analysis" in data
        assert "output" in data

    def test_default_yaml_loads_as_config(self):
        default_path = Path(__file__).parent.parent / "config" / "default.yaml"
        config = Config.from_yaml(default_path)
        assert config.ai.provider == AIProvider.DEEPSEEK
        assert config.analysis.enable_ast is True


class TestEnvIntEdgeCases:
    """Tests for _env_int edge cases."""

    def test_env_int_invalid_value_returns_default(self, monkeypatch):
        """When env var is set but not a valid int, return default."""
        from ai_code_reviewer.config import _env_int

        monkeypatch.setenv("AI_CODE_REVIEWER_TEST_INT", "not_a_number")
        result = _env_int("TEST_INT", 42)
        assert result == 42

    def test_env_int_empty_returns_default(self, monkeypatch):
        """When env var is empty, return default."""
        from ai_code_reviewer.config import _env_int

        monkeypatch.delenv("AI_CODE_REVIEWER_TEST_INT", raising=False)
        result = _env_int("TEST_INT", 99)
        assert result == 99


class TestValidatorPassthrough:
    """Tests that validators pass through enum instances."""

    def test_validate_provider_with_enum_instance(self):
        config = AIConfig(provider=AIProvider.CLAUDE)
        assert config.provider == AIProvider.CLAUDE

    def test_validate_format_with_enum_instance(self):
        config = OutputConfig(format=OutputFormat.JSON)
        assert config.format == OutputFormat.JSON


class TestApplyEnvOverrides:
    """Tests for Config._apply_env_overrides."""

    def test_env_overrides_ai_api_key(self, monkeypatch):
        monkeypatch.setenv("AI_CODE_REVIEWER_AI_API_KEY", "env-key")
        result = Config._apply_env_overrides({})
        assert result["ai"]["api_key"] == "env-key"

    def test_env_overrides_ai_model(self, monkeypatch):
        monkeypatch.setenv("AI_CODE_REVIEWER_AI_MODEL", "gpt-4o")
        result = Config._apply_env_overrides({})
        assert result["ai"]["model"] == "gpt-4o"

    def test_env_overrides_ai_max_tokens(self, monkeypatch):
        monkeypatch.setenv("AI_CODE_REVIEWER_AI_MAX_TOKENS", "16384")
        result = Config._apply_env_overrides({})
        assert result["ai"]["max_tokens"] == 16384

    def test_env_overrides_ai_max_tokens_invalid(self, monkeypatch):
        """Invalid max_tokens env var should be ignored."""
        monkeypatch.setenv("AI_CODE_REVIEWER_AI_MAX_TOKENS", "not_a_number")
        result = Config._apply_env_overrides({"ai": {"max_tokens": 4096}})
        assert result["ai"]["max_tokens"] == 4096

    def test_env_overrides_enable_ast(self, monkeypatch):
        monkeypatch.setenv("AI_CODE_REVIEWER_ENABLE_AST", "false")
        result = Config._apply_env_overrides({})
        assert result["analysis"]["enable_ast"] is False

    def test_env_overrides_enable_ai(self, monkeypatch):
        monkeypatch.setenv("AI_CODE_REVIEWER_ENABLE_AI", "true")
        result = Config._apply_env_overrides({})
        assert result["analysis"]["enable_ai"] is True

    def test_env_overrides_output_format(self, monkeypatch):
        monkeypatch.setenv("AI_CODE_REVIEWER_OUTPUT_FORMAT", "json")
        result = Config._apply_env_overrides({})
        assert result["output"]["format"] == "json"

    def test_env_overrides_preserves_existing_data(self, monkeypatch):
        """Existing data should be preserved when no env override."""
        monkeypatch.delenv("AI_CODE_REVIEWER_GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("AI_CODE_REVIEWER_AI_PROVIDER", raising=False)
        data = {"github": {"token": "yaml-token"}, "ai": {"provider": "openai"}}
        result = Config._apply_env_overrides(data)
        assert result["github"]["token"] == "yaml-token"
        assert result["ai"]["provider"] == "openai"

    def test_from_yaml_with_none_uses_default_path(self):
        """from_yaml(None) should try the default path."""
        # This exercises line 146 in config.py
        config = Config.from_yaml(None)
        assert isinstance(config, Config)


class TestLoadMethod:
    """Tests for Config.load with various scenarios."""

    def test_load_with_env_overrides_only(self, monkeypatch):
        """Config.load with no path but env vars set."""
        monkeypatch.setenv("AI_CODE_REVIEWER_GITHUB_TOKEN", "env-gh-token")
        monkeypatch.setenv("AI_CODE_REVIEWER_AI_PROVIDER", "claude")
        monkeypatch.setenv("AI_CODE_REVIEWER_AI_API_KEY", "env-ai-key")
        monkeypatch.setenv("AI_CODE_REVIEWER_AI_MODEL", "claude-3")
        monkeypatch.setenv("AI_CODE_REVIEWER_AI_MAX_TOKENS", "2048")
        monkeypatch.setenv("AI_CODE_REVIEWER_ENABLE_AST", "false")
        monkeypatch.setenv("AI_CODE_REVIEWER_ENABLE_AI", "false")
        monkeypatch.setenv("AI_CODE_REVIEWER_OUTPUT_FORMAT", "markdown")

        config = Config.load()
        assert config.github.token == "env-gh-token"
        assert config.ai.provider == AIProvider.CLAUDE
        assert config.ai.api_key == "env-ai-key"
        assert config.ai.model == "claude-3"
        assert config.ai.max_tokens == 2048
        assert config.analysis.enable_ast is False
        assert config.analysis.enable_ai is False
        assert config.output.format == OutputFormat.MARKDOWN

    def test_load_with_nonexistent_path(self):
        """Config.load with a path that doesn't exist."""
        config = Config.load("/nonexistent/path.yaml")
        assert isinstance(config, Config)
