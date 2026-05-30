"""Tests for performance optimization utilities."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import List
from unittest.mock import MagicMock

import pytest

from ai_code_reviewer.models import (
    ChangeType,
    FileChange,
    Risk,
    RiskCategory,
    RiskLevel,
)
from ai_code_reviewer.utils.performance import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_LARGE_PR_THRESHOLD,
    DEFAULT_MAX_WORKERS,
    BatchResult,
    PerformanceMetrics,
    analyze_files_concurrently,
    analyze_pr_optimized,
    batch_api_calls,
    get_optimal_batch_size,
    get_optimal_workers,
    is_large_pr,
    process_large_pr,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_file(path: str = "app.py", content: str = "x = 1\n") -> FileChange:
    """Create a sample FileChange."""
    return FileChange(
        file_path=path,
        change_type=ChangeType.FIX,
        diff_content=content,
    )


def _make_risk(
    message: str = "test risk",
    file_path: str = "app.py",
    level: RiskLevel = RiskLevel.MEDIUM,
) -> Risk:
    """Create a sample Risk."""
    return Risk(
        level=level,
        category=RiskCategory.LOGIC,
        message=message,
        file_path=file_path,
    )


def _simple_analyze(fc: FileChange) -> List[Risk]:
    """A trivial analyze function that returns one risk per file."""
    return [_make_risk(message=f"risk in {fc.file_path}", file_path=fc.file_path)]


def _failing_analyze(fc: FileChange) -> List[Risk]:
    """An analyze function that always raises."""
    raise RuntimeError(f"Analysis failed for {fc.file_path}")


def _slow_analyze(fc: FileChange) -> List[Risk]:
    """An analyze function that sleeps briefly (simulates work)."""
    time.sleep(0.05)
    return [_make_risk(message=f"slow risk in {fc.file_path}", file_path=fc.file_path)]


# ---------------------------------------------------------------------------
# analyze_files_concurrently
# ---------------------------------------------------------------------------


class TestAnalyzeFilesConcurrently:
    def test_empty_list(self):
        risks, errors = analyze_files_concurrently([], _simple_analyze)
        assert risks == []
        assert errors == {}

    def test_single_file(self):
        files = [_make_file("a.py")]
        risks, errors = analyze_files_concurrently(files, _simple_analyze)
        assert len(risks) == 1
        assert errors == {}

    def test_multiple_files(self):
        files = [_make_file(f"f{i}.py") for i in range(5)]
        risks, errors = analyze_files_concurrently(files, _simple_analyze)
        assert len(risks) == 5
        assert errors == {}

    def test_max_workers_capped(self):
        """max_workers should not exceed file count."""
        files = [_make_file(f"f{i}.py") for i in range(3)]
        # Just verify it doesn't crash with max_workers > file count
        risks, errors = analyze_files_concurrently(
            files, _simple_analyze, max_workers=10
        )
        assert len(risks) == 3

    def test_error_captured_per_file(self):
        files = [_make_file("good.py"), _make_file("bad.py")]
        # Make a function that fails only for "bad.py"
        def conditional_analyze(fc: FileChange) -> List[Risk]:
            if fc.file_path == "bad.py":
                raise ValueError("bad file")
            return [_make_risk(file_path=fc.file_path)]

        risks, errors = analyze_files_concurrently(files, conditional_analyze)
        assert len(risks) == 1
        assert "bad.py" in errors
        assert "bad file" in errors["bad.py"]

    def test_all_files_fail(self):
        files = [_make_file(f"f{i}.py") for i in range(3)]
        risks, errors = analyze_files_concurrently(files, _failing_analyze)
        assert risks == []
        assert len(errors) == 3

    def test_concurrent_execution(self):
        """Verify files are processed concurrently (not sequentially)."""
        files = [_make_file(f"f{i}.py") for i in range(4)]
        start = time.monotonic()
        risks, _ = analyze_files_concurrently(
            files, _slow_analyze, max_workers=4
        )
        elapsed = time.monotonic() - start
        # Sequential would take ~0.2s (4 * 0.05), concurrent should be ~0.05
        assert len(risks) == 4
        assert elapsed < 0.15  # generous margin


# ---------------------------------------------------------------------------
# batch_api_calls
# ---------------------------------------------------------------------------


class TestBatchApiCalls:
    def test_empty_list(self):
        risks, errors = batch_api_calls([], lambda batch: [])
        assert risks == []
        assert errors == {}

    def test_single_batch(self):
        items = [_make_file(f"f{i}.py") for i in range(3)]

        def process(batch: List[FileChange]) -> List[Risk]:
            return [_make_risk(file_path=fc.file_path) for fc in batch]

        risks, errors = batch_api_calls(items, process, batch_size=5)
        assert len(risks) == 3
        assert errors == {}

    def test_multiple_batches(self):
        items = [_make_file(f"f{i}.py") for i in range(7)]

        def process(batch: List[FileChange]) -> List[Risk]:
            return [_make_risk(file_path=fc.file_path) for fc in batch]

        risks, errors = batch_api_calls(items, process, batch_size=3)
        # 7 items / batch_size 3 = 3 batches (3+3+1)
        assert len(risks) == 7
        assert errors == {}

    def test_batch_error_does_not_stop_others(self):
        items = [_make_file(f"f{i}.py") for i in range(6)]
        call_count = [0]

        def process(batch: List[FileChange]) -> List[Risk]:
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("first batch fails")
            return [_make_risk(file_path=fc.file_path) for fc in batch]

        risks, errors = batch_api_calls(items, process, batch_size=3)
        # First batch (3 items) fails, second batch (3 items) succeeds
        assert len(risks) == 3
        assert "batch_0" in errors

    def test_exact_batch_size_boundary(self):
        items = [_make_file(f"f{i}.py") for i in range(10)]

        def process(batch: List[FileChange]) -> List[Risk]:
            return [_make_risk(file_path=fc.file_path) for fc in batch]

        risks, errors = batch_api_calls(items, process, batch_size=10)
        assert len(risks) == 10


# ---------------------------------------------------------------------------
# process_large_pr (generator)
# ---------------------------------------------------------------------------


class TestProcessLargePr:
    def test_yields_batch_results(self):
        files = [_make_file(f"f{i}.py") for i in range(5)]
        results = list(process_large_pr(files, _simple_analyze, batch_size=2))
        assert len(results) == 3  # 2+2+1
        assert all(isinstance(r, BatchResult) for r in results)

    def test_batch_index_sequential(self):
        files = [_make_file(f"f{i}.py") for i in range(6)]
        results = list(process_large_pr(files, _simple_analyze, batch_size=2))
        assert [r.batch_index for r in results] == [0, 1, 2]

    def test_files_processed_per_batch(self):
        files = [_make_file(f"f{i}.py") for i in range(7)]
        results = list(process_large_pr(files, _simple_analyze, batch_size=3))
        assert results[0].files_processed == 3
        assert results[1].files_processed == 3
        assert results[2].files_processed == 1

    def test_errors_captured(self):
        files = [_make_file("good.py"), _make_file("bad.py")]

        def conditional_analyze(fc: FileChange) -> List[Risk]:
            if fc.file_path == "bad.py":
                raise ValueError("bad file")
            return [_make_risk(file_path=fc.file_path)]

        results = list(
            process_large_pr(files, conditional_analyze, batch_size=2, max_workers=2)
        )
        assert len(results) == 1
        assert len(results[0].risks) == 1
        assert "bad.py" in results[0].errors

    def test_memory_efficient_streaming(self):
        """Verify generator yields one at a time (lazy evaluation)."""
        files = [_make_file(f"f{i}.py") for i in range(10)]
        gen = process_large_pr(files, _simple_analyze, batch_size=3)

        first = next(gen)
        assert first.batch_index == 0
        assert first.files_processed == 3

        second = next(gen)
        assert second.batch_index == 1


# ---------------------------------------------------------------------------
# is_large_pr
# ---------------------------------------------------------------------------


class TestIsLargePr:
    def test_small_pr(self):
        files = [_make_file(f"f{i}.py") for i in range(10)]
        assert is_large_pr(files, threshold=50) is False

    def test_exact_threshold(self):
        files = [_make_file(f"f{i}.py") for i in range(50)]
        assert is_large_pr(files, threshold=50) is False

    def test_above_threshold(self):
        files = [_make_file(f"f{i}.py") for i in range(51)]
        assert is_large_pr(files, threshold=50) is True

    def test_custom_threshold(self):
        files = [_make_file(f"f{i}.py") for i in range(5)]
        assert is_large_pr(files, threshold=3) is True
        assert is_large_pr(files, threshold=5) is False

    def test_empty_list(self):
        assert is_large_pr([], threshold=50) is False


# ---------------------------------------------------------------------------
# get_optimal_batch_size
# ---------------------------------------------------------------------------


class TestGetOptimalBatchSize:
    def test_small_file_count(self):
        assert get_optimal_batch_size(5) == 5

    def test_boundary_ten(self):
        assert get_optimal_batch_size(10) == 10

    def test_medium_file_count(self):
        assert get_optimal_batch_size(30) == DEFAULT_BATCH_SIZE

    def test_large_file_count(self):
        # 100 files -> max(5, 100//10) = 10
        assert get_optimal_batch_size(100) == 10

    def test_very_large_file_count(self):
        # 200 files -> max(5, 200//10) = 20
        assert get_optimal_batch_size(200) == 20

    def test_minimum_batch_size(self):
        # Even for very large counts, batch_size >= 5
        assert get_optimal_batch_size(1000) >= 5


# ---------------------------------------------------------------------------
# get_optimal_workers
# ---------------------------------------------------------------------------


class TestGetOptimalWorkers:
    def test_small_file_count(self):
        assert get_optimal_workers(3) == 3

    def test_boundary_five(self):
        assert get_optimal_workers(5) == 5

    def test_large_file_count(self):
        assert get_optimal_workers(100) == DEFAULT_MAX_WORKERS

    def test_single_file(self):
        assert get_optimal_workers(1) == 1


# ---------------------------------------------------------------------------
# BatchResult and PerformanceMetrics dataclasses
# ---------------------------------------------------------------------------


class TestDataclasses:
    def test_batch_result_defaults(self):
        br = BatchResult(batch_index=0)
        assert br.risks == []
        assert br.files_processed == 0
        assert br.errors == {}

    def test_performance_metrics_defaults(self):
        pm = PerformanceMetrics()
        assert pm.total_files == 0
        assert pm.total_batches == 0
        assert pm.concurrent_tasks == 0
        assert pm.errors == 0


# ---------------------------------------------------------------------------
# analyze_pr_optimized (orchestrator)
# ---------------------------------------------------------------------------


class TestAnalyzePrOptimized:
    def test_empty_files(self):
        risks, errors, metrics = analyze_pr_optimized([], _simple_analyze)
        assert risks == []
        assert errors == {}
        assert metrics.total_files == 0

    def test_small_pr_uses_concurrent(self):
        files = [_make_file(f"f{i}.py") for i in range(5)]
        risks, errors, metrics = analyze_pr_optimized(files, _simple_analyze)
        assert len(risks) == 5
        assert errors == {}
        assert metrics.total_files == 5
        assert metrics.total_batches == 1

    def test_large_pr_uses_batched(self):
        files = [_make_file(f"f{i}.py") for i in range(60)]
        risks, errors, metrics = analyze_pr_optimized(
            files, _simple_analyze, batch_size=10
        )
        assert len(risks) == 60
        assert errors == {}
        assert metrics.total_files == 60
        assert metrics.total_batches > 1

    def test_errors_tracked_in_metrics(self):
        files = [_make_file(f"f{i}.py") for i in range(3)]

        def partial_fail(fc: FileChange) -> List[Risk]:
            if fc.file_path == "f1.py":
                raise RuntimeError("fail")
            return [_make_risk(file_path=fc.file_path)]

        risks, errors, metrics = analyze_pr_optimized(files, partial_fail)
        assert len(risks) == 2
        assert "f1.py" in errors
        assert metrics.errors == 1

    def test_custom_overrides(self):
        files = [_make_file(f"f{i}.py") for i in range(3)]
        risks, errors, metrics = analyze_pr_optimized(
            files, _simple_analyze, batch_size=2, max_workers=2
        )
        assert len(risks) == 3

    def test_large_pr_errors_in_metrics(self):
        """Errors from batched processing count in metrics."""
        files = [_make_file(f"f{i}.py") for i in range(60)]

        def partial_fail(fc: FileChange) -> List[Risk]:
            if "f0" in fc.file_path or "f1" in fc.file_path:
                raise RuntimeError("fail")
            return [_make_risk(file_path=fc.file_path)]

        risks, errors, metrics = analyze_pr_optimized(
            files, partial_fail, batch_size=10
        )
        assert metrics.errors > 0
        assert len(errors) > 0
