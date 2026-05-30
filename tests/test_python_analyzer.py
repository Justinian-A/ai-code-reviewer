"""Tests for the Python code analyzer."""

import pytest
from pathlib import Path

from ai_code_reviewer.analyzer.python_analyzer import PythonAnalyzer
from ai_code_reviewer.models import Risk, RiskCategory, RiskLevel


@pytest.fixture
def analyzer() -> PythonAnalyzer:
    """Create a PythonAnalyzer instance."""
    return PythonAnalyzer()


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestInit:
    def test_creates_instance(self, analyzer: PythonAnalyzer):
        assert analyzer is not None

    def test_has_parser(self, analyzer: PythonAnalyzer):
        assert analyzer._parser is not None


# ---------------------------------------------------------------------------
# analyze_code - Security Risks
# ---------------------------------------------------------------------------


class TestSecurityRisks:
    def test_sql_injection_concatenation(self, analyzer: PythonAnalyzer):
        code = 'query = "SELECT * FROM users WHERE id = " + user_id\n'
        risks = analyzer.analyze_code(code)
        sql_risks = [r for r in risks if "SQL injection" in r.message and "concatenation" in r.message]
        assert len(sql_risks) == 1
        assert sql_risks[0].level == RiskLevel.HIGH
        assert sql_risks[0].category == RiskCategory.SECURITY
        assert sql_risks[0].line_number is not None

    def test_sql_injection_fstring(self, analyzer: PythonAnalyzer):
        code = 'query = f"SELECT * FROM users WHERE id = {user_id}"\n'
        risks = analyzer.analyze_code(code)
        sql_risks = [r for r in risks if "SQL injection" in r.message and "f-string" in r.message]
        assert len(sql_risks) == 1
        assert sql_risks[0].level == RiskLevel.HIGH
        assert sql_risks[0].category == RiskCategory.SECURITY

    def test_sql_injection_percent_format(self, analyzer: PythonAnalyzer):
        code = 'query = "SELECT * FROM users WHERE id = %s" % user_id\n'
        risks = analyzer.analyze_code(code)
        sql_risks = [r for r in risks if "SQL injection" in r.message and "%-formatting" in r.message]
        assert len(sql_risks) == 1
        assert sql_risks[0].level == RiskLevel.HIGH

    def test_hardcoded_secret_password(self, analyzer: PythonAnalyzer):
        code = 'password = "super_secret_123"\n'
        risks = analyzer.analyze_code(code)
        secret_risks = [r for r in risks if "Hardcoded secret" in r.message]
        assert len(secret_risks) == 1
        assert secret_risks[0].level == RiskLevel.CRITICAL
        assert secret_risks[0].category == RiskCategory.SECURITY
        assert "password" in secret_risks[0].message

    def test_hardcoded_secret_api_key(self, analyzer: PythonAnalyzer):
        code = 'api_key = "sk-1234567890abcdef"\n'
        risks = analyzer.analyze_code(code)
        secret_risks = [r for r in risks if "Hardcoded secret" in r.message]
        assert len(secret_risks) == 1
        assert secret_risks[0].level == RiskLevel.CRITICAL

    def test_hardcoded_secret_token(self, analyzer: PythonAnalyzer):
        code = 'access_token = "ghp_xxxxxxxxxxxx"\n'
        risks = analyzer.analyze_code(code)
        secret_risks = [r for r in risks if "Hardcoded secret" in r.message]
        assert len(secret_risks) == 1

    def test_eval_usage(self, analyzer: PythonAnalyzer):
        code = "result = eval(user_input)\n"
        risks = analyzer.analyze_code(code)
        eval_risks = [r for r in risks if "eval()" in r.message]
        assert len(eval_risks) == 1
        assert eval_risks[0].level == RiskLevel.CRITICAL
        assert eval_risks[0].category == RiskCategory.SECURITY

    def test_exec_usage(self, analyzer: PythonAnalyzer):
        code = "exec(code_string)\n"
        risks = analyzer.analyze_code(code)
        exec_risks = [r for r in risks if "exec()" in r.message]
        assert len(exec_risks) == 1
        assert exec_risks[0].level == RiskLevel.CRITICAL
        assert exec_risks[0].category == RiskCategory.SECURITY

    def test_pickle_import(self, analyzer: PythonAnalyzer):
        code = "import pickle\n"
        risks = analyzer.analyze_code(code)
        pickle_risks = [r for r in risks if "pickle" in r.message.lower()]
        assert len(pickle_risks) == 1
        assert pickle_risks[0].level == RiskLevel.HIGH
        assert pickle_risks[0].category == RiskCategory.SECURITY

    def test_pickle_from_import(self, analyzer: PythonAnalyzer):
        code = "from pickle import loads\n"
        risks = analyzer.analyze_code(code)
        pickle_risks = [r for r in risks if "pickle" in r.message.lower()]
        assert len(pickle_risks) == 1

    def test_clean_code_no_security_risks(self, analyzer: PythonAnalyzer):
        code = "x = 1\ny = 2\nprint(x + y)\n"
        risks = analyzer.analyze_code(code)
        security_risks = [r for r in risks if r.category == RiskCategory.SECURITY]
        assert len(security_risks) == 0


# ---------------------------------------------------------------------------
# analyze_code - Logic Risks
# ---------------------------------------------------------------------------


class TestLogicRisks:
    def test_empty_except_block(self, analyzer: PythonAnalyzer):
        code = "try:\n    pass\nexcept:\n    pass\n"
        risks = analyzer.analyze_code(code)
        except_risks = [r for r in risks if "except" in r.message.lower()]
        assert len(except_risks) >= 1
        assert any(r.category == RiskCategory.LOGIC for r in except_risks)

    def test_empty_except_no_body(self, analyzer: PythonAnalyzer):
        # Test with bare except that has no body
        code = "try:\n    x = 1\nexcept:\n    pass\n"
        risks = analyzer.analyze_code(code)
        except_risks = [r for r in risks if "except" in r.message.lower() and r.category == RiskCategory.LOGIC]
        assert len(except_risks) >= 1

    def test_mutable_default_list(self, analyzer: PythonAnalyzer):
        code = "def foo(items=[]):\n    items.append(1)\n"
        risks = analyzer.analyze_code(code)
        mutable_risks = [r for r in risks if "Mutable default" in r.message]
        assert len(mutable_risks) == 1
        assert mutable_risks[0].level == RiskLevel.MEDIUM
        assert mutable_risks[0].category == RiskCategory.LOGIC

    def test_mutable_default_dict(self, analyzer: PythonAnalyzer):
        code = "def bar(config={}):\n    config['key'] = 'value'\n"
        risks = analyzer.analyze_code(code)
        mutable_risks = [r for r in risks if "Mutable default" in r.message]
        assert len(mutable_risks) == 1

    def test_unused_variable(self, analyzer: PythonAnalyzer):
        code = "x = 1\ny = 2\nprint(y)\n"
        risks = analyzer.analyze_code(code)
        unused_risks = [r for r in risks if "never used" in r.message]
        assert len(unused_risks) == 1
        assert "x" in unused_risks[0].message
        assert unused_risks[0].level == RiskLevel.LOW
        assert unused_risks[0].category == RiskCategory.LOGIC

    def test_underscore_variable_not_flagged(self, analyzer: PythonAnalyzer):
        code = "_unused = 1\ny = 2\nprint(y)\n"
        risks = analyzer.analyze_code(code)
        unused_risks = [r for r in risks if "never used" in r.message]
        assert len(unused_risks) == 0

    def test_used_variable_not_flagged(self, analyzer: PythonAnalyzer):
        code = "x = 1\nprint(x)\n"
        risks = analyzer.analyze_code(code)
        unused_risks = [r for r in risks if "never used" in r.message]
        assert len(unused_risks) == 0

    def test_clean_code_no_logic_risks(self, analyzer: PythonAnalyzer):
        code = "x = 1\nprint(x)\n"
        risks = analyzer.analyze_code(code)
        logic_risks = [r for r in risks if r.category == RiskCategory.LOGIC]
        assert len(logic_risks) == 0


# ---------------------------------------------------------------------------
# analyze_code - Architecture Risks
# ---------------------------------------------------------------------------


class TestArchitectureRisks:
    def test_long_function(self, analyzer: PythonAnalyzer):
        # Create a function with 51 lines
        lines = ["def long_func():"]
        for i in range(50):
            lines.append(f"    x{i} = {i}")
        code = "\n".join(lines) + "\n"
        risks = analyzer.analyze_code(code)
        long_risks = [r for r in risks if "too long" in r.message]
        assert len(long_risks) == 1
        assert long_risks[0].level == RiskLevel.MEDIUM
        assert long_risks[0].category == RiskCategory.ARCHITECTURE
        assert "51" in long_risks[0].message

    def test_short_function_not_flagged(self, analyzer: PythonAnalyzer):
        lines = ["def short_func():"]
        for i in range(10):
            lines.append(f"    x{i} = {i}")
        code = "\n".join(lines) + "\n"
        risks = analyzer.analyze_code(code)
        long_risks = [r for r in risks if "too long" in r.message]
        assert len(long_risks) == 0

    def test_deep_nesting(self, analyzer: PythonAnalyzer):
        code = (
            "if a:\n"
            "    if b:\n"
            "        if c:\n"
            "            if d:\n"
            "                if e:\n"
            "                    pass\n"
        )
        risks = analyzer.analyze_code(code)
        nesting_risks = [r for r in risks if "nested" in r.message.lower()]
        assert len(nesting_risks) >= 1
        assert any(r.level == RiskLevel.MEDIUM for r in nesting_risks)
        assert any(r.category == RiskCategory.ARCHITECTURE for r in nesting_risks)

    def test_god_class(self, analyzer: PythonAnalyzer):
        methods = "\n".join([f"    def method{i}(self): pass" for i in range(11)])
        code = f"class GodClass:\n{methods}\n"
        risks = analyzer.analyze_code(code)
        god_risks = [r for r in risks if "God Class" in r.message]
        assert len(god_risks) == 1
        assert god_risks[0].level == RiskLevel.MEDIUM
        assert god_risks[0].category == RiskCategory.ARCHITECTURE
        assert "11" in god_risks[0].message

    def test_small_class_not_flagged(self, analyzer: PythonAnalyzer):
        methods = "\n".join([f"    def method{i}(self): pass" for i in range(5)])
        code = f"class SmallClass:\n{methods}\n"
        risks = analyzer.analyze_code(code)
        god_risks = [r for r in risks if "God Class" in r.message]
        assert len(god_risks) == 0

    def test_clean_code_no_architecture_risks(self, analyzer: PythonAnalyzer):
        code = "def foo():\n    pass\n"
        risks = analyzer.analyze_code(code)
        arch_risks = [r for r in risks if r.category == RiskCategory.ARCHITECTURE]
        assert len(arch_risks) == 0


# ---------------------------------------------------------------------------
# analyze_file
# ---------------------------------------------------------------------------


class TestAnalyzeFile:
    def test_analyze_file_sets_path(self, analyzer: PythonAnalyzer, tmp_path: Path):
        p = tmp_path / "test.py"
        p.write_text('password = "secret123"\n')
        risks = analyzer.analyze_file(str(p))
        assert len(risks) > 0
        assert all(r.file_path == str(p) for r in risks)

    def test_analyze_file_not_found(self, analyzer: PythonAnalyzer):
        with pytest.raises(FileNotFoundError):
            analyzer.analyze_file("/nonexistent/file.py")

    def test_analyze_file_syntax_error(self, analyzer: PythonAnalyzer, tmp_path: Path):
        p = tmp_path / "bad.py"
        p.write_text("def foo(:\n    pass\n")
        # Tree-sitter is error-tolerant, should not raise
        risks = analyzer.analyze_file(str(p))
        assert isinstance(risks, list)


# ---------------------------------------------------------------------------
# detect_security_risks / detect_logic_risks / detect_architecture_risks
# ---------------------------------------------------------------------------


class TestDetectMethods:
    def test_detect_security_risks_clean(self, analyzer: PythonAnalyzer):
        tree = analyzer._parser.parse_code("x = 1\n", "python")
        risks = analyzer.detect_security_risks(tree)
        assert len(risks) == 0

    def test_detect_logic_risks_clean(self, analyzer: PythonAnalyzer):
        tree = analyzer._parser.parse_code("x = 1\nprint(x)\n", "python")
        risks = analyzer.detect_logic_risks(tree)
        assert len(risks) == 0

    def test_detect_architecture_risks_clean(self, analyzer: PythonAnalyzer):
        tree = analyzer._parser.parse_code("def foo(): pass\n", "python")
        risks = analyzer.detect_architecture_risks(tree)
        assert len(risks) == 0

    def test_detect_security_risks_returns_risks(self, analyzer: PythonAnalyzer):
        tree = analyzer._parser.parse_code('password = "secret"\n', "python")
        risks = analyzer.detect_security_risks(tree)
        assert len(risks) > 0
        assert all(r.category == RiskCategory.SECURITY for r in risks)

    def test_detect_logic_risks_returns_risks(self, analyzer: PythonAnalyzer):
        tree = analyzer._parser.parse_code("def foo(items=[]): pass\n", "python")
        risks = analyzer.detect_logic_risks(tree)
        assert len(risks) > 0
        assert all(r.category == RiskCategory.LOGIC for r in risks)

    def test_detect_architecture_risks_returns_risks(self, analyzer: PythonAnalyzer):
        methods = "\n".join([f"    def m{i}(self): pass" for i in range(11)])
        code = f"class Big:\n{methods}\n"
        tree = analyzer._parser.parse_code(code, "python")
        risks = analyzer.detect_architecture_risks(tree)
        assert len(risks) > 0
        assert all(r.category == RiskCategory.ARCHITECTURE for r in risks)


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_code(self, analyzer: PythonAnalyzer):
        risks = analyzer.analyze_code("")
        assert isinstance(risks, list)
        assert len(risks) == 0

    def test_syntax_error_no_crash(self, analyzer: PythonAnalyzer):
        code = "def foo(:\n    pass\n"
        risks = analyzer.analyze_code(code)
        assert isinstance(risks, list)

    def test_multiple_risks(self, analyzer: PythonAnalyzer):
        code = (
            'password = "secret"\n'
            "result = eval(input())\n"
            "try:\n    pass\nexcept:\n    pass\n"
        )
        risks = analyzer.analyze_code(code)
        assert len(risks) >= 3
        categories = {r.category for r in risks}
        assert RiskCategory.SECURITY in categories
        assert RiskCategory.LOGIC in categories

    def test_risk_has_suggestion(self, analyzer: PythonAnalyzer):
        code = 'password = "secret"\n'
        risks = analyzer.analyze_code(code)
        assert all(r.suggestion is not None for r in risks)

    def test_risk_has_line_number(self, analyzer: PythonAnalyzer):
        code = 'password = "secret"\n'
        risks = analyzer.analyze_code(code)
        assert all(r.line_number is not None for r in risks)

    def test_risk_file_path_placeholder(self, analyzer: PythonAnalyzer):
        code = 'password = "secret"\n'
        risks = analyzer.analyze_code(code)
        assert all(r.file_path == "<string>" for r in risks)


# ---------------------------------------------------------------------------
# Integration
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_full_analysis(self, analyzer: PythonAnalyzer):
        code = '''"""Module with multiple risks."""

import pickle

password = "hardcoded_secret"

def process_data(data=[]):
    """Process data with mutable default."""
    try:
        result = eval(data)
    except:
        pass
    
    query = "SELECT * FROM users WHERE id = " + str(data)
    return result

class UserManager:
    def method1(self): pass
    def method2(self): pass
    def method3(self): pass
    def method4(self): pass
    def method5(self): pass
    def method6(self): pass
    def method7(self): pass
    def method8(self): pass
    def method9(self): pass
    def method10(self): pass
    def method11(self): pass
'''
        risks = analyzer.analyze_code(code)
        assert len(risks) > 0

        categories = {r.category for r in risks}
        assert RiskCategory.SECURITY in categories
        assert RiskCategory.LOGIC in categories
        assert RiskCategory.ARCHITECTURE in categories

        # Check specific risks
        messages = [r.message for r in risks]
        assert any("Hardcoded secret" in m for m in messages)
        assert any("eval()" in m for m in messages)
        assert any("pickle" in m.lower() for m in messages)
        assert any("SQL injection" in m for m in messages)
        assert any("Mutable default" in m for m in messages)
        assert any("except" in m.lower() for m in messages)
        assert any("God Class" in m for m in messages)


class TestPickleLoadDetection:
    """Test detection of pickle.loads/pickle.load calls."""

    def test_pickle_loads_detected(self, analyzer: PythonAnalyzer):
        """pickle.loads() call should be detected as security risk."""
        code = """
import pickle
data = pickle.loads(user_input)
"""
        risks = analyzer.analyze_code(code)
        pickle_risks = [r for r in risks if "pickle" in r.message.lower()]
        assert len(pickle_risks) > 0
        assert pickle_risks[0].category == RiskCategory.SECURITY

    def test_pickle_load_detected(self, analyzer: PythonAnalyzer):
        """pickle.load() call should be detected as critical risk."""
        code = """
import pickle
data = pickle.load(open("file.pkl", "rb"))
"""
        risks = analyzer.analyze_code(code)
        pickle_risks = [r for r in risks if "pickle" in r.message.lower()]
        assert len(pickle_risks) > 0


class TestEmptyExceptBlock:
    """Test detection of empty except blocks."""

    def test_empty_except_detected(self, analyzer: PythonAnalyzer):
        """Empty except block should be detected."""
        code = """
try:
    risky_operation()
except Exception:
    pass
"""
        risks = analyzer.analyze_code(code)
        except_risks = [r for r in risks if "except" in r.message.lower()]
        assert len(except_risks) > 0
        assert except_risks[0].category == RiskCategory.LOGIC
