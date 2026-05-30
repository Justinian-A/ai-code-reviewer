"""Terminal output formatter using Rich library."""

from __future__ import annotations

from typing import List

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from ai_code_reviewer.models import (
    CostReport,
    PullRequest,
    ReviewSuggestion,
    Risk,
    RiskLevel,
)

# Risk level to Rich style mapping
RISK_COLORS: dict[RiskLevel, str] = {
    RiskLevel.CRITICAL: "bold red",
    RiskLevel.HIGH: "red",
    RiskLevel.MEDIUM: "yellow",
    RiskLevel.LOW: "blue",
    RiskLevel.INFO: "green",
}

# Risk level display labels
RISK_LABELS: dict[RiskLevel, str] = {
    RiskLevel.CRITICAL: "CRITICAL",
    RiskLevel.HIGH: "HIGH",
    RiskLevel.MEDIUM: "MEDIUM",
    RiskLevel.LOW: "LOW",
    RiskLevel.INFO: "INFO",
}


class TerminalReporter:
    """Reports code review results to the terminal using Rich formatting."""

    def __init__(self, console: Console | None = None) -> None:
        """Initialize the terminal reporter.

        Args:
            console: Optional Rich Console instance for testing.
        """
        self.console = console or Console()

    def print_summary(self, pr: PullRequest, summary: str) -> None:
        """Print a formatted PR summary panel.

        Args:
            pr: Pull request metadata.
            summary: Analysis summary text.
        """
        header = Text()
        header.append(f"PR #{pr.number}", style="bold cyan")
        header.append(" — ")
        header.append(pr.title, style="bold")

        body = Text()
        body.append(f"Author: ", style="dim")
        body.append(f"{pr.author}\n", style="white")
        body.append(f"Repository: ", style="dim")
        body.append(f"{pr.repository}\n", style="white")
        body.append(f"Branch: ", style="dim")
        body.append(f"{pr.head_branch}", style="white")
        body.append(" → ", style="dim")
        body.append(f"{pr.base_branch}\n", style="white")
        if pr.description:
            body.append(f"\n{pr.description}\n", style="italic")
        body.append(f"\n{summary}", style="green")

        panel = Panel(body, title=header, border_style="cyan", padding=(1, 2))
        self.console.print(panel)

    def print_risks(self, risks: List[Risk]) -> None:
        """Print a formatted risk table.

        Args:
            risks: List of identified risks.
        """
        if not risks:
            self.console.print(
                "[green]✓ No risks identified.[/green]"
            )
            return

        table = Table(
            title="Identified Risks",
            title_style="bold",
            border_style="dim",
            show_lines=True,
        )
        table.add_column("Level", style="bold", width=10)
        table.add_column("Category", style="dim", width=14)
        table.add_column("File", style="cyan", min_width=20)
        table.add_column("Line", style="dim", width=6, justify="right")
        table.add_column("Message", min_width=30)

        for risk in risks:
            level_style = RISK_COLORS.get(risk.level, "white")
            level_label = RISK_LABELS.get(risk.level, str(risk.level))

            location = risk.file_path
            line = str(risk.line_number) if risk.line_number else "—"

            table.add_row(
                Text(level_label, style=level_style),
                risk.category.value,
                location,
                line,
                risk.message,
            )

        self.console.print(table)

        # Print suggestions if available
        for risk in risks:
            if risk.suggestion:
                level_style = RISK_COLORS.get(risk.level, "white")
                self.console.print(
                    f"  [{level_style}]→ {risk.suggestion}[/{level_style}]"
                )

    def print_suggestions(self, suggestions: List[ReviewSuggestion]) -> None:
        """Print a formatted suggestions list.

        Args:
            suggestions: List of review suggestions.
        """
        if not suggestions:
            self.console.print(
                "[green]✓ No suggestions.[/green]"
            )
            return

        self.console.print("\n[bold]Review Suggestions[/bold]\n")

        for i, suggestion in enumerate(suggestions, 1):
            # Header with number
            header = Text()
            header.append(f"  {i}. ", style="bold")
            header.append(f"{suggestion.file_path}", style="cyan")
            if suggestion.line_number is not None:
                header.append(f":{suggestion.line_number}", style="dim")

            self.console.print(header)
            self.console.print(f"     {suggestion.message}")

            # Show risk level if associated
            if suggestion.risk:
                level_style = RISK_COLORS.get(suggestion.risk.level, "white")
                level_label = RISK_LABELS.get(
                    suggestion.risk.level, str(suggestion.risk.level)
                )
                self.console.print(
                    f"     [{level_style}][{level_label}][/{level_style}]"
                )

            # Show code snippet if available
            if suggestion.code_snippet:
                self.console.print(f"     [dim]{suggestion.code_snippet}[/dim]")

            self.console.print()  # Blank line between suggestions

    def print_cost_report(self, cost: CostReport) -> None:
        """Print a formatted cost report.

        Args:
            cost: API usage cost report.
        """
        table = Table(
            title="API Cost Report",
            title_style="bold",
            border_style="dim",
            show_lines=False,
        )
        table.add_column("Metric", style="dim", min_width=16)
        table.add_column("Value", justify="right", min_width=12)

        table.add_row("Input Tokens", f"{cost.input_tokens:,}")
        table.add_row("Output Tokens", f"{cost.output_tokens:,}")
        table.add_row("Total Tokens", f"{cost.input_tokens + cost.output_tokens:,}")

        if cost.model_name:
            table.add_row("Model", cost.model_name)

        table.add_row(
            "Total Cost",
            f"[bold green]${cost.total_cost_usd:.4f}[/bold green]",
        )

        self.console.print(table)

    def print_error(self, message: str) -> None:
        """Print a formatted error message.

        Args:
            message: Error message to display.
        """
        self.console.print(f"[bold red]✗ Error:[/bold red] {message}")

    def print_success(self, message: str) -> None:
        """Print a formatted success message.

        Args:
            message: Success message to display.
        """
        self.console.print(f"[bold green]✓[/bold green] {message}")

    def create_progress_bar(self, description: str) -> Progress:
        """Create a Rich progress bar context manager.

        Args:
            description: Description text for the progress bar.

        Returns:
            Rich Progress instance for use as a context manager.
        """
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
        )
