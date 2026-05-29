"""CLI entry point for AI Code Reviewer.

Uses Click framework to provide the ``analyze`` and ``config`` commands.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Optional

import click

from ai_code_reviewer import __version__
from ai_code_reviewer.analyzer.hybrid_analyzer import HybridAnalyzer
from ai_code_reviewer.config import Config, load_config
from ai_code_reviewer.github.client import (
    GitHubClient,
    GitHubClientError,
    GitHubNotFoundError,
)
from ai_code_reviewer.github.review_publisher import ReviewPublisher, ReviewPublisherError
from ai_code_reviewer.report.markdown import MarkdownReporter
from ai_code_reviewer.report.terminal import TerminalReporter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PR_URL_PATTERN = re.compile(
    r"https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/pull/(?P<number>\d+)"
)


def parse_pr_url(url: str) -> tuple[str, str, int]:
    """Extract owner, repo, and PR number from a GitHub pull request URL.

    Args:
        url: GitHub PR URL in the form
             ``https://github.com/{owner}/{repo}/pull/{number}``.

    Returns:
        Tuple of ``(owner, repo, pr_number)``.

    Raises:
        click.BadParameter: If the URL does not match the expected format.
    """
    match = _PR_URL_PATTERN.match(url.strip())
    if not match:
        raise click.BadParameter(
            f"Invalid PR URL: {url}. "
            "Expected format: https://github.com/owner/repo/pull/123"
        )
    return match.group("owner"), match.group("repo"), int(match.group("number"))


# ---------------------------------------------------------------------------
# CLI root
# ---------------------------------------------------------------------------


@click.group()
@click.version_option(version=__version__, prog_name="ai-code-reviewer")
def cli() -> None:
    """AI Code Reviewer - Analyze GitHub PRs with AI."""


# ---------------------------------------------------------------------------
# analyze command
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("pr_url")
@click.option(
    "--output-format",
    "-f",
    type=click.Choice(["terminal", "markdown", "json"]),
    default="terminal",
    show_default=True,
    help="Output format for the review.",
)
@click.option(
    "--output-file",
    "-o",
    type=click.Path(),
    default=None,
    help="Write output to a file instead of stdout.",
)
@click.option(
    "--publish",
    "-p",
    is_flag=True,
    default=False,
    help="Publish review to GitHub as a PR review comment.",
)
@click.option(
    "--preview",
    is_flag=True,
    default=False,
    help="Preview the review without publishing.",
)
@click.option(
    "--language",
    "-l",
    type=click.Choice(["en", "zh"]),
    default="en",
    show_default=True,
    help="Language for the report.",
)
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=False),
    default=None,
    help="Path to a YAML configuration file.",
)
@click.pass_context
def analyze(
    ctx: click.Context,
    pr_url: str,
    output_format: str,
    output_file: Optional[str],
    publish: bool,
    preview: bool,
    language: str,
    config_path: Optional[str],
) -> None:
    """Analyze a GitHub pull request.

    PR_URL is the full URL of the pull request, e.g.
    https://github.com/owner/repo/pull/123
    """
    # 1. Parse PR URL
    owner, repo, pr_number = parse_pr_url(pr_url)

    # 2. Load configuration
    config = _load_config(config_path)

    # 3. Validate required tokens
    _validate_config(config)

    # 4. Initialize GitHub client and fetch PR data
    try:
        gh_client = GitHubClient(token=config.github.token)
    except ValueError as exc:
        click.secho(f"Error: {exc}", fg="red", err=True)
        ctx.exit(1)
        return

    try:
        click.secho(
            f"Fetching PR #{pr_number} from {owner}/{repo}...",
            fg="cyan",
            err=True,
        )
        pr = gh_client.get_pull_request(owner, repo, pr_number)
        files = gh_client.get_pr_files(owner, repo, pr_number)
    except GitHubNotFoundError as exc:
        click.secho(f"Not found: {exc}", fg="red", err=True)
        ctx.exit(1)
        return
    except GitHubClientError as exc:
        click.secho(f"GitHub error: {exc}", fg="red", err=True)
        ctx.exit(1)
        return
    finally:
        gh_client.close()

    # 5. Run analysis
    click.secho("Running analysis...", fg="cyan", err=True)
    analyzer = HybridAnalyzer(config)
    result = analyzer.analyze_pr(pr, files)

    # 6. Publish or preview if requested
    if publish or preview:
        pub_client = GitHubClient(token=config.github.token)
        publisher = ReviewPublisher(pub_client)
        try:
            if preview:
                preview_text = publisher.preview_review(result)
                click.echo(preview_text)
            if publish:
                click.secho("Publishing review to GitHub...", fg="cyan", err=True)
                review_data = publisher.publish_review(owner, repo, pr_number, result)
                click.secho(
                    f"Review published: {review_data.get('html_url', 'N/A')}",
                    fg="green",
                    err=True,
                )
        except ReviewPublisherError as exc:
            click.secho(f"Publish error: {exc}", fg="red", err=True)
            ctx.exit(1)
        except GitHubClientError as exc:
            click.secho(f"GitHub error: {exc}", fg="red", err=True)
            ctx.exit(1)
        finally:
            pub_client.close()

    # 7. Output results
    _output_result(result, output_format, output_file, language)


# ---------------------------------------------------------------------------
# config command group
# ---------------------------------------------------------------------------


@cli.group()
def config() -> None:
    """Manage configuration."""


@config.command("init")
def config_init() -> None:
    """Initialize a configuration file with default values."""
    config_dir = Path("config")
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "default.yaml"

    if config_file.exists():
        if not click.confirm(f"{config_file} already exists. Overwrite?"):
            click.echo("Aborted.")
            return

    default_yaml = (
        "# AI Code Reviewer Configuration\n"
        "\n"
        "github:\n"
        '  token: ""  # Or set AI_CODE_REVIEWER_GITHUB_TOKEN env var\n'
        "\n"
        "ai:\n"
        '  provider: "deepseek"  # deepseek / claude / openai\n'
        '  api_key: ""           # Or set AI_CODE_REVIEWER_AI_API_KEY env var\n'
        '  model: "deepseek-v4-flash"\n'
        "  max_tokens: 4096\n"
        "\n"
        "analysis:\n"
        "  enable_ast: true\n"
        "  enable_ai: true\n"
        "\n"
        "output:\n"
        '  format: "terminal"\n'
    )
    config_file.write_text(default_yaml, encoding="utf-8")
    click.secho(f"Configuration written to {config_file}", fg="green")


@config.command("show")
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=False),
    default=None,
    help="Path to a YAML configuration file.",
)
def config_show(config_path: Optional[str]) -> None:
    """Show the current configuration."""
    cfg = _load_config(config_path)
    # Serialize to a readable dict (mask secrets)
    data = {
        "github": {
            "token": _mask(cfg.github.token),
        },
        "ai": {
            "provider": cfg.ai.provider.value,
            "api_key": _mask(cfg.ai.api_key),
            "model": cfg.ai.model,
            "max_tokens": cfg.ai.max_tokens,
        },
        "analysis": {
            "enable_ast": cfg.analysis.enable_ast,
            "enable_ai": cfg.analysis.enable_ai,
        },
        "output": {
            "format": cfg.output.format.value,
        },
    }
    click.echo(json.dumps(data, indent=2))


@config.command("set")
@click.argument("key")
@click.argument("value", default="")
def config_set(key: str, value: str) -> None:
    """Set a configuration value.

    KEY uses dot notation, e.g. ``ai.provider``, ``github.token``.
    """
    config_dir = Path("config")
    config_file = config_dir / "default.yaml"

    import yaml

    if config_file.exists():
        with open(config_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    parts = key.split(".")
    if len(parts) != 2:
        click.secho(
            "Key must use dot notation with two parts, e.g. 'ai.provider'",
            fg="red",
            err=True,
        )
        raise SystemExit(1)

    section, field = parts
    section_dict = data.setdefault(section, {})

    # Attempt to cast booleans and integers
    cast_value: object = value
    if value.lower() in ("true", "false"):
        cast_value = value.lower() == "true"
    else:
        try:
            cast_value = int(value)
        except ValueError:
            pass

    # Validate the value before writing
    try:
        test_data = {section: {field: cast_value}}
        test_merged = Config._apply_env_overrides(test_data)
        Config(**test_merged)
    except Exception as e:
        click.secho(f"Invalid value: {e}", fg="red", err=True)
        raise SystemExit(1)

    section_dict[field] = cast_value

    config_dir.mkdir(parents=True, exist_ok=True)
    with open(config_file, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

    click.secho(f"Set {key} = {cast_value}", fg="green")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_config(config_path: Optional[str] = None) -> Config:
    """Load configuration from the given path or defaults."""
    return load_config(config_path)


def _validate_config(config: Config) -> None:
    """Validate that required configuration values are present.

    Raises ``SystemExit`` via Click if critical values are missing.
    """
    missing: list[str] = []
    if not config.github.token:
        missing.append(
            "GitHub token (set AI_CODE_REVIEWER_GITHUB_TOKEN or github.token in config)"
        )
    if not config.ai.api_key:
        missing.append(
            "AI API key (set AI_CODE_REVIEWER_AI_API_KEY or ai.api_key in config)"
        )
    if missing:
        for msg in missing:
            click.secho(f"Missing: {msg}", fg="red", err=True)
        raise SystemExit(1)


def _output_result(
    result: object,
    output_format: str,
    output_file: Optional[str],
    language: str,
) -> None:
    """Render and emit the analysis result."""
    from ai_code_reviewer.models import AnalysisResult

    assert isinstance(result, AnalysisResult), "Expected AnalysisResult"

    if output_format == "terminal":
        reporter = TerminalReporter()
        reporter.print_summary(result.pr, result.summary or "")
        reporter.print_risks(result.risks)
        reporter.print_suggestions(result.suggestions)
        if result.cost:
            reporter.print_cost_report(result.cost)
        content: Optional[str] = None  # printed directly to console

    elif output_format == "markdown":
        md_reporter = MarkdownReporter(language=language)
        content = md_reporter.generate_report(result)
        if output_file:
            md_reporter.save_report(result, output_file)
            click.secho(f"Report saved to {output_file}", fg="green")
            return
        click.echo(content)

    elif output_format == "json":
        content = result.model_dump_json(indent=2)
        if output_file:
            Path(output_file).write_text(content, encoding="utf-8")
            click.secho(f"Report saved to {output_file}", fg="green")
            return
        click.echo(content)

    else:
        click.secho(f"Unknown format: {output_format}", fg="red", err=True)
        raise SystemExit(1)


def _mask(value: str) -> str:
    """Mask a secret string, showing only the last 4 characters."""
    if not value:
        return "(not set)"
    if len(value) <= 4:
        return "****"
    return "*" * (len(value) - 4) + value[-4:]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli()
