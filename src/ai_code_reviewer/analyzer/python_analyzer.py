"""Python code analyzer for detecting security, logic, and architecture risks."""

import re
from typing import List, Set

from ai_code_reviewer.analyzer.ast_parser import ASTParser
from ai_code_reviewer.models import Risk, RiskCategory, RiskLevel


# Patterns for detecting hardcoded secrets
_SECRET_PATTERNS = [
    re.compile(r"(?i)(password|passwd|pwd)"),
    re.compile(r"(?i)(secret|secret_key)"),
    re.compile(r"(?i)(api_key|apikey|api_token)"),
    re.compile(r"(?i)(access_key|access_token)"),
    re.compile(r"(?i)(private_key|priv_key)"),
    re.compile(r"(?i)(auth_token|authentication_token)"),
]

# SQL keywords that indicate SQL injection risk
_SQL_KEYWORDS = frozenset({
    "SELECT", "INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER",
    "WHERE", "FROM", "JOIN", "SET", "VALUES", "INTO", "TABLE",
})

# Mutable default argument types
_MUTABLE_TYPES = frozenset({"list", "dictionary", "set"})

# Node types that increase nesting depth
_NESTING_TYPES = frozenset({
    "if_statement", "for_statement", "while_statement",
    "try_statement", "with_statement",
})


class PythonAnalyzer:
    """Python code analyzer for detecting security, logic, and architecture risks.

    Uses tree-sitter AST parsing to identify various risk patterns in Python code
    including security vulnerabilities, logic errors, and architectural issues.
    """

    def __init__(self) -> None:
        """Initialize the PythonAnalyzer."""
        self._parser = ASTParser()

    def analyze_file(self, file_path: str) -> List[Risk]:
        """Analyze a Python file for risks.

        Args:
            file_path: Path to the Python file to analyze.

        Returns:
            List of detected risks.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file extension is not Python.
        """
        tree = self._parser.parse_file(file_path)
        risks = self._analyze_tree(tree)
        for risk in risks:
            risk.file_path = file_path
        return risks

    def analyze_code(self, code: str) -> List[Risk]:
        """Analyze a Python code string for risks.

        Args:
            code: Python source code string to analyze.

        Returns:
            List of detected risks.
        """
        tree = self._parser.parse_code(code, "python")
        risks = self._analyze_tree(tree)
        for risk in risks:
            risk.file_path = "<string>"
        return risks

    def _analyze_tree(self, tree: dict) -> List[Risk]:
        """Analyze a parsed AST tree for all risk types."""
        risks: List[Risk] = []
        risks.extend(self.detect_security_risks(tree))
        risks.extend(self.detect_logic_risks(tree))
        risks.extend(self.detect_architecture_risks(tree))
        return risks

    def detect_security_risks(self, tree: dict) -> List[Risk]:
        """Detect security risks in the AST.

        Checks for SQL injection, hardcoded secrets, eval/exec usage,
        and pickle deserialization vulnerabilities.

        Args:
            tree: Parsed AST tree dict.

        Returns:
            List of security risks.
        """
        risks: List[Risk] = []
        self._detect_sql_injection(tree, risks)
        self._detect_hardcoded_secrets(tree, risks)
        self._detect_eval_exec(tree, risks)
        self._detect_pickle_usage(tree, risks)
        return risks

    def detect_logic_risks(self, tree: dict) -> List[Risk]:
        """Detect logic risks in the AST.

        Checks for unused variables, empty except blocks, and mutable
        default arguments.

        Args:
            tree: Parsed AST tree dict.

        Returns:
            List of logic risks.
        """
        risks: List[Risk] = []
        self._detect_unused_variables(tree, risks)
        self._detect_empty_except(tree, risks)
        self._detect_mutable_defaults(tree, risks)
        return risks

    def detect_architecture_risks(self, tree: dict) -> List[Risk]:
        """Detect architecture risks in the AST.

        Checks for long functions, deep nesting, and God Class patterns.

        Args:
            tree: Parsed AST tree dict.

        Returns:
            List of architecture risks.
        """
        risks: List[Risk] = []
        self._detect_long_functions(tree, risks)
        self._detect_deep_nesting(tree, risks)
        self._detect_god_class(tree, risks)
        return risks

    # -------------------------------------------------------------------
    # Security risk detection
    # -------------------------------------------------------------------

    def _detect_sql_injection(self, node: dict, risks: List[Risk]) -> None:
        """Detect potential SQL injection risks via string concatenation or f-strings."""
        text = node.get("text", "")
        node_type = node.get("type", "")

        # Check for string concatenation with SQL keywords
        if node_type == "binary_operator" and "+" in text:
            if self._contains_sql_keywords(text):
                risks.append(Risk(
                    level=RiskLevel.HIGH,
                    category=RiskCategory.SECURITY,
                    message="Potential SQL injection via string concatenation",
                    file_path="",
                    line_number=node.get("start_line"),
                    suggestion="Use parameterized queries instead of string concatenation",
                ))

        # Check for f-strings with SQL keywords (tree-sitter parses f-strings as "string" type)
        if node_type == "string" and text.startswith(('f"', "f'")):
            if self._contains_sql_keywords(text):
                risks.append(Risk(
                    level=RiskLevel.HIGH,
                    category=RiskCategory.SECURITY,
                    message="Potential SQL injection via f-string",
                    file_path="",
                    line_number=node.get("start_line"),
                    suggestion="Use parameterized queries instead of f-strings for SQL",
                ))

        # Check for %-formatting with SQL keywords
        if node_type == "binary_operator" and "%" in text:
            if self._contains_sql_keywords(text):
                risks.append(Risk(
                    level=RiskLevel.HIGH,
                    category=RiskCategory.SECURITY,
                    message="Potential SQL injection via %-formatting",
                    file_path="",
                    line_number=node.get("start_line"),
                    suggestion="Use parameterized queries instead of %-formatting",
                ))

        for child in node.get("children", []):
            self._detect_sql_injection(child, risks)

    def _detect_hardcoded_secrets(self, node: dict, risks: List[Risk]) -> None:
        """Detect hardcoded secrets and credentials in variable assignments."""
        if node.get("type") == "assignment":
            children = node.get("children", [])
            # Find identifier (left) and string value (right) among children
            # Assignment children include the "=" operator token
            left = None
            right = None
            for child in children:
                if child.get("type") == "identifier" and left is None:
                    left = child
                elif child.get("type") in ("string", "concatenated_string"):
                    right = child

            if left is not None and right is not None:
                left_text = left.get("text", "")
                for pattern in _SECRET_PATTERNS:
                    if pattern.search(left_text):
                        risks.append(Risk(
                            level=RiskLevel.CRITICAL,
                            category=RiskCategory.SECURITY,
                            message=f"Hardcoded secret detected: '{left_text}'",
                            file_path="",
                            line_number=node.get("start_line"),
                            suggestion="Use environment variables or a secrets manager instead of hardcoding secrets",
                        ))
                        break

        for child in node.get("children", []):
            self._detect_hardcoded_secrets(child, risks)

    def _detect_eval_exec(self, node: dict, risks: List[Risk]) -> None:
        """Detect usage of eval() and exec() functions."""
        if node.get("type") == "call":
            children = node.get("children", [])
            if children:
                func = children[0]
                if func.get("type") == "identifier":
                    func_name = func.get("text", "")
                    if func_name == "eval":
                        risks.append(Risk(
                            level=RiskLevel.CRITICAL,
                            category=RiskCategory.SECURITY,
                            message="Use of eval() detected - potential code injection risk",
                            file_path="",
                            line_number=node.get("start_line"),
                            suggestion="Avoid eval() - use ast.literal_eval() for safe evaluation or restructure code",
                        ))
                    elif func_name == "exec":
                        risks.append(Risk(
                            level=RiskLevel.CRITICAL,
                            category=RiskCategory.SECURITY,
                            message="Use of exec() detected - potential code injection risk",
                            file_path="",
                            line_number=node.get("start_line"),
                            suggestion="Avoid exec() - restructure code to avoid dynamic code execution",
                        ))

        for child in node.get("children", []):
            self._detect_eval_exec(child, risks)

    def _detect_pickle_usage(self, node: dict, risks: List[Risk]) -> None:
        """Detect usage of pickle module for deserialization."""
        node_type = node.get("type", "")
        text = node.get("text", "")

        # Check for import of pickle
        if node_type in ("import_statement", "import_from_statement"):
            if "pickle" in text:
                risks.append(Risk(
                    level=RiskLevel.HIGH,
                    category=RiskCategory.SECURITY,
                    message="Use of pickle module detected - potential deserialization vulnerability",
                    file_path="",
                    line_number=node.get("start_line"),
                    suggestion="Consider using safer alternatives like json or implement proper input validation",
                ))

        # Check for pickle.loads() or pickle.load() calls
        if node_type == "call":
            children = node.get("children", [])
            if children:
                func = children[0]
                if func.get("type") == "attribute":
                    attr_text = func.get("text", "")
                    if "pickle.loads" in attr_text or "pickle.load(" in attr_text:
                        risks.append(Risk(
                            level=RiskLevel.CRITICAL,
                            category=RiskCategory.SECURITY,
                            message="Use of pickle.loads()/pickle.load() - critical deserialization risk",
                            file_path="",
                            line_number=node.get("start_line"),
                            suggestion="Never unpickle untrusted data - use json or implement proper validation",
                        ))

        for child in node.get("children", []):
            self._detect_pickle_usage(child, risks)

    # -------------------------------------------------------------------
    # Logic risk detection
    # -------------------------------------------------------------------

    def _detect_unused_variables(self, node: dict, risks: List[Risk]) -> None:
        """Detect unused variables at module and function scope."""
        if node.get("type") in ("module", "function_definition"):
            assignments: dict = {}
            usages: Set[str] = set()
            self._collect_assignments_and_usages(node, assignments, usages)
            for name, line in assignments.items():
                if name not in usages and not name.startswith("_"):
                    risks.append(Risk(
                        level=RiskLevel.LOW,
                        category=RiskCategory.LOGIC,
                        message=f"Variable '{name}' is assigned but never used",
                        file_path="",
                        line_number=line,
                        suggestion=f"Remove unused variable '{name}' or prefix with '_' if intentionally unused",
                    ))

        for child in node.get("children", []):
            self._detect_unused_variables(child, risks)

    def _collect_assignments_and_usages(
        self, node: dict, assignments: dict, usages: Set[str]
    ) -> None:
        """Collect variable assignments and usages in a scope."""
        node_type = node.get("type", "")

        if node_type == "assignment":
            # Assignment children include the "=" operator token
            for child in node.get("children", []):
                if child.get("type") == "identifier":
                    name = child.get("text", "")
                    if name:
                        assignments[name] = node.get("start_line")
                    break
            # Collect usages from value side (non-identifier, non-operator children)
            for child in node.get("children", []):
                if child.get("type") not in ("identifier", "="):
                    self._collect_usages(child, usages)
            return

        if node_type == "identifier":
            name = node.get("text", "")
            if name:
                usages.add(name)

        for child in node.get("children", []):
            self._collect_assignments_and_usages(child, assignments, usages)

    def _collect_usages(self, node: dict, usages: Set[str]) -> None:
        """Collect all identifier usages from a node tree."""
        if node.get("type") == "identifier":
            name = node.get("text", "")
            if name:
                usages.add(name)

        for child in node.get("children", []):
            self._collect_usages(child, usages)

    def _detect_empty_except(self, node: dict, risks: List[Risk]) -> None:
        """Detect empty except blocks or except blocks with only pass."""
        if node.get("type") == "except_clause":
            children = node.get("children", [])
            body_children = []
            for child in children:
                if child.get("type") == "block":
                    body_children = child.get("children", [])
                    break

            if not body_children:
                risks.append(Risk(
                    level=RiskLevel.MEDIUM,
                    category=RiskCategory.LOGIC,
                    message="Empty except block - exceptions are silently ignored",
                    file_path="",
                    line_number=node.get("start_line"),
                    suggestion="Add proper exception handling or at least log the exception",
                ))
            elif len(body_children) == 1 and body_children[0].get("type") == "pass_statement":
                risks.append(Risk(
                    level=RiskLevel.LOW,
                    category=RiskCategory.LOGIC,
                    message="Except block with only 'pass' - exceptions are silently ignored",
                    file_path="",
                    line_number=node.get("start_line"),
                    suggestion="Consider logging the exception or adding proper handling",
                ))

        for child in node.get("children", []):
            self._detect_empty_except(child, risks)

    def _detect_mutable_defaults(self, node: dict, risks: List[Risk]) -> None:
        """Detect mutable default arguments in function definitions."""
        if node.get("type") == "function_definition":
            children = node.get("children", [])
            for child in children:
                if child.get("type") == "parameters":
                    self._check_mutable_params(child, risks)
                    break

        for child in node.get("children", []):
            self._detect_mutable_defaults(child, risks)

    def _check_mutable_params(self, params_node: dict, risks: List[Risk]) -> None:
        """Check for mutable default arguments in parameters."""
        for child in params_node.get("children", []):
            if child.get("type") == "default_parameter":
                for default_child in child.get("children", []):
                    if default_child.get("type") in _MUTABLE_TYPES:
                        risks.append(Risk(
                            level=RiskLevel.MEDIUM,
                            category=RiskCategory.LOGIC,
                            message="Mutable default argument detected",
                            file_path="",
                            line_number=child.get("start_line"),
                            suggestion="Use None as default and create mutable object inside the function",
                        ))
                        break

    # -------------------------------------------------------------------
    # Architecture risk detection
    # -------------------------------------------------------------------

    def _detect_long_functions(self, node: dict, risks: List[Risk]) -> None:
        """Detect functions that are too long (>50 lines)."""
        if node.get("type") == "function_definition":
            start = node.get("start_line", 0)
            end = node.get("end_line", 0)
            length = end - start + 1
            if length > 50:
                func_name = node.get("name", "<anonymous>")
                risks.append(Risk(
                    level=RiskLevel.MEDIUM,
                    category=RiskCategory.ARCHITECTURE,
                    message=f"Function '{func_name}' is too long ({length} lines)",
                    file_path="",
                    line_number=start,
                    suggestion=f"Consider breaking '{func_name}' into smaller, more focused functions",
                ))

        for child in node.get("children", []):
            self._detect_long_functions(child, risks)

    def _detect_deep_nesting(self, node: dict, risks: List[Risk], depth: int = 0) -> None:
        """Detect deeply nested code blocks (>4 levels)."""
        node_type = node.get("type", "")
        current_depth = depth

        if node_type in _NESTING_TYPES:
            current_depth += 1
            if current_depth > 4:
                risks.append(Risk(
                    level=RiskLevel.MEDIUM,
                    category=RiskCategory.ARCHITECTURE,
                    message=f"Deeply nested code (depth {current_depth})",
                    file_path="",
                    line_number=node.get("start_line"),
                    suggestion="Consider refactoring to reduce nesting depth using early returns or helper functions",
                ))

        for child in node.get("children", []):
            self._detect_deep_nesting(child, risks, current_depth)

    def _detect_god_class(self, node: dict, risks: List[Risk]) -> None:
        """Detect classes with too many methods (>10) - God Class pattern."""
        if node.get("type") == "class_definition":
            method_count = self._count_methods(node)
            if method_count > 10:
                class_name = node.get("name", "<anonymous>")
                risks.append(Risk(
                    level=RiskLevel.MEDIUM,
                    category=RiskCategory.ARCHITECTURE,
                    message=f"Class '{class_name}' has too many methods ({method_count}) - potential God Class",
                    file_path="",
                    line_number=node.get("start_line"),
                    suggestion=f"Consider splitting '{class_name}' into smaller, focused classes",
                ))

        for child in node.get("children", []):
            self._detect_god_class(child, risks)

    def _count_methods(self, class_node: dict) -> int:
        """Count methods in a class definition."""
        count = 0
        for child in class_node.get("children", []):
            count += self._count_methods_recursive(child)
        return count

    def _count_methods_recursive(self, node: dict) -> int:
        """Recursively count method definitions, stopping at nested classes."""
        count = 0
        if node.get("type") == "function_definition":
            count += 1
        # Don't recurse into nested classes
        if node.get("type") not in ("class_definition",):
            for child in node.get("children", []):
                count += self._count_methods_recursive(child)
        return count

    # -------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------

    @staticmethod
    def _contains_sql_keywords(text: str) -> bool:
        """Check if text contains SQL keywords."""
        upper_text = text.upper()
        return any(keyword in upper_text for keyword in _SQL_KEYWORDS)
