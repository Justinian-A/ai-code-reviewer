"""Tree-sitter based AST parser for Python and JavaScript/TypeScript."""

from pathlib import Path
from typing import Dict, List, Optional

import tree_sitter_javascript as tsjavascript
import tree_sitter_python as tspython
import tree_sitter_typescript as tsts
from tree_sitter import Language, Node, Parser

# Language extension mapping
_EXT_TO_LANG: Dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
}

# Python node types that contribute to cyclomatic complexity
_PYTHON_BRANCH_NODES = frozenset({
    "if_statement",
    "elif_clause",
    "for_statement",
    "while_statement",
    "except_clause",
    "with_statement",
    "assert_statement",
    "conditional_expression",
    "boolean_operator",
})

# JavaScript/TypeScript node types that contribute to cyclomatic complexity
_JS_BRANCH_NODES = frozenset({
    "if_statement",
    "for_statement",
    "for_in_statement",
    "while_statement",
    "do_statement",
    "switch_statement",
    "catch_clause",
    "ternary_expression",
    "binary_expression",
    "conditional_expression",
})


class ASTParser:
    """AST parser using Tree-sitter for Python and JavaScript/TypeScript.

    Supports code structure extraction (functions, classes, imports) and
    cyclomatic complexity calculation.
    """

    def __init__(self) -> None:
        """Initialize parsers for supported languages."""
        self._python_lang = Language(tspython.language())
        self._js_lang = Language(tsjavascript.language())
        self._ts_lang = Language(tsts.language_typescript())
        self._parser = Parser()

    def parse_file(self, file_path: str) -> dict:
        """Parse a file and return its code structure as a dict.

        Args:
            file_path: Path to the source file.

        Returns:
            Dict representation of the AST with node types, positions, and children.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the language cannot be detected.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        language = self.detect_language(file_path)
        code = path.read_text(encoding="utf-8")
        return self.parse_code(code, language)

    def parse_code(self, code: str, language: str) -> dict:
        """Parse a code string and return its structure as a dict.

        Args:
            code: Source code string to parse.
            language: Language identifier ("python", "javascript", or "typescript").

        Returns:
            Dict representation of the AST.

        Raises:
            ValueError: If the language is not supported.
        """
        lang_key = language.lower()
        if lang_key == "python":
            self._parser.language = self._python_lang
        elif lang_key == "javascript":
            self._parser.language = self._js_lang
        elif lang_key == "typescript":
            self._parser.language = self._ts_lang
        else:
            raise ValueError(
                f"Unsupported language: {language!r}. "
                f"Supported: python, javascript, typescript"
            )

        code_bytes = code.encode("utf-8")
        tree = self._parser.parse(code_bytes)
        return self._node_to_dict(tree.root_node, code_bytes)

    def extract_functions(self, tree: dict) -> List[dict]:
        """Extract function information from a parsed AST dict.

        Args:
            tree: Dict representation of the AST (from parse_code/parse_file).

        Returns:
            List of dicts with keys: name, start_line, end_line, text.
        """
        functions: List[dict] = []
        self._walk_and_collect(tree, {"function_definition", "function_declaration", "arrow_function", "method_definition"}, functions)
        return functions

    def extract_classes(self, tree: dict) -> List[dict]:
        """Extract class information from a parsed AST dict.

        Args:
            tree: Dict representation of the AST (from parse_code/parse_file).

        Returns:
            List of dicts with keys: name, start_line, end_line, text, methods.
        """
        classes: List[dict] = []
        self._walk_and_collect_classes(tree, classes)
        return classes

    def calculate_complexity(self, tree: dict) -> int:
        """Calculate cyclomatic complexity from a parsed AST dict.

        Cyclomatic complexity = 1 + number of branching/decision points.

        Args:
            tree: Dict representation of the AST (from parse_code/parse_file).

        Returns:
            Integer cyclomatic complexity score (minimum 1).
        """
        # Determine which branch node set to use based on root type
        root_type = tree.get("type", "")
        if root_type == "module":
            branch_nodes = _PYTHON_BRANCH_NODES
        else:
            branch_nodes = _JS_BRANCH_NODES

        count = self._count_branches(tree, branch_nodes)
        return 1 + count

    def detect_language(self, file_path: str) -> str:
        """Detect the programming language from a file path.

        Args:
            file_path: Path to the source file.

        Returns:
            Language string: "python", "javascript", or "typescript".

        Raises:
            ValueError: If the file extension is not recognized.
        """
        ext = Path(file_path).suffix.lower()
        lang = _EXT_TO_LANG.get(ext)
        if lang is None:
            raise ValueError(
                f"Cannot detect language for extension {ext!r}. "
                f"Supported: {', '.join(sorted(set(_EXT_TO_LANG.values())))}"
            )
        return lang

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _node_to_dict(self, node: Node, code_bytes: bytes) -> dict:
        """Convert a tree-sitter Node to a plain dict."""
        result: dict = {
            "type": node.type,
            "start_line": node.start_point[0] + 1,  # 1-indexed
            "start_col": node.start_point[1],
            "end_line": node.end_point[0] + 1,
            "end_col": node.end_point[1],
            "text": code_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace"),
        }

        # Add name for named constructs
        name = self._extract_name(node, code_bytes)
        if name is not None:
            result["name"] = name

        # Recurse into children
        if node.child_count > 0:
            result["children"] = [
                self._node_to_dict(child, code_bytes) for child in node.children
            ]
        else:
            result["children"] = []

        return result

    @staticmethod
    def _extract_name(node: Node, code_bytes: bytes) -> Optional[str]:
        """Extract the name identifier from a function/class definition node."""
        _NAMED_TYPES = frozenset({
            "function_definition",
            "class_definition",
            "function_declaration",
            "class_declaration",
            "method_definition",
        })
        if node.type in _NAMED_TYPES:
            # Look for the 'name' field child (identifier or property_identifier)
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                return code_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace")
        return None

    @staticmethod
    def _walk_and_collect(
        node: dict, target_types: set, results: List[dict]
    ) -> None:
        """Walk the AST dict and collect nodes matching target types."""
        if node.get("type") in target_types:
            entry: dict = {
                "name": node.get("name", "<anonymous>"),
                "start_line": node["start_line"],
                "end_line": node["end_line"],
                "text": node.get("text", ""),
            }
            results.append(entry)

        for child in node.get("children", []):
            ASTParser._walk_and_collect(child, target_types, results)

    @staticmethod
    def _walk_and_collect_classes(node: dict, results: List[dict]) -> None:
        """Walk the AST dict and collect class definitions with their methods."""
        if node.get("type") in ("class_definition", "class_declaration"):
            methods: List[dict] = []
            # Collect methods from children
            for child in node.get("children", []):
                ASTParser._collect_methods(child, methods)

            entry: dict = {
                "name": node.get("name", "<anonymous>"),
                "start_line": node["start_line"],
                "end_line": node["end_line"],
                "text": node.get("text", ""),
                "methods": methods,
            }
            results.append(entry)
        else:
            for child in node.get("children", []):
                ASTParser._walk_and_collect_classes(child, results)

    @staticmethod
    def _collect_methods(node: dict, methods: List[dict]) -> None:
        """Recursively collect method definitions from a class body."""
        node_type = node.get("type", "")
        if node_type in ("function_definition", "function_declaration", "method_definition"):
            methods.append({
                "name": node.get("name", "<anonymous>"),
                "start_line": node["start_line"],
                "end_line": node["end_line"],
            })
        # Recurse into blocks (but not into nested classes)
        if node_type != "class_definition" and node_type != "class_declaration":
            for child in node.get("children", []):
                ASTParser._collect_methods(child, methods)

    @staticmethod
    def _count_branches(node: dict, branch_nodes: frozenset) -> int:
        """Count branching nodes recursively in the AST dict."""
        count = 0
        node_type = node.get("type", "")

        if node_type in branch_nodes:
            # For boolean_operator / binary_expression, count each occurrence
            # (each 'and'/'or' or '&&'/'||' adds a branch)
            count += 1

        for child in node.get("children", []):
            count += ASTParser._count_branches(child, branch_nodes)

        return count
