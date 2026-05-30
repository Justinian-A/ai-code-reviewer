"""Risk detection and aggregation across Python and JS/TS analyzers."""

from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from ai_code_reviewer.analyzer.js_ts_analyzer import JSTSAnalyzer
from ai_code_reviewer.analyzer.python_analyzer import PythonAnalyzer
from ai_code_reviewer.models import (
    FileChange,
    Risk,
    RiskCategory,
    RiskLevel,
)

# Priority ordering: lower number = higher priority
RISK_PRIORITY: Dict[RiskLevel, int] = {
    RiskLevel.CRITICAL: 0,
    RiskLevel.HIGH: 1,
    RiskLevel.MEDIUM: 2,
    RiskLevel.LOW: 3,
    RiskLevel.INFO: 4,
}

# Extension → language mapping for routing files to analyzers
_EXT_TO_LANG: Dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
}


def _infer_language(file_path: str, explicit_language: Optional[str] = None) -> Optional[str]:
    """Infer the language from the explicit hint or file extension.

    Args:
        file_path: Path to the source file.
        explicit_language: Language field from FileChange, if set.

    Returns:
        Language string ('python', 'javascript', 'typescript') or None.
    """
    if explicit_language:
        lang = explicit_language.lower()
        if lang in ("python", "javascript", "typescript"):
            return lang
        # Map common aliases
        if lang in ("py",):
            return "python"
        if lang in ("js", "jsx", "mjs"):
            return "javascript"
        if lang in ("ts", "tsx"):
            return "typescript"

    ext = Path(file_path).suffix.lower()
    return _EXT_TO_LANG.get(ext)


class RiskDetector:
    """Detects, merges, deduplicates, and sorts risks from code analyzers.

    Integrates PythonAnalyzer and JSTSAnalyzer to provide a unified risk
    detection pipeline for mixed-language pull requests.
    """

    def __init__(self) -> None:
        """Initialize the RiskDetector with language-specific analyzers."""
        self._python_analyzer = PythonAnalyzer()
        self._js_ts_analyzer = JSTSAnalyzer()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect_risks(self, files: List[FileChange]) -> List[Risk]:
        """Detect all risks across a list of file changes.

        Routes each file to the appropriate analyzer based on language,
        then merges and deduplicates results.

        Args:
            files: List of FileChange objects to analyze.

        Returns:
            Deduplicated and priority-sorted list of risks.
        """
        all_risks: List[List[Risk]] = []

        for fc in files:
            risks = self._analyze_single_file(fc)
            if risks:
                all_risks.append(risks)

        merged = self.merge_risks(all_risks)
        deduplicated = self.deduplicate_risks(merged)
        return self.sort_by_priority(deduplicated)

    def merge_risks(self, risks_list: List[List[Risk]]) -> List[Risk]:
        """Merge multiple risk lists into a single flat list.

        Args:
            risks_list: List of risk lists to merge.

        Returns:
            Flat list containing all risks from all input lists.
        """
        merged: List[Risk] = []
        for risks in risks_list:
            merged.extend(risks)
        return merged

    def deduplicate_risks(self, risks: List[Risk]) -> List[Risk]:
        """Remove duplicate risks based on file path, line number, and message.

        Two risks are considered duplicates when they share the same
        (file_path, line_number, message). When duplicates are found,
        the first occurrence is kept (preserving the highest-priority one
        if the caller has already sorted).

        Args:
            risks: List of risks to deduplicate.

        Returns:
            Deduplicated list of risks.
        """
        seen: Set[Tuple[str, Optional[int], str]] = set()
        unique: List[Risk] = []

        for risk in risks:
            key = (risk.file_path, risk.line_number, risk.message)
            if key not in seen:
                seen.add(key)
                unique.append(risk)

        return unique

    def sort_by_priority(self, risks: List[Risk]) -> List[Risk]:
        """Sort risks by priority level (critical first, info last).

        Uses RISK_PRIORITY mapping: critical=0, high=1, medium=2, low=3, info=4.

        Args:
            risks: List of risks to sort.

        Returns:
            New list sorted by priority (highest first).
        """
        return sorted(risks, key=lambda r: RISK_PRIORITY.get(r.level, 99))

    def filter_by_category(
        self, risks: List[Risk], category: RiskCategory
    ) -> List[Risk]:
        """Filter risks to only those matching the given category.

        Args:
            risks: List of risks to filter.
            category: RiskCategory to keep.

        Returns:
            List of risks matching the specified category.
        """
        return [r for r in risks if r.category == category]

    def filter_by_level(
        self, risks: List[Risk], level: RiskLevel
    ) -> List[Risk]:
        """Filter risks to only those matching the given level.

        Args:
            risks: List of risks to filter.
            level: RiskLevel to keep.

        Returns:
            List of risks matching the specified level.
        """
        return [r for r in risks if r.level == level]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _analyze_single_file(self, fc: FileChange) -> List[Risk]:
        """Analyze a single FileChange using the appropriate analyzer.

        Args:
            fc: FileChange to analyze.

        Returns:
            List of risks found in the file, or empty list if the
            language is unsupported or there is no content to analyze.
        """
        language = _infer_language(fc.file_path, fc.language)
        code = fc.diff_content

        if not code or not language:
            return []

        if language == "python":
            risks = self._python_analyzer.analyze_code(code)
        elif language in ("javascript", "typescript"):
            risks = self._js_ts_analyzer.analyze_code(
                code, language, file_path=fc.file_path
            )
        else:
            return []

        # Ensure file_path is set correctly on all risks
        for risk in risks:
            risk.file_path = fc.file_path

        return risks
