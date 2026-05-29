"""JavaScript/TypeScript code analyzer for risk detection."""

from pathlib import Path
from typing import List

from ai_code_reviewer.analyzer.ast_parser import ASTParser
from ai_code_reviewer.models import Risk, RiskCategory, RiskLevel


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_LONG_FUNCTION_THRESHOLD = 50  # lines
_DEEP_NESTING_THRESHOLD = 4  # levels
_CALLBACK_HELL_THRESHOLD = 3  # nested callbacks


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------


class JSTSAnalyzer:
    """Analyzes JavaScript/TypeScript code for security, logic, and architecture risks.

    Uses the ASTParser to parse code into a tree-sitter AST dict and then
    walks the tree to identify risk patterns.
    """

    def __init__(self) -> None:
        self._parser = ASTParser()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_file(self, file_path: str) -> List[Risk]:
        """Analyze a JavaScript/TypeScript file and return identified risks.

        Args:
            file_path: Path to the source file.

        Returns:
            List of Risk instances found in the file.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file extension is not JS/TS.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        language = self._parser.detect_language(file_path)
        if language not in ("javascript", "typescript"):
            raise ValueError(
                f"JSTSAnalyzer only supports JavaScript/TypeScript, got {language!r}"
            )

        code = path.read_text(encoding="utf-8")
        return self.analyze_code(code, language, file_path=file_path)

    def analyze_code(
        self,
        code: str,
        language: str,
        file_path: str = "<string>",
    ) -> List[Risk]:
        """Analyze a code string and return identified risks.

        Args:
            code: Source code to analyze.
            language: "javascript" or "typescript".
            file_path: Optional file path for risk messages.

        Returns:
            List of Risk instances found in the code.
        """
        lang = language.lower()
        if lang not in ("javascript", "typescript"):
            raise ValueError(
                f"JSTSAnalyzer only supports JavaScript/TypeScript, got {language!r}"
            )

        try:
            tree = self._parser.parse_code(code, lang)
        except Exception:
            # If parsing fails completely, return no risks (caller should
            # handle syntax errors at a higher level if needed).
            return []

        risks: List[Risk] = []
        risks.extend(self.detect_security_risks(tree, file_path=file_path))
        risks.extend(self.detect_logic_risks(code, tree, file_path=file_path))
        risks.extend(self.detect_architecture_risks(tree, file_path=file_path))
        return risks

    # ------------------------------------------------------------------
    # Security risks
    # ------------------------------------------------------------------

    def detect_security_risks(
        self, tree: dict, file_path: str = "<string>"
    ) -> List[Risk]:
        """Detect security risks in a parsed AST.

        Checks for:
        - innerHTML direct DOM manipulation
        - eval() usage
        - dangerouslySetInnerHTML (React XSS)
        - document.write() usage

        Args:
            tree: Parsed AST dict from ASTParser.
            file_path: File path for risk messages.

        Returns:
            List of security-related Risk instances.
        """
        risks: List[Risk] = []
        self._walk_security(tree, risks, file_path)
        return risks

    # ------------------------------------------------------------------
    # Logic risks
    # ------------------------------------------------------------------

    def detect_logic_risks(
        self,
        code: str,
        tree: dict,
        file_path: str = "<string>",
    ) -> List[Risk]:
        """Detect logic risks in source code and its AST.

        Checks for:
        - ``==`` / ``!=`` loose equality (should use ``===`` / ``!==``)
        - ``var`` declarations (should use ``let``/``const``)

        Args:
            code: Original source code (for regex-based checks).
            tree: Parsed AST dict from ASTParser.
            file_path: File path for risk messages.

        Returns:
            List of logic-related Risk instances.
        """
        risks: List[Risk] = []
        self._check_loose_equality(code, risks, file_path)
        self._check_var_usage(code, risks, file_path)
        return risks

    # ------------------------------------------------------------------
    # Architecture risks
    # ------------------------------------------------------------------

    def detect_architecture_risks(
        self, tree: dict, file_path: str = "<string>"
    ) -> List[Risk]:
        """Detect architecture risks in a parsed AST.

        Checks for:
        - Long functions (> 50 lines)
        - Deep nesting (> 4 levels)
        - Callback hell (nested callbacks > 3 levels)

        Args:
            tree: Parsed AST dict from ASTParser.
            file_path: File path for risk messages.

        Returns:
            List of architecture-related Risk instances.
        """
        risks: List[Risk] = []
        functions = self._parser.extract_functions(tree)
        for func in functions:
            self._check_long_function(func, risks, file_path)
        self._check_deep_nesting(tree, risks, file_path, depth=0)
        self._check_callback_hell(tree, risks, file_path, depth=0)
        return risks

    # ==================================================================
    # Internal helpers — Security
    # ==================================================================

    def _walk_security(
        self, node: dict, risks: List[Risk], file_path: str
    ) -> None:
        """Recursively walk the AST looking for security patterns."""
        node_type = node.get("type", "")
        text = node.get("text", "")
        line = node.get("start_line")

        # innerHTML assignment:  someElement.innerHTML = ...
        if node_type == "assignment_expression" and "innerHTML" in text:
            risks.append(
                Risk(
                    level=RiskLevel.HIGH,
                    category=RiskCategory.SECURITY,
                    message="Direct innerHTML assignment may lead to XSS vulnerabilities.",
                    file_path=file_path,
                    line_number=line,
                    suggestion="Use textContent or a sanitization library (e.g., DOMPurify) instead of innerHTML.",
                )
            )

        # dangerouslySetInnerHTML prop (React)
        if "dangerouslySetInnerHTML" in text:
            risks.append(
                Risk(
                    level=RiskLevel.HIGH,
                    category=RiskCategory.SECURITY,
                    message="dangerouslySetInnerHTML can introduce XSS if input is not sanitized.",
                    file_path=file_path,
                    line_number=line,
                    suggestion="Sanitize HTML with a library like DOMPurify before passing to dangerouslySetInnerHTML.",
                )
            )

        # eval() calls
        if node_type == "call_expression":
            # The first child of a call_expression is the function being called
            children = node.get("children", [])
            if children and children[0].get("text") == "eval":
                risks.append(
                    Risk(
                        level=RiskLevel.CRITICAL,
                        category=RiskCategory.SECURITY,
                        message="Use of eval() is dangerous and can execute arbitrary code.",
                        file_path=file_path,
                        line_number=line,
                        suggestion="Avoid eval(). Use safer alternatives like JSON.parse() for data, or Function constructor if absolutely necessary.",
                    )
                )

        # document.write()
        if node_type == "call_expression" and "document.write" in text:
            risks.append(
                Risk(
                    level=RiskLevel.HIGH,
                    category=RiskCategory.SECURITY,
                    message="document.write() can lead to XSS and is discouraged.",
                    file_path=file_path,
                    line_number=line,
                    suggestion="Use DOM manipulation methods (createElement, appendChild) instead of document.write().",
                )
            )

        # Recurse
        for child in node.get("children", []):
            self._walk_security(child, risks, file_path)

    # ==================================================================
    # Internal helpers — Logic
    # ==================================================================

    @staticmethod
    def _check_loose_equality(
        code: str, risks: List[Risk], file_path: str
    ) -> None:
        """Check for ``==`` and ``!=`` (should use strict equality)."""
        import re

        # Match == or != but not === or !==
        pattern = re.compile(r"(?<![!=])[!=]=(?!=)")
        for i, line_text in enumerate(code.splitlines(), start=1):
            if pattern.search(line_text):
                risks.append(
                    Risk(
                        level=RiskLevel.LOW,
                        category=RiskCategory.LOGIC,
                        message="Loose equality (== or !=) used; prefer strict equality (=== or !==).",
                        file_path=file_path,
                        line_number=i,
                        suggestion="Replace == with === and != with !== to avoid type coercion bugs.",
                    )
                )

    @staticmethod
    def _check_var_usage(
        code: str, risks: List[Risk], file_path: str
    ) -> None:
        """Check for ``var`` declarations (should use ``let``/``const``)."""
        import re

        pattern = re.compile(r"\bvar\s+")
        for i, line_text in enumerate(code.splitlines(), start=1):
            stripped = line_text.lstrip()
            if pattern.match(stripped):
                risks.append(
                    Risk(
                        level=RiskLevel.LOW,
                        category=RiskCategory.LOGIC,
                        message="'var' is function-scoped and can cause unexpected hoisting; prefer 'let' or 'const'.",
                        file_path=file_path,
                        line_number=i,
                        suggestion="Replace 'var' with 'const' for values that don't change, or 'let' for mutable bindings.",
                    )
                )

    # ==================================================================
    # Internal helpers — Architecture
    # ==================================================================

    @staticmethod
    def _check_long_function(
        func: dict, risks: List[Risk], file_path: str
    ) -> None:
        """Flag functions exceeding the line-count threshold."""
        line_count = func["end_line"] - func["start_line"] + 1
        if line_count > _LONG_FUNCTION_THRESHOLD:
            risks.append(
                Risk(
                    level=RiskLevel.MEDIUM,
                    category=RiskCategory.ARCHITECTURE,
                    message=(
                        f"Function '{func.get('name', '<anonymous>')}' is {line_count} lines long "
                        f"(threshold: {_LONG_FUNCTION_THRESHOLD})."
                    ),
                    file_path=file_path,
                    line_number=func["start_line"],
                    suggestion="Break this function into smaller, focused functions.",
                )
            )

    def _check_deep_nesting(
        self, node: dict, risks: List[Risk], file_path: str, depth: int
    ) -> None:
        """Detect deeply nested control-flow blocks."""
        nesting_types = {
            "if_statement",
            "for_statement",
            "for_in_statement",
            "while_statement",
            "do_statement",
            "try_statement",
            "switch_statement",
        }

        node_type = node.get("type", "")
        new_depth = depth + 1 if node_type in nesting_types else depth

        if new_depth > _DEEP_NESTING_THRESHOLD:
            risks.append(
                Risk(
                    level=RiskLevel.MEDIUM,
                    category=RiskCategory.ARCHITECTURE,
                    message=f"Nesting depth of {new_depth} exceeds threshold ({_DEEP_NESTING_THRESHOLD}).",
                    file_path=file_path,
                    line_number=node.get("start_line"),
                    suggestion="Refactor using early returns, guard clauses, or extract helper functions to reduce nesting.",
                )
            )

        for child in node.get("children", []):
            self._check_deep_nesting(child, risks, file_path, new_depth)

    def _check_callback_hell(
        self, node: dict, risks: List[Risk], file_path: str, depth: int
    ) -> None:
        """Detect callback hell: deeply nested function expressions / arrow functions."""
        callback_types = {
            "arrow_function",
            "function_expression",
        }

        node_type = node.get("type", "")
        new_depth = depth + 1 if node_type in callback_types else depth

        if new_depth > _CALLBACK_HELL_THRESHOLD:
            risks.append(
                Risk(
                    level=RiskLevel.MEDIUM,
                    category=RiskCategory.ARCHITECTURE,
                    message=f"Callback nesting depth of {new_depth} exceeds threshold ({_CALLBACK_HELL_THRESHOLD}).",
                    file_path=file_path,
                    line_number=node.get("start_line"),
                    suggestion="Refactor callbacks to use async/await, Promises, or extract named functions.",
                )
            )

        for child in node.get("children", []):
            self._check_callback_hell(child, risks, file_path, new_depth)
