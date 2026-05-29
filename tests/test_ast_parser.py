"""Tests for the Tree-sitter AST parser."""

import pytest

from ai_code_reviewer.analyzer.ast_parser import ASTParser


@pytest.fixture
def parser() -> ASTParser:
    """Create an ASTParser instance."""
    return ASTParser()


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestInit:
    def test_creates_instance(self, parser: ASTParser):
        assert parser is not None

    def test_has_parsers(self, parser: ASTParser):
        assert parser._parser is not None
        assert parser._python_lang is not None
        assert parser._js_lang is not None
        assert parser._ts_lang is not None


# ---------------------------------------------------------------------------
# detect_language
# ---------------------------------------------------------------------------


class TestDetectLanguage:
    def test_python_file(self, parser: ASTParser):
        assert parser.detect_language("main.py") == "python"

    def test_python_stub(self, parser: ASTParser):
        assert parser.detect_language("types.pyi") == "python"

    def test_javascript_file(self, parser: ASTParser):
        assert parser.detect_language("app.js") == "javascript"

    def test_jsx_file(self, parser: ASTParser):
        assert parser.detect_language("App.jsx") == "javascript"

    def test_mjs_file(self, parser: ASTParser):
        assert parser.detect_language("module.mjs") == "javascript"

    def test_typescript_file(self, parser: ASTParser):
        assert parser.detect_language("index.ts") == "typescript"

    def test_tsx_file(self, parser: ASTParser):
        assert parser.detect_language("Component.tsx") == "typescript"

    def test_path_with_directories(self, parser: ASTParser):
        assert parser.detect_language("src/utils/helper.py") == "python"

    def test_unsupported_extension_raises(self, parser: ASTParser):
        with pytest.raises(ValueError, match="Cannot detect language"):
            parser.detect_language("main.go")

    def test_no_extension_raises(self, parser: ASTParser):
        with pytest.raises(ValueError, match="Cannot detect language"):
            parser.detect_language("Makefile")


# ---------------------------------------------------------------------------
# parse_code
# ---------------------------------------------------------------------------


class TestParseCode:
    def test_python_simple(self, parser: ASTParser):
        tree = parser.parse_code("x = 1", "python")
        assert tree["type"] == "module"
        assert "children" in tree
        assert len(tree["children"]) > 0

    def test_javascript_simple(self, parser: ASTParser):
        tree = parser.parse_code("let x = 1;", "javascript")
        assert tree["type"] == "program"
        assert "children" in tree

    def test_typescript_simple(self, parser: ASTParser):
        tree = parser.parse_code("const x: number = 1;", "typescript")
        assert tree["type"] == "program"
        assert "children" in tree

    def test_unsupported_language_raises(self, parser: ASTParser):
        with pytest.raises(ValueError, match="Unsupported language"):
            parser.parse_code("int x = 1;", "c")

    def test_node_has_required_fields(self, parser: ASTParser):
        tree = parser.parse_code("x = 1", "python")
        assert "type" in tree
        assert "start_line" in tree
        assert "end_line" in tree
        assert "text" in tree
        assert "children" in tree

    def test_line_numbers_are_1_indexed(self, parser: ASTParser):
        tree = parser.parse_code("x = 1\ny = 2", "python")
        assert tree["start_line"] == 1
        # Second statement should start at line 2
        if len(tree["children"]) >= 2:
            assert tree["children"][1]["start_line"] == 2

    def test_python_syntax_error_still_parses(self, parser: ASTParser):
        # Tree-sitter is error-tolerant — it should still return a tree
        tree = parser.parse_code("def foo(:", "python")
        assert tree["type"] == "module"
        assert "children" in tree


# ---------------------------------------------------------------------------
# parse_file
# ---------------------------------------------------------------------------


class TestParseFile:
    def test_parse_python_file(self, parser: ASTParser, tmp_path):
        p = tmp_path / "test.py"
        p.write_text("def hello():\n    pass\n")
        tree = parser.parse_file(str(p))
        assert tree["type"] == "module"
        assert len(tree["children"]) >= 1

    def test_parse_js_file(self, parser: ASTParser, tmp_path):
        p = tmp_path / "test.js"
        p.write_text("function hello() {}\n")
        tree = parser.parse_file(str(p))
        assert tree["type"] == "program"

    def test_file_not_found_raises(self, parser: ASTParser):
        with pytest.raises(FileNotFoundError):
            parser.parse_file("/nonexistent/file.py")

    def test_unsupported_extension_raises(self, parser: ASTParser, tmp_path):
        p = tmp_path / "test.go"
        p.write_text("package main\n")
        with pytest.raises(ValueError, match="Cannot detect language"):
            parser.parse_file(str(p))


# ---------------------------------------------------------------------------
# extract_functions
# ---------------------------------------------------------------------------


class TestExtractFunctions:
    def test_python_simple_function(self, parser: ASTParser):
        tree = parser.parse_code("def hello():\n    pass\n", "python")
        funcs = parser.extract_functions(tree)
        assert len(funcs) == 1
        assert funcs[0]["name"] == "hello"
        assert funcs[0]["start_line"] == 1

    def test_python_multiple_functions(self, parser: ASTParser):
        code = "def foo():\n    pass\n\ndef bar():\n    pass\n"
        tree = parser.parse_code(code, "python")
        funcs = parser.extract_functions(tree)
        assert len(funcs) == 2
        names = {f["name"] for f in funcs}
        assert names == {"foo", "bar"}

    def test_python_nested_function(self, parser: ASTParser):
        code = "def outer():\n    def inner():\n        pass\n"
        tree = parser.parse_code(code, "python")
        funcs = parser.extract_functions(tree)
        names = {f["name"] for f in funcs}
        assert "outer" in names
        assert "inner" in names

    def test_python_method_in_class(self, parser: ASTParser):
        code = "class Foo:\n    def bar(self):\n        pass\n"
        tree = parser.parse_code(code, "python")
        funcs = parser.extract_functions(tree)
        assert any(f["name"] == "bar" for f in funcs)

    def test_js_simple_function(self, parser: ASTParser):
        code = "function hello() {}\n"
        tree = parser.parse_code(code, "javascript")
        funcs = parser.extract_functions(tree)
        assert len(funcs) == 1
        assert funcs[0]["name"] == "hello"

    def test_js_arrow_function(self, parser: ASTParser):
        code = "const greet = () => {};\n"
        tree = parser.parse_code(code, "javascript")
        funcs = parser.extract_functions(tree)
        assert len(funcs) >= 1

    def test_no_functions(self, parser: ASTParser):
        tree = parser.parse_code("x = 1\n", "python")
        funcs = parser.extract_functions(tree)
        assert len(funcs) == 0

    def test_function_has_text(self, parser: ASTParser):
        code = "def hello():\n    pass\n"
        tree = parser.parse_code(code, "python")
        funcs = parser.extract_functions(tree)
        assert "def hello" in funcs[0]["text"]


# ---------------------------------------------------------------------------
# extract_classes
# ---------------------------------------------------------------------------


class TestExtractClasses:
    def test_python_simple_class(self, parser: ASTParser):
        code = "class Foo:\n    pass\n"
        tree = parser.parse_code(code, "python")
        classes = parser.extract_classes(tree)
        assert len(classes) == 1
        assert classes[0]["name"] == "Foo"

    def test_python_class_with_methods(self, parser: ASTParser):
        code = "class Foo:\n    def bar(self):\n        pass\n    def baz(self):\n        pass\n"
        tree = parser.parse_code(code, "python")
        classes = parser.extract_classes(tree)
        assert len(classes) == 1
        assert classes[0]["name"] == "Foo"
        method_names = {m["name"] for m in classes[0]["methods"]}
        assert method_names == {"bar", "baz"}

    def test_python_class_with_inheritance(self, parser: ASTParser):
        code = "class Foo(Bar):\n    pass\n"
        tree = parser.parse_code(code, "python")
        classes = parser.extract_classes(tree)
        assert len(classes) == 1
        assert classes[0]["name"] == "Foo"

    def test_js_simple_class(self, parser: ASTParser):
        code = "class Foo {}\n"
        tree = parser.parse_code(code, "javascript")
        classes = parser.extract_classes(tree)
        assert len(classes) == 1
        assert classes[0]["name"] == "Foo"

    def test_js_class_with_methods(self, parser: ASTParser):
        code = "class Foo {\n    bar() {}\n    baz() {}\n}\n"
        tree = parser.parse_code(code, "javascript")
        classes = parser.extract_classes(tree)
        assert len(classes) == 1
        method_names = {m["name"] for m in classes[0]["methods"]}
        assert method_names == {"bar", "baz"}

    def test_no_classes(self, parser: ASTParser):
        tree = parser.parse_code("x = 1\n", "python")
        classes = parser.extract_classes(tree)
        assert len(classes) == 0

    def test_multiple_classes(self, parser: ASTParser):
        code = "class A:\n    pass\n\nclass B:\n    pass\n"
        tree = parser.parse_code(code, "python")
        classes = parser.extract_classes(tree)
        names = {c["name"] for c in classes}
        assert names == {"A", "B"}


# ---------------------------------------------------------------------------
# calculate_complexity
# ---------------------------------------------------------------------------


class TestCalculateComplexity:
    def test_simple_function_complexity_1(self, parser: ASTParser):
        code = "def foo():\n    pass\n"
        tree = parser.parse_code(code, "python")
        assert parser.calculate_complexity(tree) == 1

    def test_if_adds_complexity(self, parser: ASTParser):
        code = "def foo(x):\n    if x:\n        pass\n"
        tree = parser.parse_code(code, "python")
        assert parser.calculate_complexity(tree) == 2

    def test_if_elif_else_complexity(self, parser: ASTParser):
        code = (
            "def foo(x):\n"
            "    if x > 0:\n"
            "        pass\n"
            "    elif x < 0:\n"
            "        pass\n"
            "    else:\n"
            "        pass\n"
        )
        tree = parser.parse_code(code, "python")
        # 1 base + 1 if + 1 elif = 3
        assert parser.calculate_complexity(tree) == 3

    def test_for_loop_adds_complexity(self, parser: ASTParser):
        code = "def foo():\n    for i in range(10):\n        pass\n"
        tree = parser.parse_code(code, "python")
        assert parser.calculate_complexity(tree) == 2

    def test_while_loop_adds_complexity(self, parser: ASTParser):
        code = "def foo():\n    while True:\n        pass\n"
        tree = parser.parse_code(code, "python")
        assert parser.calculate_complexity(tree) == 2

    def test_try_except_adds_complexity(self, parser: ASTParser):
        code = "def foo():\n    try:\n        pass\n    except:\n        pass\n"
        tree = parser.parse_code(code, "python")
        # 1 base + 1 except_clause = 2
        assert parser.calculate_complexity(tree) >= 2

    def test_boolean_operator_adds_complexity(self, parser: ASTParser):
        code = "def foo(a, b):\n    if a and b:\n        pass\n"
        tree = parser.parse_code(code, "python")
        # 1 base + 1 if + 1 boolean_operator = 3
        assert parser.calculate_complexity(tree) == 3

    def test_nested_branches(self, parser: ASTParser):
        code = (
            "def foo(x):\n"
            "    if x > 0:\n"
            "        for i in range(x):\n"
            "            if i % 2 == 0:\n"
            "                pass\n"
        )
        tree = parser.parse_code(code, "python")
        # 1 base + 3 (if + for + if) = 4
        assert parser.calculate_complexity(tree) == 4

    def test_js_if_adds_complexity(self, parser: ASTParser):
        code = "function foo(x) {\n    if (x) {\n        return 1;\n    }\n}\n"
        tree = parser.parse_code(code, "javascript")
        assert parser.calculate_complexity(tree) == 2

    def test_js_logical_operators(self, parser: ASTParser):
        code = "function foo(a, b) {\n    if (a && b) {\n        return 1;\n    }\n}\n"
        tree = parser.parse_code(code, "javascript")
        # 1 base + 1 if + 1 binary_expression = 3
        assert parser.calculate_complexity(tree) == 3

    def test_empty_module_complexity_1(self, parser: ASTParser):
        tree = parser.parse_code("", "python")
        assert parser.calculate_complexity(tree) == 1


# ---------------------------------------------------------------------------
# Integration: parse_code + extract + complexity
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_full_python_analysis(self, parser: ASTParser):
        code = '''"""Module docstring."""

import os
from pathlib import Path

class Calculator:
    """A simple calculator."""

    def add(self, a: int, b: int) -> int:
        return a + b

    def divide(self, a: float, b: float) -> float:
        if b == 0:
            raise ValueError("Division by zero")
        return a / b

def process(items: list) -> list:
    result = []
    for item in items:
        if item > 0:
            result.append(item)
    return result
'''
        tree = parser.parse_code(code, "python")

        # Structure
        assert tree["type"] == "module"

        # Functions (top-level + methods)
        funcs = parser.extract_functions(tree)
        func_names = {f["name"] for f in funcs}
        assert "add" in func_names
        assert "divide" in func_names
        assert "process" in func_names

        # Classes
        classes = parser.extract_classes(tree)
        assert len(classes) == 1
        assert classes[0]["name"] == "Calculator"
        method_names = {m["name"] for m in classes[0]["methods"]}
        assert "add" in method_names
        assert "divide" in method_names

        # Complexity
        complexity = parser.calculate_complexity(tree)
        # 1 base + 1 if (b==0) + 1 for + 1 if (item>0) = 4
        assert complexity >= 3

    def test_full_js_analysis(self, parser: ASTParser):
        code = '''import React from 'react';

class UserService {
    constructor(api) {
        this.api = api;
    }

    async fetchUser(id) {
        if (!id) return null;
        try {
            const res = await this.api.get(`/users/${id}`);
            return res.data;
        } catch (err) {
            console.error(err);
            return null;
        }
    }
}

function validate(user) {
    if (user && user.name) {
        return true;
    }
    return false;
}
'''
        tree = parser.parse_code(code, "javascript")

        # Functions
        funcs = parser.extract_functions(tree)
        func_names = {f["name"] for f in funcs}
        assert "fetchUser" in func_names
        assert "validate" in func_names

        # Classes
        classes = parser.extract_classes(tree)
        assert len(classes) >= 1
        assert classes[0]["name"] == "UserService"

        # Complexity
        complexity = parser.calculate_complexity(tree)
        assert complexity >= 3
