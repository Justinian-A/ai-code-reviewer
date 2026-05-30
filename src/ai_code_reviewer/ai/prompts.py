"""Prompt templates for AI code analysis."""

from __future__ import annotations

SYSTEM_PROMPT = """You are an expert code reviewer. You analyze code changes for:
- Security vulnerabilities
- Logic errors and bugs
- Performance issues
- Code quality and maintainability
- Architecture concerns

Always respond in the exact JSON format requested. Be precise and actionable."""


def build_analyze_code_prompt(code: str, context: str) -> list[dict[str, str]]:
    """Build messages for code analysis.

    Args:
        code: The source code to analyze.
        context: Additional context (e.g., file path, purpose).

    Returns:
        List of message dicts for the LLM.
    """
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Analyze the following code and identify risks.\n\n"
                f"## Context\n{context}\n\n"
                f"## Code\n```\n{code}\n```\n\n"
                "Respond with a JSON object:\n"
                '```json\n{"risks": [{"level": "critical|high|medium|low|info", '
                '"category": "security|logic|architecture", "message": "...", '
                '"suggestion": "..."}], "summary": "..."}\n```'
            ),
        },
    ]


def build_detect_issues_prompt(code: str) -> list[dict[str, str]]:
    """Build messages for issue detection.

    Args:
        code: The source code to scan.

    Returns:
        List of message dicts for the LLM.
    """
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Detect potential issues in this code.\n\n"
                f"```\n{code}\n```\n\n"
                "Respond with a JSON object:\n"
                '```json\n{"risks": [{"level": "critical|high|medium|low|info", '
                '"category": "security|logic|architecture", "message": "...", '
                '"suggestion": "..."}]}\n```'
            ),
        },
    ]


def build_generate_summary_prompt(changes_description: str) -> list[dict[str, str]]:
    """Build messages for generating a change summary.

    Args:
        changes_description: Human-readable description of file changes.

    Returns:
        List of message dicts for the LLM.
    """
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Generate a concise summary of the following code changes.\n\n"
                f"{changes_description}\n\n"
                "Respond with a JSON object:\n"
                '```json\n{"summary": "..."}\n```'
            ),
        },
    ]
