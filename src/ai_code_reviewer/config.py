"""Configuration management for AI Code Reviewer."""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field, field_validator


# Default config file path
DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "default.yaml"
ENV_PREFIX = "AI_CODE_REVIEWER_"


class AIProvider(str, Enum):
    """Supported AI providers."""
    DEEPSEEK = "deepseek"
    CLAUDE = "claude"
    OPENAI = "openai"


class OutputFormat(str, Enum):
    """Supported output formats."""
    TERMINAL = "terminal"
    MARKDOWN = "markdown"
    JSON = "json"


def _env(key: str, default: str = "") -> str:
    """Get environment variable with prefix."""
    return os.getenv(f"{ENV_PREFIX}{key}", default)


def _env_bool(key: str, default: bool = False) -> bool:
    """Get boolean environment variable with prefix."""
    val = os.getenv(f"{ENV_PREFIX}{key}", "").lower()
    if not val:
        return default
    return val in ("true", "1", "yes")


def _env_int(key: str, default: int = 0) -> int:
    """Get integer environment variable with prefix."""
    val = os.getenv(f"{ENV_PREFIX}{key}", "")
    if not val:
        return default
    try:
        return int(val)
    except ValueError:
        return default


class GitHubConfig(BaseModel):
    """GitHub configuration."""
    token: str = Field(
        default_factory=lambda: _env("GITHUB_TOKEN"),
        description="GitHub Personal Access Token"
    )


class AIConfig(BaseModel):
    """AI provider configuration."""
    provider: AIProvider = Field(
        default_factory=lambda: AIProvider(_env("AI_PROVIDER", "deepseek")),
        description="AI provider (deepseek/claude/openai)"
    )
    api_key: str = Field(
        default_factory=lambda: _env("AI_API_KEY"),
        description="AI provider API key"
    )
    model: str = Field(
        default_factory=lambda: _env("AI_MODEL", "deepseek-v4-flash"),
        description="AI model name"
    )
    max_tokens: int = Field(
        default_factory=lambda: _env_int("AI_MAX_TOKENS", 4096),
        description="Maximum tokens for AI response",
        gt=0
    )

    @field_validator("provider", mode="before")
    @classmethod
    def validate_provider(cls, v: str | AIProvider) -> AIProvider:
        """Validate and convert provider string."""
        if isinstance(v, AIProvider):
            return v
        try:
            return AIProvider(v.lower())
        except ValueError:
            raise ValueError(f"Unsupported AI provider: {v}. Use: {[p.value for p in AIProvider]}")


class AnalysisConfig(BaseModel):
    """Analysis configuration."""
    enable_ast: bool = Field(
        default_factory=lambda: _env_bool("ENABLE_AST", True),
        description="Enable AST-based analysis"
    )
    enable_ai: bool = Field(
        default_factory=lambda: _env_bool("ENABLE_AI", True),
        description="Enable AI-based analysis"
    )


class OutputConfig(BaseModel):
    """Output configuration."""
    format: OutputFormat = Field(
        default_factory=lambda: OutputFormat(_env("OUTPUT_FORMAT", "terminal")),
        description="Output format (terminal/markdown/json)"
    )

    @field_validator("format", mode="before")
    @classmethod
    def validate_format(cls, v: str | OutputFormat) -> OutputFormat:
        """Validate and convert format string."""
        if isinstance(v, OutputFormat):
            return v
        try:
            return OutputFormat(v.lower())
        except ValueError:
            raise ValueError(f"Unsupported output format: {v}. Use: {[f.value for f in OutputFormat]}")


class Config(BaseModel):
    """Main configuration for AI Code Reviewer."""
    github: GitHubConfig = Field(default_factory=GitHubConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)

    @classmethod
    def from_yaml(cls, path: Path | str | None = None) -> Config:
        """Load configuration from YAML file.
        
        Args:
            path: Path to YAML config file. Uses default if None.
            
        Returns:
            Config instance with values from YAML.
        """
        if path is None:
            path = DEFAULT_CONFIG_PATH
        
        path = Path(path)
        if not path.exists():
            return cls()
        
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        
        return cls(**data)

    @classmethod
    def from_env(cls) -> Config:
        """Load configuration from environment variables only.
        
        Returns:
            Config instance with values from environment.
        """
        return cls()

    @classmethod
    def load(cls, config_path: Path | str | None = None) -> Config:
        """Load configuration with precedence: env vars > yaml > defaults.
        
        Environment variables always override YAML values.
        
        Args:
            config_path: Optional path to YAML config file.
            
        Returns:
            Fully resolved Config instance.
        """
        # Load YAML first
        yaml_data = {}
        if config_path is None:
            config_path = DEFAULT_CONFIG_PATH

        config_path = Path(config_path)
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                yaml_data = yaml.safe_load(f) or {}
        
        # Apply env overrides to yaml data
        merged = cls._apply_env_overrides(yaml_data)
        
        return cls(**merged)

    @classmethod
    def _apply_env_overrides(cls, data: dict) -> dict:
        """Apply environment variable overrides to config data.
        
        Args:
            data: Config data from YAML.
            
        Returns:
            Merged data with env overrides applied.
        """
        result = dict(data)
        
        # GitHub overrides
        github = result.setdefault("github", {})
        env_token = os.getenv(f"{ENV_PREFIX}GITHUB_TOKEN")
        if env_token is not None:
            github["token"] = env_token
        
        # AI overrides
        ai = result.setdefault("ai", {})
        env_provider = os.getenv(f"{ENV_PREFIX}AI_PROVIDER")
        if env_provider is not None:
            ai["provider"] = env_provider
        env_api_key = os.getenv(f"{ENV_PREFIX}AI_API_KEY")
        if env_api_key is not None:
            ai["api_key"] = env_api_key
        env_model = os.getenv(f"{ENV_PREFIX}AI_MODEL")
        if env_model is not None:
            ai["model"] = env_model
        env_max_tokens = os.getenv(f"{ENV_PREFIX}AI_MAX_TOKENS")
        if env_max_tokens is not None:
            try:
                ai["max_tokens"] = int(env_max_tokens)
            except ValueError:
                pass
        
        # Analysis overrides
        analysis = result.setdefault("analysis", {})
        env_enable_ast = os.getenv(f"{ENV_PREFIX}ENABLE_AST")
        if env_enable_ast is not None:
            analysis["enable_ast"] = env_enable_ast.lower() in ("true", "1", "yes")
        env_enable_ai = os.getenv(f"{ENV_PREFIX}ENABLE_AI")
        if env_enable_ai is not None:
            analysis["enable_ai"] = env_enable_ai.lower() in ("true", "1", "yes")
        
        # Output overrides
        output = result.setdefault("output", {})
        env_format = os.getenv(f"{ENV_PREFIX}OUTPUT_FORMAT")
        if env_format is not None:
            output["format"] = env_format
        
        return result


def load_config(config_path: Path | str | None = None) -> Config:
    """Convenience function to load configuration.
    
    Args:
        config_path: Optional path to YAML config file.
        
    Returns:
        Config instance.
    """
    return Config.load(config_path)
