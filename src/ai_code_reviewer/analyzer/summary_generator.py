"""PR change summary generator with bilingual support (Chinese/English)."""

from typing import Dict, List

from ai_code_reviewer.models import ChangeType, FileChange, PullRequest


class SummaryGenerator:
    """Generates structured PR change summaries from file changes.

    Supports Chinese (zh) and English (en) output languages.
    Classifies changes by type and extracts key modifications.
    """

    # Display labels for change types
    _LABELS: Dict[str, Dict[ChangeType, str]] = {
        "en": {
            ChangeType.FEATURE: "Features",
            ChangeType.FIX: "Bug Fixes",
            ChangeType.REFACTOR: "Refactoring",
            ChangeType.DOCS: "Documentation",
            ChangeType.TEST: "Tests",
            ChangeType.CHORE: "Chores",
        },
        "zh": {
            ChangeType.FEATURE: "新功能",
            ChangeType.FIX: "缺陷修复",
            ChangeType.REFACTOR: "重构",
            ChangeType.DOCS: "文档",
            ChangeType.TEST: "测试",
            ChangeType.CHORE: "杂项",
        },
    }

    # Section headers
    _HEADERS: Dict[str, Dict[str, str]] = {
        "en": {
            "title": "PR Summary",
            "changes_by_type": "Changes by Type",
            "key_changes": "Key Changes",
            "files": "files",
            "file": "file",
        },
        "zh": {
            "title": "PR 变更总结",
            "changes_by_type": "按类型分类",
            "key_changes": "关键变更",
            "files": "个文件",
            "file": "个文件",
        },
    }

    def __init__(self, language: str = "en") -> None:
        """Initialize the summary generator.

        Args:
            language: Output language, either 'en' or 'zh'. Defaults to 'en'.
        """
        if language not in ("en", "zh"):
            raise ValueError(f"Unsupported language: {language!r}. Use 'en' or 'zh'.")
        self._language = language

    @property
    def language(self) -> str:
        """Return the current output language."""
        return self._language

    def generate_summary(self, pr: PullRequest, files: List[FileChange]) -> str:
        """Generate a complete PR change summary.

        Args:
            pr: Pull request metadata.
            files: List of file changes in the PR.

        Returns:
            Formatted markdown summary string.
        """
        if not files:
            return self._empty_summary(pr)

        classified = self.classify_changes(files)
        key_changes = self.extract_key_changes(files)
        return self.format_summary(pr, classified, key_changes)

    def classify_changes(self, files: List[FileChange]) -> Dict[ChangeType, List[str]]:
        """Classify file changes by their change type.

        Args:
            files: List of file changes to classify.

        Returns:
            Dict mapping ChangeType to list of file paths.
        """
        classified: Dict[ChangeType, List[str]] = {}
        for f in files:
            classified.setdefault(f.change_type, []).append(f.file_path)
        return classified

    def extract_key_changes(self, files: List[FileChange]) -> List[str]:
        """Extract key change descriptions from file changes.

        Analyzes file paths, change types, and diff content to produce
        human-readable change descriptions.

        Args:
            files: List of file changes to analyze.

        Returns:
            List of key change description strings (up to 10 items).
        """
        key_changes: List[str] = []

        for f in files:
            description = self._describe_change(f)
            if description:
                key_changes.append(description)

        # Deduplicate while preserving order
        seen: set = set()
        unique: List[str] = []
        for item in key_changes:
            if item not in seen:
                seen.add(item)
                unique.append(item)

        return unique[:10]

    def format_summary(
        self,
        pr: PullRequest,
        changes: Dict[ChangeType, List[str]],
        key_changes: List[str],
    ) -> str:
        """Format the summary as a structured markdown string.

        Args:
            pr: Pull request metadata.
            changes: Classified changes by type.
            key_changes: List of key change descriptions.

        Returns:
            Formatted markdown summary.
        """
        lang = self._language
        headers = self._HEADERS[lang]
        labels = self._LABELS[lang]

        # Calculate totals
        total_files = sum(len(files) for files in changes.values())
        total_additions = 0
        total_deletions = 0

        # We need file changes for counting - reconstruct from what we have
        lines: List[str] = []

        # Header
        lines.append(f"## {headers['title']}")
        lines.append("")
        lines.append(f"**Title**: {pr.title}")
        lines.append(f"**Author**: {pr.author}")
        lines.append(f"**Changes**: {total_files} file(s) modified")
        lines.append("")

        # Changes by type
        lines.append(f"### {headers['changes_by_type']}")
        lines.append("")

        # Sort by change type for consistent output
        for change_type in ChangeType:
            file_list = changes.get(change_type, [])
            if not file_list:
                continue

            count = len(file_list)
            label = labels[change_type]
            file_word = headers["files"] if count > 1 else headers["file"]
            lines.append(f"**{label}** ({count} {file_word}):")

            for file_path in file_list:
                lines.append(f"- {file_path}")

            lines.append("")

        # Key changes
        if key_changes:
            lines.append(f"### {headers['key_changes']}")
            lines.append("")
            for i, change in enumerate(key_changes, 1):
                lines.append(f"{i}. {change}")
            lines.append("")

        return "\n".join(lines)

    def _describe_change(self, file_change: FileChange) -> str:
        """Generate a human-readable description for a single file change.

        Args:
            file_change: The file change to describe.

        Returns:
            Description string, or empty if no meaningful description.
        """
        lang = self._language
        path = file_change.file_path
        change_type = file_change.change_type
        name = self._extract_file_name(path)

        if lang == "zh":
            return self._describe_change_zh(file_change, name)
        return self._describe_change_en(file_change, name)

    def _describe_change_en(self, file_change: FileChange, name: str) -> str:
        """Generate English description for a file change."""
        path = file_change.file_path
        ct = file_change.change_type

        if ct == ChangeType.FEATURE:
            return f"Added new functionality in {name}"
        if ct == ChangeType.FIX:
            return f"Fixed issue in {name}"
        if ct == ChangeType.REFACTOR:
            return f"Refactored code in {name}"
        if ct == ChangeType.DOCS:
            return f"Updated documentation in {name}"
        if ct == ChangeType.TEST:
            return f"Updated tests in {name}"
        if ct == ChangeType.CHORE:
            return f"Updated {name}"
        return f"Changed {name}"

    def _describe_change_zh(self, file_change: FileChange, name: str) -> str:
        """Generate Chinese description for a file change."""
        path = file_change.file_path
        ct = file_change.change_type

        if ct == ChangeType.FEATURE:
            return f"在 {name} 中添加新功能"
        if ct == ChangeType.FIX:
            return f"修复 {name} 中的问题"
        if ct == ChangeType.REFACTOR:
            return f"重构 {name} 中的代码"
        if ct == ChangeType.DOCS:
            return f"更新 {name} 中的文档"
        if ct == ChangeType.TEST:
            return f"更新 {name} 中的测试"
        if ct == ChangeType.CHORE:
            return f"更新 {name}"
        return f"变更 {name}"

    @staticmethod
    def _extract_file_name(file_path: str) -> str:
        """Extract the file name from a path for display.

        Args:
            file_path: Full file path.

        Returns:
            File name without directory prefix.
        """
        return file_path.rsplit("/", 1)[-1] if "/" in file_path else file_path

    def _empty_summary(self, pr: PullRequest) -> str:
        """Generate a summary for PRs with no file changes.

        Args:
            pr: Pull request metadata.

        Returns:
            Minimal summary string.
        """
        lang = self._language
        headers = self._HEADERS[lang]

        lines = [
            f"## {headers['title']}",
            "",
            f"**Title**: {pr.title}",
            f"**Author**: {pr.author}",
            "**Changes**: No files changed",
            "",
        ]
        return "\n".join(lines)
