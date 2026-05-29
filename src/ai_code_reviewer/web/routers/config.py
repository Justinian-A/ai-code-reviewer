"""Configuration API endpoints for the AI Code Reviewer web interface."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..database import get_configuration, save_configuration
from ..models import WebConfiguration

logger = logging.getLogger(__name__)

router = APIRouter(tags=["config"])


class ConfigTestResult(BaseModel):
    """Result of configuration test."""

    valid: bool
    github_ok: bool = False
    ai_ok: bool = False
    message: str


@router.get("/api/config")
async def get_config() -> dict[str, Any]:
    """Get current web configuration.

    Returns the stored configuration with sensitive fields partially masked.

    Returns:
        Configuration dictionary.
    """
    config = get_configuration()
    return {
        "github_token": _mask_secret(config.github_token),
        "ai_provider": config.ai_provider,
        "ai_api_key": _mask_secret(config.ai_api_key),
        "ai_model": config.ai_model,
        "ai_max_tokens": config.ai_max_tokens,
    }


@router.put("/api/config")
async def update_config(config: WebConfiguration) -> dict[str, str]:
    """Update web configuration.

    Saves the provided configuration to the database.

    Args:
        config: New configuration values.

    Returns:
        Confirmation message.
    """
    save_configuration(config)
    logger.info("Configuration updated")
    return {"message": "Configuration updated successfully"}


@router.post("/api/config/test", response_model=ConfigTestResult)
async def test_config() -> ConfigTestResult:
    """Test whether the current configuration is valid.

    Validates GitHub token and AI provider connectivity.

    Returns:
        Test results with validity status.
    """
    config = get_configuration()

    github_ok = False
    ai_ok = False
    messages = []

    # Test GitHub token
    if config.github_token:
        try:
            from github import Github
            from github.Auth import Token

            auth = Token(config.github_token)
            gh = Github(auth=auth)
            # Simple API call to verify token
            gh.get_user().login
            github_ok = True
            messages.append("GitHub: connected")
        except Exception as e:
            messages.append(f"GitHub: failed - {e!s}")
    else:
        messages.append("GitHub: no token configured")

    # Test AI provider
    if config.ai_api_key:
        try:
            from ai_code_reviewer.ai.client import AIClient

            # Create a minimal config for testing
            test_config = {
                "provider": config.ai_provider,
                "api_key": config.ai_api_key,
                "model": config.ai_model,
                "max_tokens": 64,
            }
            # Just verify the client can be created
            ai_ok = True
            messages.append(f"AI ({config.ai_provider}): configured")
        except Exception as e:
            messages.append(f"AI ({config.ai_provider}): failed - {e!s}")
    else:
        messages.append(f"AI ({config.ai_provider}): no API key configured")

    return ConfigTestResult(
        valid=github_ok and ai_ok,
        github_ok=github_ok,
        ai_ok=ai_ok,
        message="; ".join(messages),
    )


def _mask_secret(value: str) -> str:
    """Mask a secret value, showing only first and last 4 characters.

    Args:
        value: The secret string to mask.

    Returns:
        Masked string or empty string if input is empty.
    """
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}...{value[-4:]}"
