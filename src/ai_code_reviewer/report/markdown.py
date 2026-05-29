"""Markdown report generator for code review results."""

from pathlib import Path
from typing import Dict, List, Optional

from ai_code_reviewer.models import (
    AnalysisResult,
    CostReport,
    PullRequest,
    Risk,
    RiskLevel,
    ReviewSuggestion,
)

# Language strings for i18n
_STRINGS: Dict[str, Dict[str, str]] = {
    "en": {
        "report_title": "Code Review Report",
        "summary": "Summary",
        "pr": "PR",
        "author": "Author",
        "repository": "Repository",
        "changes": "Changes",
        "additions": "additions",
        "deletions": "deletions",
        "across": "across",
        "files": "files",
        "risks_found": "Risks Found",
        "level": "Level",
        "category": "Category",
        "file": "File",
        "line": "Line",
        "description": "Description",
        "suggestions": "Suggestions",
        "cost_report": "Cost Report",
        "input_tokens": "Input Tokens",
        "output_tokens": "Output Tokens",
        "total_cost": "Total Cost",
        "no_risks": "No risks identified.",
        "no_suggestions": "No suggestions.",
        "not_available": "N/A",
    },
    "zh": {
        "report_title": "代码审查报告",
        "summary": "摘要",
        "pr": "PR",
        "author": "作者",
        "repository": "仓库",
        "changes": "变更",
        "additions": "新增",
        "deletions": "删除",
        "across": "涉及",
        "files": "个文件",
        "risks_found": "发现的风险",
        "level": "级别",
        "category": "分类",
        "file": "文件",
        "line": "行号",
        "description": "描述",
        "suggestions": "建议",
        "cost_report": "成本报告",
        "input_tokens": "输入Token",
        "output_tokens": "输出Token",
        "total_cost": "总成本",
        "no_risks": "未发现风险。",
        "no_suggestions": "暂无建议。",
        "not_available": "无",
    },
}


class MarkdownReporter:
    """Generates Markdown-formatted code review reports."""

    def __init__(self, language: str = "en") -> None:
        """Initialize the reporter.

        Args:
            language: Output language, either 'en' or 'zh'.
        """
        if language not in _STRINGS:
            raise ValueError(f"Unsupported language: {language}. Use 'en' or 'zh'.")
        self._lang = language
        self._strings = _STRINGS[language]

    @property
    def language(self) -> str:
        """Return the current language setting."""
        return self._lang

    def _t(self, key: str) -> str:
        """Translate a string key to the current language."""
        return self._strings[key]

    def generate_report(self, result: AnalysisResult) -> str:
        """Generate a complete Markdown report.

        Args:
            result: The analysis result to format.

        Returns:
            Complete Markdown report as a string.
        """
        sections = [
            f"# {self._t('report_title')}\n",
            self.generate_summary_section(result.pr, result.summary or ""),
            self.generate_risks_section(result.risks),
            self.generate_suggestions_section(result.suggestions),
        ]

        if result.cost:
            sections.append(self.generate_cost_section(result.cost))

        return "\n".join(sections)

    def generate_summary_section(self, pr: PullRequest, summary: str) -> str:
        """Generate the summary section of the report.

        Args:
            pr: Pull request metadata.
            summary: Text summary of the analysis.

        Returns:
            Markdown summary section.
        """
        # Calculate total changes from the PR context
        # Note: File changes are not passed here, so we use placeholder values
        lines = [
            f"## {self._t('summary')}\n",
            f"**{self._t('pr')}**: #{pr.number} - {pr.title}",
            f"**{self._t('author')}**: {pr.author}",
            f"**{self._t('repository')}**: {pr.repository}",
        ]

        if summary:
            lines.append(f"\n{summary}")

        return "\n".join(lines)

    def generate_summary_section_with_changes(
        self,
        pr: PullRequest,
        summary: str,
        total_additions: int,
        total_deletions: int,
        file_count: int,
    ) -> str:
        """Generate the summary section with change statistics.

        Args:
            pr: Pull request metadata.
            summary: Text summary of the analysis.
            total_additions: Total lines added.
            total_deletions: Total lines deleted.
            file_count: Number of files changed.

        Returns:
            Markdown summary section.
        """
        lines = [
            f"## {self._t('summary')}\n",
            f"**{self._t('pr')}**: #{pr.number} - {pr.title}",
            f"**{self._t('author')}**: {pr.author}",
            f"**{self._t('repository')}**: {pr.repository}",
            f"**{self._t('changes')}**: {total_additions} {self._t('additions')}, "
            f"{total_deletions} {self._t('deletions')} "
            f"{self._t('across')} {file_count} {self._t('files')}",
        ]

        if summary:
            lines.append(f"\n{summary}")

        return "\n".join(lines)

    def generate_risks_section(self, risks: List[Risk]) -> str:
        """Generate the risks section of the report.

        Args:
            risks: List of identified risks.

        Returns:
            Markdown risks section.
        """
        lines = [f"## {self._t('risks_found')}\n"]

        if not risks:
            lines.append(self._t("no_risks"))
            return "\n".join(lines)

        # Table header
        lines.append(
            f"| {self._t('level')} | {self._t('category')} | "
            f"{self._t('file')} | {self._t('line')} | "
            f"{self._t('description')} |"
        )
        lines.append("|-------|----------|------|------|-------------|")

        # Table rows
        for risk in risks:
            level = risk.level.value.upper()
            category = risk.category.value
            file_path = risk.file_path
            line_num = str(risk.line_number) if risk.line_number else self._t("not_available")
            description = risk.message
            lines.append(
                f"| {level} | {category} | {file_path} | {line_num} | {description} |"
            )

        return "\n".join(lines)

    def generate_suggestions_section(self, suggestions: List[ReviewSuggestion]) -> str:
        """Generate the suggestions section of the report.

        Args:
            suggestions: List of review suggestions.

        Returns:
            Markdown suggestions section.
        """
        lines = [f"## {self._t('suggestions')}\n"]

        if not suggestions:
            lines.append(self._t("no_suggestions"))
            return "\n".join(lines)

        for i, suggestion in enumerate(suggestions, 1):
            location = suggestion.file_path
            if suggestion.line_number:
                location += f":{suggestion.line_number}"
            lines.append(f"{i}. **{location}** - {suggestion.message}")

        return "\n".join(lines)

    def generate_cost_section(self, cost: CostReport) -> str:
        """Generate the cost section of the report.

        Args:
            cost: Cost report data.

        Returns:
            Markdown cost section.
        """
        lines = [
            f"## {self._t('cost_report')}\n",
            f"- **{self._t('input_tokens')}**: {cost.input_tokens:,}",
            f"- **{self._t('output_tokens')}**: {cost.output_tokens:,}",
            f"- **{self._t('total_cost')}**: ${cost.total_cost_usd:.4f}",
        ]

        return "\n".join(lines)

    def save_report(self, result: AnalysisResult, output_path: str) -> None:
        """Generate and save the report to a file.

        Args:
            result: The analysis result to format.
            output_path: Path to save the Markdown report.
        """
        report_content = self.generate_report(result)
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report_content, encoding="utf-8")
