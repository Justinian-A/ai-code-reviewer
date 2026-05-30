"""Tests for the RiskDetector class."""

import pytest

from ai_code_reviewer.analyzer.risk_detector import RISK_PRIORITY, RiskDetector
from ai_code_reviewer.models import (
    ChangeType,
    FileChange,
    Risk,
    RiskCategory,
    RiskLevel,
)


@pytest.fixture
def detector() -> RiskDetector:
    """Create a RiskDetector instance."""
    return RiskDetector()


# ---------------------------------------------------------------------------
# Fixtures: sample risks
# ---------------------------------------------------------------------------


def _make_risk(
    level: RiskLevel = RiskLevel.MEDIUM,
    category: RiskCategory = RiskCategory.LOGIC,
    message: str = "test risk",
    file_path: str = "test.py",
    line_number: int | None = 1,
    suggestion: str | None = None,
) -> Risk:
    """Helper to create a Risk with defaults."""
    return Risk(
        level=level,
        category=category,
        message=message,
        file_path=file_path,
        line_number=line_number,
        suggestion=suggestion,
    )


def _make_file_change(
    file_path: str = "test.py",
    language: str | None = None,
    diff_content: str | None = None,
    change_type: ChangeType = ChangeType.FIX,
) -> FileChange:
    """Helper to create a FileChange."""
    return FileChange(
        file_path=file_path,
        change_type=change_type,
        language=language,
        diff_content=diff_content,
    )


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestInit:
    def test_creates_instance(self, detector: RiskDetector):
        assert detector is not None

    def test_has_python_analyzer(self, detector: RiskDetector):
        assert detector._python_analyzer is not None

    def test_has_js_ts_analyzer(self, detector: RiskDetector):
        assert detector._js_ts_analyzer is not None


# ---------------------------------------------------------------------------
# RISK_PRIORITY constant
# ---------------------------------------------------------------------------


class TestRiskPriority:
    def test_critical_is_highest(self):
        assert RISK_PRIORITY[RiskLevel.CRITICAL] == 0

    def test_info_is_lowest(self):
        assert RISK_PRIORITY[RiskLevel.INFO] == 4

    def test_ordering(self):
        levels = [
            RiskLevel.CRITICAL,
            RiskLevel.HIGH,
            RiskLevel.MEDIUM,
            RiskLevel.LOW,
            RiskLevel.INFO,
        ]
        priorities = [RISK_PRIORITY[lvl] for lvl in levels]
        assert priorities == sorted(priorities)

    def test_all_levels_covered(self):
        for level in RiskLevel:
            assert level in RISK_PRIORITY


# ---------------------------------------------------------------------------
# detect_risks - routing
# ---------------------------------------------------------------------------


class TestDetectRisksRouting:
    def test_python_file_routed_to_python_analyzer(self, detector: RiskDetector):
        code = 'password = "secret123"\n'
        fc = _make_file_change(file_path="app.py", diff_content=code)
        risks = detector.detect_risks([fc])
        # Should find the hardcoded secret
        assert any("Hardcoded secret" in r.message for r in risks)

    def test_python_file_by_language_hint(self, detector: RiskDetector):
        code = 'password = "secret123"\n'
        fc = _make_file_change(
            file_path="noext", language="python", diff_content=code
        )
        risks = detector.detect_risks([fc])
        assert any("Hardcoded secret" in r.message for r in risks)

    def test_js_file_routed_to_js_analyzer(self, detector: RiskDetector):
        code = "const x = 1;\neval('alert(1)');\n"
        fc = _make_file_change(file_path="app.js", diff_content=code)
        risks = detector.detect_risks([fc])
        assert any("eval" in r.message.lower() for r in risks)

    def test_ts_file_routed_to_ts_analyzer(self, detector: RiskDetector):
        code = "const x = 1;\neval('alert(1)');\n"
        fc = _make_file_change(file_path="app.ts", diff_content=code)
        risks = detector.detect_risks([fc])
        assert any("eval" in r.message.lower() for r in risks)

    def test_tsx_file_routed_to_ts_analyzer(self, detector: RiskDetector):
        code = "const x = 1;\neval('alert(1)');\n"
        fc = _make_file_change(file_path="Component.tsx", diff_content=code)
        risks = detector.detect_risks([fc])
        assert any("eval" in r.message.lower() for r in risks)

    def test_unsupported_language_skipped(self, detector: RiskDetector):
        fc = _make_file_change(
            file_path="readme.txt", diff_content="some text"
        )
        risks = detector.detect_risks([fc])
        assert risks == []

    def test_no_diff_content_skipped(self, detector: RiskDetector):
        fc = _make_file_change(file_path="app.py", diff_content=None)
        risks = detector.detect_risks([fc])
        assert risks == []

    def test_empty_diff_content_skipped(self, detector: RiskDetector):
        fc = _make_file_change(file_path="app.py", diff_content="")
        risks = detector.detect_risks([fc])
        assert risks == []

    def test_file_path_set_on_risks(self, detector: RiskDetector):
        code = 'password = "secret123"\n'
        fc = _make_file_change(file_path="src/main.py", diff_content=code)
        risks = detector.detect_risks([fc])
        for risk in risks:
            assert risk.file_path == "src/main.py"


# ---------------------------------------------------------------------------
# detect_risks - mixed files
# ---------------------------------------------------------------------------


class TestDetectRisksMixed:
    def test_multiple_files(self, detector: RiskDetector):
        py_code = 'password = "secret123"\n'
        js_code = "const x = 1;\neval('alert(1)');\n"
        files = [
            _make_file_change(file_path="app.py", diff_content=py_code),
            _make_file_change(file_path="app.js", diff_content=js_code),
        ]
        risks = detector.detect_risks(files)
        assert len(risks) >= 2
        # Should have both Python and JS risks
        py_risks = [r for r in risks if r.file_path == "app.py"]
        js_risks = [r for r in risks if r.file_path == "app.js"]
        assert len(py_risks) >= 1
        assert len(js_risks) >= 1

    def test_results_sorted_by_priority(self, detector: RiskDetector):
        # Mix different risk levels
        py_code = 'password = "secret"\n'  # CRITICAL
        js_code = "var x = 1;\n"  # LOW
        files = [
            _make_file_change(file_path="app.py", diff_content=py_code),
            _make_file_change(file_path="app.js", diff_content=js_code),
        ]
        risks = detector.detect_risks(files)
        if len(risks) >= 2:
            for i in range(len(risks) - 1):
                assert RISK_PRIORITY[risks[i].level] <= RISK_PRIORITY[risks[i + 1].level]


# ---------------------------------------------------------------------------
# merge_risks
# ---------------------------------------------------------------------------


class TestMergeRisks:
    def test_empty_list(self, detector: RiskDetector):
        assert detector.merge_risks([]) == []

    def test_single_list(self, detector: RiskDetector):
        risks = [_make_risk(message="a")]
        result = detector.merge_risks([risks])
        assert len(result) == 1

    def test_multiple_lists(self, detector: RiskDetector):
        list1 = [_make_risk(message="a"), _make_risk(message="b")]
        list2 = [_make_risk(message="c")]
        list3 = [_make_risk(message="d"), _make_risk(message="e"), _make_risk(message="f")]
        result = detector.merge_risks([list1, list2, list3])
        assert len(result) == 6

    def test_preserves_order(self, detector: RiskDetector):
        r1 = _make_risk(message="first")
        r2 = _make_risk(message="second")
        result = detector.merge_risks([[r1], [r2]])
        assert result[0].message == "first"
        assert result[1].message == "second"

    def test_empty_inner_lists(self, detector: RiskDetector):
        result = detector.merge_risks([[], [_make_risk()], []])
        assert len(result) == 1


# ---------------------------------------------------------------------------
# deduplicate_risks
# ---------------------------------------------------------------------------


class TestDeduplicateRisks:
    def test_empty_list(self, detector: RiskDetector):
        assert detector.deduplicate_risks([]) == []

    def test_no_duplicates(self, detector: RiskDetector):
        risks = [
            _make_risk(message="a", file_path="a.py", line_number=1),
            _make_risk(message="b", file_path="a.py", line_number=2),
        ]
        result = detector.deduplicate_risks(risks)
        assert len(result) == 2

    def test_removes_exact_duplicates(self, detector: RiskDetector):
        risks = [
            _make_risk(message="same", file_path="a.py", line_number=1),
            _make_risk(message="same", file_path="a.py", line_number=1),
        ]
        result = detector.deduplicate_risks(risks)
        assert len(result) == 1

    def test_different_message_not_duplicate(self, detector: RiskDetector):
        risks = [
            _make_risk(message="msg1", file_path="a.py", line_number=1),
            _make_risk(message="msg2", file_path="a.py", line_number=1),
        ]
        result = detector.deduplicate_risks(risks)
        assert len(result) == 2

    def test_different_file_not_duplicate(self, detector: RiskDetector):
        risks = [
            _make_risk(message="same", file_path="a.py", line_number=1),
            _make_risk(message="same", file_path="b.py", line_number=1),
        ]
        result = detector.deduplicate_risks(risks)
        assert len(result) == 2

    def test_different_line_not_duplicate(self, detector: RiskDetector):
        risks = [
            _make_risk(message="same", file_path="a.py", line_number=1),
            _make_risk(message="same", file_path="a.py", line_number=2),
        ]
        result = detector.deduplicate_risks(risks)
        assert len(result) == 2

    def test_none_line_number_handled(self, detector: RiskDetector):
        risks = [
            _make_risk(message="same", file_path="a.py", line_number=None),
            _make_risk(message="same", file_path="a.py", line_number=None),
        ]
        result = detector.deduplicate_risks(risks)
        assert len(result) == 1

    def test_preserves_first_occurrence(self, detector: RiskDetector):
        r1 = _make_risk(
            message="same", file_path="a.py", line_number=1,
            suggestion="first",
        )
        r2 = _make_risk(
            message="same", file_path="a.py", line_number=1,
            suggestion="second",
        )
        result = detector.deduplicate_risks([r1, r2])
        assert len(result) == 1
        assert result[0].suggestion == "first"

    def test_complex_dedup_scenario(self, detector: RiskDetector):
        risks = [
            _make_risk(message="a", file_path="x.py", line_number=1),
            _make_risk(message="b", file_path="x.py", line_number=1),
            _make_risk(message="a", file_path="x.py", line_number=1),  # dup of first
            _make_risk(message="a", file_path="y.py", line_number=1),  # different file
            _make_risk(message="b", file_path="x.py", line_number=1),  # dup of second
        ]
        result = detector.deduplicate_risks(risks)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# sort_by_priority
# ---------------------------------------------------------------------------


class TestSortByPriority:
    def test_empty_list(self, detector: RiskDetector):
        assert detector.sort_by_priority([]) == []

    def test_already_sorted(self, detector: RiskDetector):
        risks = [
            _make_risk(level=RiskLevel.CRITICAL),
            _make_risk(level=RiskLevel.HIGH),
            _make_risk(level=RiskLevel.LOW),
        ]
        result = detector.sort_by_priority(risks)
        assert [r.level for r in result] == [
            RiskLevel.CRITICAL,
            RiskLevel.HIGH,
            RiskLevel.LOW,
        ]

    def test_reverse_order_sorted(self, detector: RiskDetector):
        risks = [
            _make_risk(level=RiskLevel.INFO),
            _make_risk(level=RiskLevel.LOW),
            _make_risk(level=RiskLevel.MEDIUM),
            _make_risk(level=RiskLevel.HIGH),
            _make_risk(level=RiskLevel.CRITICAL),
        ]
        result = detector.sort_by_priority(risks)
        assert [r.level for r in result] == [
            RiskLevel.CRITICAL,
            RiskLevel.HIGH,
            RiskLevel.MEDIUM,
            RiskLevel.LOW,
            RiskLevel.INFO,
        ]

    def test_same_level_preserved(self, detector: RiskDetector):
        r1 = _make_risk(level=RiskLevel.HIGH, message="first")
        r2 = _make_risk(level=RiskLevel.HIGH, message="second")
        result = detector.sort_by_priority([r1, r2])
        assert result[0].message == "first"
        assert result[1].message == "second"

    def test_does_not_mutate_input(self, detector: RiskDetector):
        risks = [
            _make_risk(level=RiskLevel.LOW),
            _make_risk(level=RiskLevel.CRITICAL),
        ]
        original_order = [r.level for r in risks]
        detector.sort_by_priority(risks)
        assert [r.level for r in risks] == original_order


# ---------------------------------------------------------------------------
# filter_by_category
# ---------------------------------------------------------------------------


class TestFilterByCategory:
    def test_empty_list(self, detector: RiskDetector):
        assert detector.filter_by_category([], RiskCategory.SECURITY) == []

    def test_filters_matching(self, detector: RiskDetector):
        risks = [
            _make_risk(category=RiskCategory.SECURITY),
            _make_risk(category=RiskCategory.LOGIC),
            _make_risk(category=RiskCategory.SECURITY),
        ]
        result = detector.filter_by_category(risks, RiskCategory.SECURITY)
        assert len(result) == 2
        assert all(r.category == RiskCategory.SECURITY for r in result)

    def test_no_matches(self, detector: RiskDetector):
        risks = [
            _make_risk(category=RiskCategory.LOGIC),
            _make_risk(category=RiskCategory.ARCHITECTURE),
        ]
        result = detector.filter_by_category(risks, RiskCategory.SECURITY)
        assert result == []

    def test_all_match(self, detector: RiskDetector):
        risks = [
            _make_risk(category=RiskCategory.ARCHITECTURE),
            _make_risk(category=RiskCategory.ARCHITECTURE),
        ]
        result = detector.filter_by_category(risks, RiskCategory.ARCHITECTURE)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# filter_by_level
# ---------------------------------------------------------------------------


class TestFilterByLevel:
    def test_empty_list(self, detector: RiskDetector):
        assert detector.filter_by_level([], RiskLevel.HIGH) == []

    def test_filters_matching(self, detector: RiskDetector):
        risks = [
            _make_risk(level=RiskLevel.CRITICAL),
            _make_risk(level=RiskLevel.HIGH),
            _make_risk(level=RiskLevel.CRITICAL),
        ]
        result = detector.filter_by_level(risks, RiskLevel.CRITICAL)
        assert len(result) == 2
        assert all(r.level == RiskLevel.CRITICAL for r in result)

    def test_no_matches(self, detector: RiskDetector):
        risks = [
            _make_risk(level=RiskLevel.LOW),
            _make_risk(level=RiskLevel.INFO),
        ]
        result = detector.filter_by_level(risks, RiskLevel.CRITICAL)
        assert result == []

    def test_all_match(self, detector: RiskDetector):
        risks = [
            _make_risk(level=RiskLevel.MEDIUM),
            _make_risk(level=RiskLevel.MEDIUM),
        ]
        result = detector.filter_by_level(risks, RiskLevel.MEDIUM)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Integration: end-to-end detect_risks
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_python_eval_detected(self, detector: RiskDetector):
        code = "result = eval(user_input)\n"
        fc = _make_file_change(file_path="danger.py", diff_content=code)
        risks = detector.detect_risks([fc])
        eval_risks = [r for r in risks if "eval" in r.message.lower()]
        assert len(eval_risks) >= 1
        assert eval_risks[0].level == RiskLevel.CRITICAL

    def test_js_innerhtml_detected(self, detector: RiskDetector):
        code = "el.innerHTML = userInput;\n"
        fc = _make_file_change(file_path="ui.js", diff_content=code)
        risks = detector.detect_risks([fc])
        assert any("innerHTML" in r.message for r in risks)

    def test_py_and_js_combined_dedup(self, detector: RiskDetector):
        # Same risk from two different files should not be deduped
        py_code = 'password = "secret"\n'
        js_code = "var x = 1;\n"
        files = [
            _make_file_change(file_path="a.py", diff_content=py_code),
            _make_file_change(file_path="b.js", diff_content=js_code),
        ]
        risks = detector.detect_risks(files)
        # Each file should contribute its own risks
        py_risks = [r for r in risks if r.file_path == "a.py"]
        js_risks = [r for r in risks if r.file_path == "b.js"]
        assert len(py_risks) >= 1
        assert len(js_risks) >= 1

    def test_detect_risks_returns_sorted_and_deduped(self, detector: RiskDetector):
        code = 'password = "secret"\napi_key = "key123"\n'
        fc = _make_file_change(file_path="config.py", diff_content=code)
        risks = detector.detect_risks([fc])
        # Should be sorted
        for i in range(len(risks) - 1):
            assert RISK_PRIORITY[risks[i].level] <= RISK_PRIORITY[risks[i + 1].level]
        # Should be deduped
        keys = {(r.file_path, r.line_number, r.message) for r in risks}
        assert len(keys) == len(risks)

    def test_language_alias_py(self, detector: RiskDetector):
        code = 'password = "secret123"\n'
        fc = _make_file_change(
            file_path="config", language="py", diff_content=code
        )
        risks = detector.detect_risks([fc])
        assert any("Hardcoded secret" in r.message for r in risks)

    def test_language_alias_js(self, detector: RiskDetector):
        code = "var x = 1;\n"
        fc = _make_file_change(
            file_path="config", language="js", diff_content=code
        )
        risks = detector.detect_risks([fc])
        assert any("var" in r.message for r in risks)

    def test_language_alias_ts(self, detector: RiskDetector):
        code = "var x = 1;\n"
        fc = _make_file_change(
            file_path="config", language="ts", diff_content=code
        )
        risks = detector.detect_risks([fc])
        assert any("var" in r.message for r in risks)


class TestUnsupportedLanguage:
    """Test behavior with unsupported languages."""

    def test_unsupported_language_returns_empty(self, detector: RiskDetector):
        """Unsupported languages should return empty list."""
        fc = _make_file_change(
            file_path="main.go", language="go", diff_content="package main\n"
        )
        risks = detector.detect_risks([fc])
        assert risks == []

    def test_none_language_returns_empty(self, detector: RiskDetector):
        """None language should return empty list."""
        fc = _make_file_change(
            file_path="unknown.xyz", language=None, diff_content="some code"
        )
        risks = detector.detect_risks([fc])
        assert risks == []
