"""Hybrid analyzer combining AST and AI-based code analysis."""

import logging
from typing import List

from ai_code_reviewer.ai.client import AIClient
from ai_code_reviewer.analyzer.ast_parser import ASTParser
from ai_code_reviewer.analyzer.js_ts_analyzer import JSTSAnalyzer
from ai_code_reviewer.analyzer.python_analyzer import PythonAnalyzer
from ai_code_reviewer.analyzer.review_generator import ReviewGenerator
from ai_code_reviewer.analyzer.risk_detector import RiskDetector
from ai_code_reviewer.analyzer.summary_generator import SummaryGenerator
from ai_code_reviewer.config import Config
from ai_code_reviewer.models import (
    AnalysisResult,
    CostReport,
    FileChange,
    PullRequest,
    Risk,
    ReviewSuggestion,
)

logger = logging.getLogger(__name__)


class HybridAnalyzer:
    """Coordinates AST-based and AI-based code analysis.

    Integrates multiple analysis components to produce a unified code review:
    - ASTParser / PythonAnalyzer / JSTSAnalyzer for static analysis
    - RiskDetector for risk aggregation and deduplication
    - SummaryGenerator for change summaries
    - ReviewGenerator for actionable suggestions
    - AIClient for LLM-powered semantic analysis (optional)

    Args:
        config: Application configuration controlling analysis behavior.
    """

    def __init__(self, config: Config) -> None:
        """Initialize all analysis sub-components from config.

        Args:
            config: Config instance with analysis, AI, and output settings.
        """
        self.config = config

        # AST components
        self.ast_parser = ASTParser()
        self.python_analyzer = PythonAnalyzer()
        self.js_ts_analyzer = JSTSAnalyzer()

        # Aggregation / generation components
        self.risk_detector = RiskDetector()
        self.summary_generator = SummaryGenerator()
        self.review_generator = ReviewGenerator()

        # AI client (created only when AI is enabled and API key is available)
        self._ai_client: AIClient | None = None
        if config.analysis.enable_ai and config.ai.api_key:
            self._ai_client = AIClient(
                provider=config.ai.provider.value,
                api_key=config.ai.api_key,
                model=config.ai.model,
                max_tokens=config.ai.max_tokens,
            )

    @property
    def ai_client(self) -> AIClient | None:
        """Return the AI client, or None if AI analysis is disabled."""
        return self._ai_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_pr(
        self, pr: PullRequest, files: List[FileChange]
    ) -> AnalysisResult:
        """Analyze a pull request using both AST and AI analysis.

        Flow:
        1. Generate a change summary.
        2. Detect risks via AST analyzers (PythonAnalyzer, JSTSAnalyzer).
        3. Detect risks via AI client (if enabled).
        4. Merge, deduplicate, and sort all risks.
        5. Generate review suggestions.
        6. Build and return the final AnalysisResult.

        Args:
            pr: Pull request metadata.
            files: List of file changes in the PR.

        Returns:
            Complete AnalysisResult with risks, suggestions, summary, and cost.
        """
        # 1. Generate summary
        summary = self.summary_generator.generate_summary(pr, files)

        # 2. AST-based risk detection
        ast_risks: List[Risk] = []
        if self.config.analysis.enable_ast:
            ast_risks = self.risk_detector.detect_risks(files)

        # 3. AI-based risk detection (if enabled)
        ai_risks: List[Risk] = []
        if self._ai_client is not None:
            for file in files:
                if file.diff_content:
                    try:
                        detected = self._ai_client.detect_issues(file.diff_content)
                        for risk in detected:
                            risk.file_path = file.file_path
                        ai_risks.extend(detected)
                    except Exception:
                        logger.warning(
                            "AI analysis failed for %s, skipping",
                            file.file_path,
                            exc_info=True,
                        )

        # 4. Merge, deduplicate, sort
        all_risks = self.merge_results(ast_risks, ai_risks)

        # 5. Generate suggestions
        suggestions = self.review_generator.generate_suggestions(all_risks)

        # 6. Build report
        return self.generate_report(pr, all_risks, suggestions, summary)

    def analyze_file(self, file: FileChange) -> List[Risk]:
        """Analyze a single file change using both AST and AI analysis.

        Args:
            file: FileChange to analyze.

        Returns:
            Deduplicated, priority-sorted list of risks found in the file.
        """
        ast_risks: List[Risk] = []
        ai_risks: List[Risk] = []

        # AST analysis
        if self.config.analysis.enable_ast:
            file_risks = self.risk_detector._analyze_single_file(file)
            ast_risks.extend(file_risks)

        # AI analysis
        if self._ai_client is not None and file.diff_content:
            try:
                detected = self._ai_client.detect_issues(file.diff_content)
                for risk in detected:
                    risk.file_path = file.file_path
                ai_risks.extend(detected)
            except Exception:
                logger.warning(
                    "AI analysis failed for %s, skipping",
                    file.file_path,
                    exc_info=True,
                )

        return self.merge_results(ast_risks, ai_risks)

    def merge_results(
        self, ast_risks: List[Risk], ai_risks: List[Risk]
    ) -> List[Risk]:
        """Merge AST and AI risk lists, deduplicate, and sort by priority.

        Args:
            ast_risks: Risks detected by AST-based analyzers.
            ai_risks: Risks detected by AI analysis.

        Returns:
            Deduplicated, priority-sorted list of risks.
        """
        merged = self.risk_detector.merge_risks([ast_risks, ai_risks])
        deduplicated = self.risk_detector.deduplicate_risks(merged)
        return self.risk_detector.sort_by_priority(deduplicated)

    def generate_report(
        self,
        pr: PullRequest,
        risks: List[Risk],
        suggestions: List[ReviewSuggestion],
        summary: str | None = None,
    ) -> AnalysisResult:
        """Generate a complete analysis report.

        Args:
            pr: Pull request metadata.
            risks: Final list of deduplicated, sorted risks.
            suggestions: Review suggestions generated from risks.
            summary: Optional pre-generated summary string.

        Returns:
            AnalysisResult containing all analysis artifacts.
        """
        cost: CostReport | None = None
        if self._ai_client is not None:
            cost = self._ai_client.cost_report

        return AnalysisResult(
            pr=pr,
            risks=risks,
            suggestions=suggestions,
            cost=cost,
            summary=summary,
        )
