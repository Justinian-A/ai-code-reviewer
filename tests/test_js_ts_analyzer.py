"""Tests for the JavaScript/TypeScript code analyzer."""

import pytest

from ai_code_reviewer.analyzer.js_ts_analyzer import JSTSAnalyzer
from ai_code_reviewer.models import RiskCategory, RiskLevel


@pytest.fixture
def analyzer() -> JSTSAnalyzer:
    """Create a JSTSAnalyzer instance."""
    return JSTSAnalyzer()


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestInit:
    def test_creates_instance(self, analyzer: JSTSAnalyzer):
        assert analyzer is not None

    def test_has_parser(self, analyzer: JSTSAnalyzer):
        assert analyzer._parser is not None


# ---------------------------------------------------------------------------
# analyze_code — basic
# ---------------------------------------------------------------------------


class TestAnalyzeCode:
    def test_empty_code_returns_empty(self, analyzer: JSTSAnalyzer):
        risks = analyzer.analyze_code("", "javascript")
        assert risks == []

    def test_clean_code_returns_empty(self, analyzer: JSTSAnalyzer):
        code = "const x = 1;\nconst y = 2;\n"
        risks = analyzer.analyze_code(code, "javascript")
        assert risks == []

    def test_typescript_supported(self, analyzer: JSTSAnalyzer):
        code = "const x: number = 1;\n"
        risks = analyzer.analyze_code(code, "typescript")
        assert isinstance(risks, list)

    def test_unsupported_language_raises(self, analyzer: JSTSAnalyzer):
        with pytest.raises(ValueError, match="only supports"):
            analyzer.analyze_code("x = 1", "python")


# ---------------------------------------------------------------------------
# analyze_file
# ---------------------------------------------------------------------------


class TestAnalyzeFile:
    def test_analyze_js_file(self, analyzer: JSTSAnalyzer, tmp_path):
        p = tmp_path / "test.js"
        p.write_text("const x = 1;\n")
        risks = analyzer.analyze_file(str(p))
        assert isinstance(risks, list)

    def test_analyze_ts_file(self, analyzer: JSTSAnalyzer, tmp_path):
        p = tmp_path / "test.ts"
        p.write_text("const x: number = 1;\n")
        risks = analyzer.analyze_file(str(p))
        assert isinstance(risks, list)

    def test_file_not_found_raises(self, analyzer: JSTSAnalyzer):
        with pytest.raises(FileNotFoundError):
            analyzer.analyze_file("/nonexistent/file.js")

    def test_unsupported_extension_raises(self, analyzer: JSTSAnalyzer, tmp_path):
        p = tmp_path / "test.py"
        p.write_text("x = 1\n")
        with pytest.raises(ValueError, match="only supports"):
            analyzer.analyze_file(str(p))


# ---------------------------------------------------------------------------
# Security risks
# ---------------------------------------------------------------------------


class TestSecurityRisks:
    def test_innerhtml_detected(self, analyzer: JSTSAnalyzer):
        code = "el.innerHTML = userInput;\n"
        risks = analyzer.analyze_code(code, "javascript")
        sec = [r for r in risks if r.category == RiskCategory.SECURITY]
        assert len(sec) >= 1
        assert any("innerHTML" in r.message for r in sec)
        assert sec[0].level == RiskLevel.HIGH

    def test_eval_detected(self, analyzer: JSTSAnalyzer):
        code = 'eval("alert(1)");\n'
        risks = analyzer.analyze_code(code, "javascript")
        sec = [r for r in risks if r.category == RiskCategory.SECURITY]
        assert len(sec) >= 1
        assert any("eval" in r.message for r in sec)
        assert any(r.level == RiskLevel.CRITICAL for r in sec)

    def test_dangerously_set_innerhtml_detected(self, analyzer: JSTSAnalyzer):
        code = '<div dangerouslySetInnerHTML={{__html: userHtml}} />\n'
        risks = analyzer.analyze_code(code, "javascript")
        sec = [r for r in risks if r.category == RiskCategory.SECURITY]
        assert len(sec) >= 1
        assert any("dangerouslySetInnerHTML" in r.message for r in sec)

    def test_document_write_detected(self, analyzer: JSTSAnalyzer):
        code = "document.write('<h1>Hello</h1>');\n"
        risks = analyzer.analyze_code(code, "javascript")
        sec = [r for r in risks if r.category == RiskCategory.SECURITY]
        assert len(sec) >= 1
        assert any("document.write" in r.message for r in sec)

    def test_no_security_risk_on_clean_code(self, analyzer: JSTSAnalyzer):
        code = "const x = 1;\nconsole.log(x);\n"
        risks = analyzer.analyze_code(code, "javascript")
        sec = [r for r in risks if r.category == RiskCategory.SECURITY]
        assert len(sec) == 0

    def test_multiple_security_risks(self, analyzer: JSTSAnalyzer):
        code = (
            "el.innerHTML = data;\n"
            "eval(code);\n"
            "document.write(html);\n"
        )
        risks = analyzer.analyze_code(code, "javascript")
        sec = [r for r in risks if r.category == RiskCategory.SECURITY]
        assert len(sec) >= 3

    def test_security_risk_has_suggestion(self, analyzer: JSTSAnalyzer):
        code = "el.innerHTML = data;\n"
        risks = analyzer.analyze_code(code, "javascript")
        sec = [r for r in risks if r.category == RiskCategory.SECURITY]
        assert sec[0].suggestion is not None
        assert len(sec[0].suggestion) > 0


# ---------------------------------------------------------------------------
# Logic risks
# ---------------------------------------------------------------------------


class TestLogicRisks:
    def test_loose_equality_double_equals(self, analyzer: JSTSAnalyzer):
        code = "if (x == y) { }\n"
        risks = analyzer.analyze_code(code, "javascript")
        logic = [r for r in risks if r.category == RiskCategory.LOGIC]
        assert len(logic) >= 1
        assert any("==" in r.message or "equality" in r.message.lower() for r in logic)

    def test_loose_equality_not_equals(self, analyzer: JSTSAnalyzer):
        code = "if (x != y) { }\n"
        risks = analyzer.analyze_code(code, "javascript")
        logic = [r for r in risks if r.category == RiskCategory.LOGIC]
        assert len(logic) >= 1

    def test_strict_equality_no_flag(self, analyzer: JSTSAnalyzer):
        code = "if (x === y) { }\n"
        risks = analyzer.analyze_code(code, "javascript")
        logic = [r for r in risks if r.category == RiskCategory.LOGIC]
        # Should not flag ===
        assert not any("equality" in r.message.lower() and "===" not in r.message for r in logic)

    def test_strict_not_equals_no_flag(self, analyzer: JSTSAnalyzer):
        code = "if (x !== y) { }\n"
        risks = analyzer.analyze_code(code, "javascript")
        logic = [r for r in risks if r.category == RiskCategory.LOGIC]
        assert len(logic) == 0

    def test_var_detected(self, analyzer: JSTSAnalyzer):
        code = "var x = 1;\n"
        risks = analyzer.analyze_code(code, "javascript")
        logic = [r for r in risks if r.category == RiskCategory.LOGIC]
        assert len(logic) >= 1
        assert any("var" in r.message for r in logic)

    def test_let_no_flag(self, analyzer: JSTSAnalyzer):
        code = "let x = 1;\n"
        risks = analyzer.analyze_code(code, "javascript")
        logic = [r for r in risks if r.category == RiskCategory.LOGIC]
        assert not any("var" in r.message for r in logic)

    def test_const_no_flag(self, analyzer: JSTSAnalyzer):
        code = "const x = 1;\n"
        risks = analyzer.analyze_code(code, "javascript")
        logic = [r for r in risks if r.category == RiskCategory.LOGIC]
        assert not any("var" in r.message for r in logic)

    def test_logic_risk_has_line_number(self, analyzer: JSTSAnalyzer):
        code = "const a = 1;\nvar b = 2;\n"
        risks = analyzer.analyze_code(code, "javascript")
        logic = [r for r in risks if r.category == RiskCategory.LOGIC]
        for r in logic:
            assert r.line_number is not None

    def test_logic_risk_has_suggestion(self, analyzer: JSTSAnalyzer):
        code = "var x = 1;\n"
        risks = analyzer.analyze_code(code, "javascript")
        logic = [r for r in risks if r.category == RiskCategory.LOGIC]
        assert logic[0].suggestion is not None


# ---------------------------------------------------------------------------
# Architecture risks
# ---------------------------------------------------------------------------


class TestArchitectureRisks:
    def test_long_function_detected(self, analyzer: JSTSAnalyzer):
        # Build a function with > 50 lines
        lines = ["function longFunc() {"]
        for i in range(55):
            lines.append(f"    const x{i} = {i};")
        lines.append("}")
        code = "\n".join(lines) + "\n"

        risks = analyzer.analyze_code(code, "javascript")
        arch = [r for r in risks if r.category == RiskCategory.ARCHITECTURE]
        assert any("long" in r.message.lower() or "lines" in r.message.lower() for r in arch)

    def test_short_function_no_flag(self, analyzer: JSTSAnalyzer):
        code = "function short() {\n    return 1;\n}\n"
        risks = analyzer.analyze_code(code, "javascript")
        arch = [r for r in risks if r.category == RiskCategory.ARCHITECTURE]
        assert not any("lines" in r.message.lower() for r in arch)

    def test_deep_nesting_detected(self, analyzer: JSTSAnalyzer):
        # Build deeply nested code (> 4 levels)
        code = (
            "function deep() {\n"
            "    if (a) {\n"
            "        for (let i = 0; i < 10; i++) {\n"
            "            while (b) {\n"
            "                if (c) {\n"
            "                    do { } while (d);\n"
            "                }\n"
            "            }\n"
            "        }\n"
            "    }\n"
            "}\n"
        )
        risks = analyzer.analyze_code(code, "javascript")
        arch = [r for r in risks if r.category == RiskCategory.ARCHITECTURE]
        assert any("nesting" in r.message.lower() for r in arch)

    def test_callback_hell_detected(self, analyzer: JSTSAnalyzer):
        # Build deeply nested callbacks (> 3 levels)
        code = (
            "function loadData() {\n"
            "    getData(function(a) {\n"
            "        processA(a, function(b) {\n"
            "            processB(b, function(c) {\n"
            "                processC(c, function(d) {\n"
            "                    console.log(d);\n"
            "                });\n"
            "            });\n"
            "        });\n"
            "    });\n"
            "}\n"
        )
        risks = analyzer.analyze_code(code, "javascript")
        arch = [r for r in risks if r.category == RiskCategory.ARCHITECTURE]
        assert any("callback" in r.message.lower() for r in arch)

    def test_no_arch_risk_on_clean_code(self, analyzer: JSTSAnalyzer):
        code = "function add(a, b) {\n    return a + b;\n}\n"
        risks = analyzer.analyze_code(code, "javascript")
        arch = [r for r in risks if r.category == RiskCategory.ARCHITECTURE]
        assert len(arch) == 0

    def test_arch_risk_has_suggestion(self, analyzer: JSTSAnalyzer):
        lines = ["function longFunc() {"]
        for i in range(55):
            lines.append(f"    const x{i} = {i};")
        lines.append("}")
        code = "\n".join(lines) + "\n"

        risks = analyzer.analyze_code(code, "javascript")
        arch = [r for r in risks if r.category == RiskCategory.ARCHITECTURE]
        assert arch[0].suggestion is not None


# ---------------------------------------------------------------------------
# detect_security_risks — direct call
# ---------------------------------------------------------------------------


class TestDetectSecurityRisksDirect:
    def test_returns_list(self, analyzer: JSTSAnalyzer):
        tree = analyzer._parser.parse_code("const x = 1;", "javascript")
        risks = analyzer.detect_security_risks(tree)
        assert isinstance(risks, list)

    def test_detects_eval_in_tree(self, analyzer: JSTSAnalyzer):
        tree = analyzer._parser.parse_code('eval("test");', "javascript")
        risks = analyzer.detect_security_risks(tree)
        assert len(risks) >= 1


# ---------------------------------------------------------------------------
# detect_logic_risks — direct call
# ---------------------------------------------------------------------------


class TestDetectLogicRisksDirect:
    def test_returns_list(self, analyzer: JSTSAnalyzer):
        tree = analyzer._parser.parse_code("const x = 1;", "javascript")
        risks = analyzer.detect_logic_risks("const x = 1;", tree)
        assert isinstance(risks, list)

    def test_detects_var(self, analyzer: JSTSAnalyzer):
        tree = analyzer._parser.parse_code("var x = 1;", "javascript")
        risks = analyzer.detect_logic_risks("var x = 1;", tree)
        assert any("var" in r.message for r in risks)


# ---------------------------------------------------------------------------
# detect_architecture_risks — direct call
# ---------------------------------------------------------------------------


class TestDetectArchitectureRisksDirect:
    def test_returns_list(self, analyzer: JSTSAnalyzer):
        tree = analyzer._parser.parse_code("const x = 1;", "javascript")
        risks = analyzer.detect_architecture_risks(tree)
        assert isinstance(risks, list)


# ---------------------------------------------------------------------------
# Integration
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_all_categories_present_in_complex_code(self, analyzer: JSTSAnalyzer):
        """Code with security, logic, and architecture issues should flag all."""
        lines = ["function risky() {"]
        lines.append("    var x = 1;")
        lines.append("    el.innerHTML = data;")
        for i in range(50):
            lines.append(f"    const v{i} = {i};")
        lines.append("}")
        code = "\n".join(lines) + "\n"

        risks = analyzer.analyze_code(code, "javascript")
        categories = {r.category for r in risks}
        assert RiskCategory.SECURITY in categories
        assert RiskCategory.LOGIC in categories
        assert RiskCategory.ARCHITECTURE in categories

    def test_risk_file_path_preserved(self, analyzer: JSTSAnalyzer):
        code = "el.innerHTML = data;\n"
        risks = analyzer.analyze_code(code, "javascript", file_path="src/app.js")
        for r in risks:
            assert r.file_path == "src/app.js"

    def test_risks_are_risk_model_instances(self, analyzer: JSTSAnalyzer):
        code = "var x = 1;\n"
        risks = analyzer.analyze_code(code, "javascript")
        for r in risks:
            assert hasattr(r, "level")
            assert hasattr(r, "category")
            assert hasattr(r, "message")
            assert hasattr(r, "file_path")


# ---------------------------------------------------------------------------
# Parse failure handling
# ---------------------------------------------------------------------------


class TestParseFailure:
    """Test that parse failures return empty list."""

    def test_parse_failure_returns_empty(self, analyzer: JSTSAnalyzer):
        """When parser raises an exception, analyze_code should return empty list."""
        from unittest.mock import MagicMock, patch

        with patch.object(analyzer._parser, "parse_code", side_effect=Exception("parse error")):
            risks = analyzer.analyze_code("invalid code", "javascript")
            assert risks == []

    def test_parse_failure_typescript(self, analyzer: JSTSAnalyzer):
        """Parse failure for TypeScript should also return empty list."""
        from unittest.mock import MagicMock, patch

        with patch.object(analyzer._parser, "parse_code", side_effect=Exception("parse error")):
            risks = analyzer.analyze_code("invalid code", "typescript")
            assert risks == []
