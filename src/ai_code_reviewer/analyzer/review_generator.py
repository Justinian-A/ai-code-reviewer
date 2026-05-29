"""Review suggestion generator for AI Code Reviewer."""

from typing import Dict, List

from ai_code_reviewer.models import Risk, RiskCategory, RiskLevel, ReviewSuggestion


# Actionable suggestion templates per category and level
_SUGGESTION_TEMPLATES: Dict[RiskCategory, Dict[RiskLevel, str]] = {
    RiskCategory.SECURITY: {
        RiskLevel.CRITICAL: "SECURITY CRITICAL: {message}. This MUST be fixed before merging.",
        RiskLevel.HIGH: "SECURITY HIGH: {message}. Strongly recommend fixing before merge.",
        RiskLevel.MEDIUM: "SECURITY MEDIUM: {message}. Consider addressing in this PR.",
        RiskLevel.LOW: "SECURITY LOW: {message}. Can be addressed in a follow-up.",
        RiskLevel.INFO: "SECURITY INFO: {message}. For awareness.",
    },
    RiskCategory.LOGIC: {
        RiskLevel.CRITICAL: "LOGIC CRITICAL: {message}. This will cause runtime failures.",
        RiskLevel.HIGH: "LOGIC HIGH: {message}. Likely to cause bugs in production.",
        RiskLevel.MEDIUM: "LOGIC MEDIUM: {message}. May lead to unexpected behavior.",
        RiskLevel.LOW: "LOGIC LOW: {message}. Minor logic concern.",
        RiskLevel.INFO: "LOGIC INFO: {message}. Stylistic or minor observation.",
    },
    RiskCategory.ARCHITECTURE: {
        RiskLevel.CRITICAL: "ARCHITECTURE CRITICAL: {message}. Fundamental design issue.",
        RiskLevel.HIGH: "ARCHITECTURE HIGH: {message}. Significant design concern.",
        RiskLevel.MEDIUM: "ARCHITECTURE MEDIUM: {message}. Consider refactoring.",
        RiskLevel.LOW: "ARCHITECTURE LOW: {message}. Minor architectural note.",
        RiskLevel.INFO: "ARCHITECTURE INFO: {message}. For future consideration.",
    },
}


def _build_suggestion_message(risk: Risk) -> str:
    """Build a concrete, actionable suggestion message from a risk."""
    templates = _SUGGESTION_TEMPLATES.get(risk.category, {})
    template = templates.get(risk.level, "{message}")
    return template.format(message=risk.message)


def _is_must_fix(level: RiskLevel) -> bool:
    """Return True if the risk level requires immediate action."""
    return level in (RiskLevel.CRITICAL, RiskLevel.HIGH)


class ReviewGenerator:
    """Generates review suggestions from identified risks."""

    def generate_suggestions(self, risks: List[Risk]) -> List[ReviewSuggestion]:
        """Convert a list of risks into review suggestions.

        Args:
            risks: List of Risk objects identified during analysis.

        Returns:
            List of ReviewSuggestion objects sorted by severity (critical first).
        """
        suggestions = [self.format_suggestion(risk) for risk in risks]
        # Sort: critical -> high -> medium -> low -> info
        level_order = {
            RiskLevel.CRITICAL: 0,
            RiskLevel.HIGH: 1,
            RiskLevel.MEDIUM: 2,
            RiskLevel.LOW: 3,
            RiskLevel.INFO: 4,
        }
        suggestions.sort(key=lambda s: level_order.get(s.risk.level, 5) if s.risk else 5)
        return suggestions

    def group_by_priority(self, risks: List[Risk]) -> Dict[RiskLevel, List[Risk]]:
        """Group risks by their priority level.

        Args:
            risks: List of Risk objects.

        Returns:
            Dictionary mapping RiskLevel to lists of Risk objects.
            Only levels with at least one risk are included.
        """
        groups: Dict[RiskLevel, List[Risk]] = {}
        for risk in risks:
            groups.setdefault(risk.level, []).append(risk)
        return groups

    def format_suggestion(self, risk: Risk) -> ReviewSuggestion:
        """Format a single risk into a review suggestion.

        Args:
            risk: The Risk object to format.

        Returns:
            A ReviewSuggestion with an actionable message.
        """
        message = _build_suggestion_message(risk)
        # Prepend the original suggestion if available
        if risk.suggestion:
            message = f"{message}\n\nSuggested fix: {risk.suggestion}"

        return ReviewSuggestion(
            file_path=risk.file_path,
            line_number=risk.line_number,
            message=message,
            risk=risk,
            code_snippet=None,  # Code snippets are populated by callers with diff context
        )

    def generate_summary(self, suggestions: List[ReviewSuggestion]) -> str:
        """Generate a human-readable summary of all suggestions.

        Args:
            suggestions: List of ReviewSuggestion objects.

        Returns:
            Summary string with counts and must-fix indicator.
        """
        if not suggestions:
            return "No issues found. Code looks good!"

        # Count by level
        counts: Dict[RiskLevel, int] = {}
        for s in suggestions:
            if s.risk:
                counts[s.risk.level] = counts.get(s.risk.level, 0) + 1

        total = len(suggestions)
        must_fix = sum(1 for s in suggestions if s.risk and _is_must_fix(s.risk.level))

        # Build summary lines
        lines = [f"Review Summary: {total} suggestion(s) found."]
        lines.append("")

        level_labels = {
            RiskLevel.CRITICAL: "Critical (must fix)",
            RiskLevel.HIGH: "High (must fix)",
            RiskLevel.MEDIUM: "Medium",
            RiskLevel.LOW: "Low",
            RiskLevel.INFO: "Info",
        }
        for level in RiskLevel:
            count = counts.get(level, 0)
            if count > 0:
                label = level_labels.get(level, level.value)
                lines.append(f"  - {label}: {count}")

        if must_fix > 0:
            lines.append("")
            lines.append(
                f"BLOCKER: {must_fix} issue(s) must be resolved before merging."
            )
        else:
            lines.append("")
            lines.append("No blockers. All suggestions are advisory.")

        return "\n".join(lines)
