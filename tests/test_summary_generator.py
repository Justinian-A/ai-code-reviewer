"""Tests for the SummaryGenerator class."""

from datetime import UTC, datetime

import pytest

from ai_code_reviewer.analyzer.summary_generator import SummaryGenerator
from ai_code_reviewer.models import ChangeType, FileChange, PullRequest


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def sample_pr() -> PullRequest:
    """Create a sample pull request for testing."""
    return PullRequest(
        number=42,
        title="Add authentication module",
        description="Implements JWT-based auth",
        author="testuser",
        repository="org/repo",
        base_branch="main",
        head_branch="feature/auth",
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
        updated_at=datetime(2025, 1, 2, tzinfo=UTC),
    )


@pytest.fixture
def sample_files() -> list[FileChange]:
    """Create a sample list of file changes."""
    return [
        FileChange(
            file_path="src/auth/login.py",
            change_type=ChangeType.FEATURE,
            additions=50,
            deletions=5,
        ),
        FileChange(
            file_path="src/auth/jwt.py",
            change_type=ChangeType.FEATURE,
            additions=30,
            deletions=0,
        ),
        FileChange(
            file_path="src/utils/helper.py",
            change_type=ChangeType.FIX,
            additions=10,
            deletions=8,
        ),
        FileChange(
            file_path="src/core/module.py",
            change_type=ChangeType.REFACTOR,
            additions=20,
            deletions=15,
        ),
        FileChange(
            file_path="docs/README.md",
            change_type=ChangeType.DOCS,
            additions=5,
            deletions=2,
        ),
        FileChange(
            file_path="tests/test_auth.py",
            change_type=ChangeType.TEST,
            additions=40,
            deletions=0,
        ),
        FileChange(
            file_path="pyproject.toml",
            change_type=ChangeType.CHORE,
            additions=3,
            deletions=1,
        ),
    ]


@pytest.fixture
def en_generator() -> SummaryGenerator:
    """Create an English summary generator."""
    return SummaryGenerator(language="en")


@pytest.fixture
def zh_generator() -> SummaryGenerator:
    """Create a Chinese summary generator."""
    return SummaryGenerator(language="zh")


# ------------------------------------------------------------------
# Initialization tests
# ------------------------------------------------------------------


class TestInit:
    """Tests for SummaryGenerator initialization."""

    def test_default_language_is_english(self) -> None:
        gen = SummaryGenerator()
        assert gen.language == "en"

    def test_explicit_english(self) -> None:
        gen = SummaryGenerator(language="en")
        assert gen.language == "en"

    def test_explicit_chinese(self) -> None:
        gen = SummaryGenerator(language="zh")
        assert gen.language == "zh"

    def test_unsupported_language_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported language"):
            SummaryGenerator(language="fr")


# ------------------------------------------------------------------
# classify_changes tests
# ------------------------------------------------------------------


class TestClassifyChanges:
    """Tests for the classify_changes method."""

    def test_classify_returns_all_types(
        self, en_generator: SummaryGenerator, sample_files: list[FileChange]
    ) -> None:
        result = en_generator.classify_changes(sample_files)
        assert ChangeType.FEATURE in result
        assert ChangeType.FIX in result
        assert ChangeType.REFACTOR in result
        assert ChangeType.DOCS in result
        assert ChangeType.TEST in result
        assert ChangeType.CHORE in result

    def test_classify_correct_file_count(
        self, en_generator: SummaryGenerator, sample_files: list[FileChange]
    ) -> None:
        result = en_generator.classify_changes(sample_files)
        assert len(result[ChangeType.FEATURE]) == 2
        assert len(result[ChangeType.FIX]) == 1
        assert len(result[ChangeType.REFACTOR]) == 1

    def test_classify_correct_file_paths(
        self, en_generator: SummaryGenerator, sample_files: list[FileChange]
    ) -> None:
        result = en_generator.classify_changes(sample_files)
        assert "src/auth/login.py" in result[ChangeType.FEATURE]
        assert "src/auth/jwt.py" in result[ChangeType.FEATURE]

    def test_classify_single_type(self, en_generator: SummaryGenerator) -> None:
        files = [
            FileChange(file_path="a.py", change_type=ChangeType.FIX, additions=5, deletions=2),
        ]
        result = en_generator.classify_changes(files)
        assert len(result) == 1
        assert result[ChangeType.FIX] == ["a.py"]

    def test_classify_empty_list(self, en_generator: SummaryGenerator) -> None:
        result = en_generator.classify_changes([])
        assert result == {}


# ------------------------------------------------------------------
# extract_key_changes tests
# ------------------------------------------------------------------


class TestExtractKeyChanges:
    """Tests for the extract_key_changes method."""

    def test_returns_descriptions(self, en_generator: SummaryGenerator, sample_files: list[FileChange]) -> None:
        result = en_generator.extract_key_changes(sample_files)
        assert len(result) > 0
        assert all(isinstance(item, str) for item in result)

    def test_max_ten_items(self, en_generator: SummaryGenerator) -> None:
        files = [
            FileChange(file_path=f"file{i}.py", change_type=ChangeType.FEATURE, additions=1)
            for i in range(20)
        ]
        result = en_generator.extract_key_changes(files)
        assert len(result) <= 10

    def test_deduplication(self, en_generator: SummaryGenerator) -> None:
        # Same file path and type should produce same description
        files = [
            FileChange(file_path="a.py", change_type=ChangeType.FIX, additions=1),
            FileChange(file_path="a.py", change_type=ChangeType.FIX, additions=2),
        ]
        result = en_generator.extract_key_changes(files)
        assert len(result) == 1

    def test_empty_input(self, en_generator: SummaryGenerator) -> None:
        result = en_generator.extract_key_changes([])
        assert result == []

    def test_english_descriptions(self, en_generator: SummaryGenerator) -> None:
        files = [
            FileChange(file_path="src/auth.py", change_type=ChangeType.FEATURE, additions=10),
            FileChange(file_path="src/bug.py", change_type=ChangeType.FIX, additions=5),
        ]
        result = en_generator.extract_key_changes(files)
        assert any("Added" in desc for desc in result)
        assert any("Fixed" in desc for desc in result)

    def test_chinese_descriptions(self, zh_generator: SummaryGenerator) -> None:
        files = [
            FileChange(file_path="src/auth.py", change_type=ChangeType.FEATURE, additions=10),
            FileChange(file_path="src/bug.py", change_type=ChangeType.FIX, additions=5),
        ]
        result = zh_generator.extract_key_changes(files)
        assert any("新功能" in desc or "添加" in desc for desc in result)
        assert any("修复" in desc for desc in result)


# ------------------------------------------------------------------
# format_summary tests
# ------------------------------------------------------------------


class TestFormatSummary:
    """Tests for the format_summary method."""

    def test_contains_title(self, en_generator: SummaryGenerator, sample_pr: PullRequest) -> None:
        changes = {ChangeType.FEATURE: ["a.py"]}
        result = en_generator.format_summary(sample_pr, changes, ["Added a"])
        assert "PR Summary" in result

    def test_contains_pr_metadata(self, en_generator: SummaryGenerator, sample_pr: PullRequest) -> None:
        changes = {ChangeType.FEATURE: ["a.py"]}
        result = en_generator.format_summary(sample_pr, changes, ["Added a"])
        assert "Add authentication module" in result
        assert "testuser" in result

    def test_contains_change_types(self, en_generator: SummaryGenerator, sample_pr: PullRequest) -> None:
        changes = {
            ChangeType.FEATURE: ["a.py", "b.py"],
            ChangeType.FIX: ["c.py"],
        }
        result = en_generator.format_summary(sample_pr, changes, [])
        assert "Features" in result
        assert "Bug Fixes" in result

    def test_contains_file_paths(self, en_generator: SummaryGenerator, sample_pr: PullRequest) -> None:
        changes = {ChangeType.FEATURE: ["src/auth.py"]}
        result = en_generator.format_summary(sample_pr, changes, [])
        assert "src/auth.py" in result

    def test_contains_key_changes(self, en_generator: SummaryGenerator, sample_pr: PullRequest) -> None:
        changes = {ChangeType.FEATURE: ["a.py"]}
        key = ["Added authentication", "Updated config"]
        result = en_generator.format_summary(sample_pr, changes, key)
        assert "Key Changes" in result
        assert "1. Added authentication" in result
        assert "2. Updated config" in result

    def test_chinese_output(self, zh_generator: SummaryGenerator, sample_pr: PullRequest) -> None:
        changes = {ChangeType.FEATURE: ["a.py"]}
        result = zh_generator.format_summary(sample_pr, changes, ["添加认证"])
        assert "PR 变更总结" in result
        assert "新功能" in result
        assert "关键变更" in result
        assert "添加认证" in result

    def test_file_count_display(self, en_generator: SummaryGenerator, sample_pr: PullRequest) -> None:
        changes = {ChangeType.FEATURE: ["a.py", "b.py"]}
        result = en_generator.format_summary(sample_pr, changes, [])
        assert "2 files" in result

    def test_single_file_count_display(self, en_generator: SummaryGenerator, sample_pr: PullRequest) -> None:
        changes = {ChangeType.FEATURE: ["a.py"]}
        result = en_generator.format_summary(sample_pr, changes, [])
        assert "1 file" in result

    def test_no_key_changes_section_when_empty(
        self, en_generator: SummaryGenerator, sample_pr: PullRequest
    ) -> None:
        changes = {ChangeType.FEATURE: ["a.py"]}
        result = en_generator.format_summary(sample_pr, changes, [])
        assert "Key Changes" not in result


# ------------------------------------------------------------------
# generate_summary integration tests
# ------------------------------------------------------------------


class TestGenerateSummary:
    """Integration tests for generate_summary."""

    def test_full_summary_english(
        self, en_generator: SummaryGenerator, sample_pr: PullRequest, sample_files: list[FileChange]
    ) -> None:
        result = en_generator.generate_summary(sample_pr, sample_files)
        assert "PR Summary" in result
        assert "Add authentication module" in result
        assert "testuser" in result
        assert "Features" in result
        assert "Bug Fixes" in result
        assert "Key Changes" in result

    def test_full_summary_chinese(
        self, zh_generator: SummaryGenerator, sample_pr: PullRequest, sample_files: list[FileChange]
    ) -> None:
        result = zh_generator.generate_summary(sample_pr, sample_files)
        assert "PR 变更总结" in result
        assert "新功能" in result
        assert "缺陷修复" in result
        assert "关键变更" in result

    def test_empty_files(self, en_generator: SummaryGenerator, sample_pr: PullRequest) -> None:
        result = en_generator.generate_summary(sample_pr, [])
        assert "PR Summary" in result
        assert "No files changed" in result

    def test_single_file_change(self, en_generator: SummaryGenerator, sample_pr: PullRequest) -> None:
        files = [FileChange(file_path="a.py", change_type=ChangeType.FIX, additions=5, deletions=2)]
        result = en_generator.generate_summary(sample_pr, files)
        assert "Bug Fixes" in result
        assert "a.py" in result

    def test_output_is_markdown(
        self, en_generator: SummaryGenerator, sample_pr: PullRequest, sample_files: list[FileChange]
    ) -> None:
        result = en_generator.generate_summary(sample_pr, sample_files)
        assert result.startswith("## ")
        assert "**" in result


# ------------------------------------------------------------------
# Edge case tests
# ------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_file_path_extraction(self) -> None:
        assert SummaryGenerator._extract_file_name("src/auth.py") == "auth.py"
        assert SummaryGenerator._extract_file_name("auth.py") == "auth.py"
        assert SummaryGenerator._extract_file_name("deep/nested/path/file.py") == "file.py"

    def test_all_change_types_covered_en(self, en_generator: SummaryGenerator) -> None:
        files = [
            FileChange(file_path=f"{ct.value}.py", change_type=ct, additions=1)
            for ct in ChangeType
        ]
        result = en_generator.extract_key_changes(files)
        assert len(result) == len(ChangeType)

    def test_all_change_types_covered_zh(self, zh_generator: SummaryGenerator) -> None:
        files = [
            FileChange(file_path=f"{ct.value}.py", change_type=ct, additions=1)
            for ct in ChangeType
        ]
        result = zh_generator.extract_key_changes(files)
        assert len(result) == len(ChangeType)
