"""Pytest configuration and fixtures."""

import pytest


@pytest.fixture
def sample_config() -> dict:
    """Sample configuration for testing."""
    return {
        "github": {"token": "test-token"},
        "ai": {"model": "gpt-4", "provider": "openai"},
    }
