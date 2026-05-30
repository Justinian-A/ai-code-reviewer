"""Performance optimization utilities for large pull request analysis.

Provides concurrent file analysis, API call batching, and memory-efficient
processing for PRs with many file changes.
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Generator, List, TypeVar

from ai_code_reviewer.models import FileChange, Risk

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Default thresholds
DEFAULT_MAX_WORKERS = 5
DEFAULT_BATCH_SIZE = 10
DEFAULT_LARGE_PR_THRESHOLD = 50


@dataclass
class BatchResult:
    """Result of processing a single batch of files.

    Attributes:
        batch_index: Zero-based index of this batch.
        risks: Risks detected in this batch.
        files_processed: Number of files in this batch.
        errors: Mapping of file_path to error message for failed files.
    """

    batch_index: int
    risks: List[Risk] = field(default_factory=list)
    files_processed: int = 0
    errors: dict[str, str] = field(default_factory=dict)


@dataclass
class PerformanceMetrics:
    """Tracks performance metrics during analysis.

    Attributes:
        total_files: Total number of files processed.
        total_batches: Number of batches used.
        concurrent_tasks: Number of concurrent tasks launched.
        errors: Total number of file-level errors.
    """

    total_files: int = 0
    total_batches: int = 0
    concurrent_tasks: int = 0
    errors: int = 0


# ---------------------------------------------------------------------------
# Concurrent file analysis
# ---------------------------------------------------------------------------


def analyze_files_concurrently(
    files: List[FileChange],
    analyze_fn: Callable[[FileChange], List[Risk]],
    max_workers: int = DEFAULT_MAX_WORKERS,
) -> tuple[List[Risk], dict[str, str]]:
    """Analyze multiple files concurrently using a thread pool.

    Each file is submitted to the thread pool as an independent task.
    Files that fail are logged and recorded but do not abort the batch.

    Args:
        files: List of FileChange objects to analyze.
        analyze_fn: Callable that accepts a FileChange and returns a list of
            risks. This should be a thread-safe function.
        max_workers: Maximum number of concurrent threads. Defaults to 5.

    Returns:
        A tuple of (all_risks, errors) where all_risks is a flat list of
        detected risks and errors maps file_path to the error message for
        files that failed analysis.
    """
    if not files:
        return [], {}

    all_risks: List[Risk] = []
    errors: dict[str, str] = {}
    workers = min(max_workers, len(files))

    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_file = {
            executor.submit(analyze_fn, file_change): file_change
            for file_change in files
        }

        for future in as_completed(future_to_file):
            file_change = future_to_file[future]
            try:
                risks = future.result()
                all_risks.extend(risks)
            except Exception as exc:
                file_path = file_change.file_path
                errors[file_path] = str(exc)
                logger.warning(
                    "Concurrent analysis failed for %s: %s",
                    file_path,
                    exc,
                )

    return all_risks, errors


# ---------------------------------------------------------------------------
# API call batching
# ---------------------------------------------------------------------------


def batch_api_calls(
    items: List[T],
    process_fn: Callable[[List[T]], List[Risk]],
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> tuple[List[Risk], dict[str, str]]:
    """Batch multiple items into groups and process each group via a single API call.

    This reduces the number of API round-trips when analyzing many files.
    Each batch is processed independently; failures in one batch do not
    prevent subsequent batches from running.

    Args:
        items: List of items to process (e.g. FileChange objects).
        process_fn: Callable that accepts a batch (list of items) and returns
            a list of risks detected across the batch.
        batch_size: Number of items per batch. Defaults to 10.

    Returns:
        A tuple of (all_risks, errors) where all_risks is a flat list of
        detected risks and errors maps a batch identifier to the error message.
    """
    if not items:
        return [], {}

    all_risks: List[Risk] = []
    errors: dict[str, str] = {}

    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]
        batch_id = f"batch_{i // batch_size}"
        try:
            batch_risks = process_fn(batch)
            all_risks.extend(batch_risks)
        except Exception as exc:
            errors[batch_id] = str(exc)
            logger.warning("Batch %s failed: %s", batch_id, exc)

    return all_risks, errors


# ---------------------------------------------------------------------------
# Memory-efficient large PR processing
# ---------------------------------------------------------------------------


def process_large_pr(
    files: List[FileChange],
    analyze_fn: Callable[[FileChange], List[Risk]],
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_workers: int = DEFAULT_MAX_WORKERS,
) -> Generator[BatchResult, None, None]:
    """Process a large PR in memory-efficient batches using a generator.

    Yields BatchResult objects one at a time so the caller can stream
    results without holding every risk in memory simultaneously.

    Each batch is analyzed concurrently within the batch, but batches
    are processed sequentially to limit peak memory usage.

    Args:
        files: List of FileChange objects to analyze.
        analyze_fn: Callable that accepts a FileChange and returns a list of
            risks.
        batch_size: Number of files per batch. Defaults to 10.
        max_workers: Number of threads per batch. Defaults to 5.

    Yields:
        BatchResult for each batch of files processed.
    """
    for batch_idx, i in enumerate(range(0, len(files), batch_size)):
        batch = files[i : i + batch_size]

        batch_risks: List[Risk] = []
        batch_errors: dict[str, str] = {}

        workers = min(max_workers, len(batch))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_file = {
                executor.submit(analyze_fn, fc): fc for fc in batch
            }

            for future in as_completed(future_to_file):
                fc = future_to_file[future]
                try:
                    risks = future.result()
                    batch_risks.extend(risks)
                except Exception as exc:
                    batch_errors[fc.file_path] = str(exc)
                    logger.warning(
                        "Analysis failed for %s in batch %d: %s",
                        fc.file_path,
                        batch_idx,
                        exc,
                    )

        yield BatchResult(
            batch_index=batch_idx,
            risks=batch_risks,
            files_processed=len(batch),
            errors=batch_errors,
        )


# ---------------------------------------------------------------------------
# Large PR detection and strategy selection
# ---------------------------------------------------------------------------


def is_large_pr(
    files: List[FileChange],
    threshold: int = DEFAULT_LARGE_PR_THRESHOLD,
) -> bool:
    """Determine whether a PR qualifies as a large PR.

    Args:
        files: List of FileChange objects in the PR.
        threshold: File count above which a PR is considered large.
            Defaults to 50.

    Returns:
        True if the number of files exceeds the threshold.
    """
    return len(files) > threshold


def get_optimal_batch_size(file_count: int) -> int:
    """Calculate an optimal batch size based on total file count.

    Uses a simple heuristic:
    - <= 10 files: process all at once (batch_size = file_count)
    - <= 50 files: batch_size = 10
    - > 50 files: batch_size = max(5, file_count // 10)

    Args:
        file_count: Total number of files in the PR.

    Returns:
        Recommended batch size.
    """
    if file_count <= 10:
        return file_count
    if file_count <= 50:
        return DEFAULT_BATCH_SIZE
    return max(5, file_count // 10)


def get_optimal_workers(file_count: int) -> int:
    """Calculate optimal worker count based on total file count.

    Args:
        file_count: Total number of files in the PR.

    Returns:
        Recommended max_workers value.
    """
    if file_count <= 5:
        return file_count
    return min(DEFAULT_MAX_WORKERS, file_count)


# ---------------------------------------------------------------------------
# High-level orchestrator
# ---------------------------------------------------------------------------


def analyze_pr_optimized(
    files: List[FileChange],
    analyze_fn: Callable[[FileChange], List[Risk]],
    batch_size: int | None = None,
    max_workers: int | None = None,
) -> tuple[List[Risk], dict[str, str], PerformanceMetrics]:
    """Analyze a PR using the optimal strategy based on file count.

    Automatically selects between:
    - Concurrent-only (small PRs): all files processed in one concurrent batch.
    - Batched + concurrent (large PRs): files split into batches, each batch
      analyzed concurrently, yielded one at a time for memory efficiency.

    Args:
        files: List of FileChange objects in the PR.
        analyze_fn: Callable that accepts a FileChange and returns a list of
            risks.
        batch_size: Override for batch size. If None, uses heuristic.
        max_workers: Override for max workers. If None, uses heuristic.

    Returns:
        A tuple of (all_risks, all_errors, metrics).
    """
    if not files:
        return [], {}, PerformanceMetrics()

    file_count = len(files)
    effective_batch_size = batch_size or get_optimal_batch_size(file_count)
    effective_workers = max_workers or get_optimal_workers(file_count)

    all_risks: List[Risk] = []
    all_errors: dict[str, str] = {}
    metrics = PerformanceMetrics(total_files=file_count)

    if is_large_pr(files, threshold=effective_batch_size):
        # Large PR: batched + concurrent
        metrics.total_batches = 0
        for batch_result in process_large_pr(
            files,
            analyze_fn,
            batch_size=effective_batch_size,
            max_workers=effective_workers,
        ):
            all_risks.extend(batch_result.risks)
            all_errors.update(batch_result.errors)
            metrics.total_batches += 1
            metrics.concurrent_tasks += batch_result.files_processed
            metrics.errors += len(batch_result.errors)
    else:
        # Small PR: fully concurrent
        risks, errors = analyze_files_concurrently(
            files, analyze_fn, max_workers=effective_workers
        )
        all_risks.extend(risks)
        all_errors.update(errors)
        metrics.total_batches = 1
        metrics.concurrent_tasks = file_count
        metrics.errors = len(errors)

    return all_risks, all_errors, metrics
