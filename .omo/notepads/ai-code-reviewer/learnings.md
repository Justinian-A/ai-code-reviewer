## Terminal Reporter Implementation (2025-06-01)

### Project Conventions
- Python 3.11+ with `from __future__ import annotations` for type hints
- Pydantic v2 for data models with `BaseModel`
- Test fixtures follow `sample_*` naming pattern
- Tests use class-based organization (e.g., `TestPrintRisks`)
- Rich library available as dependency (`rich>=13.0`)
- `Console(record=True, force_terminal=True)` for capturing output in tests
- `console.export_text()` for extracting plain text from Rich console

### Design Decisions
- TerminalReporter accepts optional `Console` for testability
- RISK_COLORS/RISK_LABELS as module-level dicts (not class attributes) for easy import
- Empty list inputs show green "âœ“ No ..." messages (consistent UX)
- Risk suggestions printed below the table, not inside it
- Progress bar returned as `Progress` context manager, not pre-configured

### Test Patterns
- 49 tests covering: constants, init, each print method, edge cases
- Fixtures: `console`, `reporter`, `sample_pr`, `sample_risks`, `sample_suggestions`, `sample_cost`
- `get_output(console)` helper to extract text
- Empty input tests verify graceful handling
## User Documentation (2026-05-29)

### Documentation Structure
- README.md: Project overview, quick start, features, installation, configuration, usage, development
- docs/installation.md: Requirements, install methods, GitHub/AI token setup, troubleshooting
- docs/configuration.md: YAML config reference, env vars, CLI config commands, full example
- docs/usage.md: CLI commands, output formats, risk levels/categories, analysis modes, exit codes
- docs/examples.md: Real-world examples, CI/CD integration, Python API reference, data models, FAQ

### Key Project Details
- CLI entry point: i-code-reviewer via Click framework
- Main commands: nalyze (PR analysis), config (init/show/set)
- Hybrid analysis: AST (tree-sitter) + AI (LiteLLM for DeepSeek/Claude/OpenAI)
- Output formats: terminal (Rich), markdown, JSON
- Languages supported: Python, JavaScript, TypeScript
- Risk categories: security, logic, architecture
- Risk levels: critical > high > medium > low > info
- Config precedence: env vars (AI_CODE_REVIEWER_*) > YAML > defaults
- Python 3.11+ required, uses Pydantic v2 for models

### Documentation Conventions
- No em dashes, use commas or periods
- Avoid AI-sounding phrases
- Tables for structured reference data
- Code blocks with language tags
- Practical examples over abstract descriptions

## Test Coverage Task (2026-05-29)

### Coverage Results
- **Before**: 95% (618 tests)
- **After**: 99% (736 tests, +118 new tests)

### Files Modified
1. tests/test_main.py - Added tests for _mask, publish/preview, JSON-to-file, config_set boolean/integer, config_init overwrite
2. tests/test_config.py - Added tests for _env_int, validator passthrough, _apply_env_overrides, Config.load scenarios
3. tests/test_github.py - Added tests for decoded_content fallback, GithubException in get_pr_files/get_file_content/create_review
4. tests/test_ai.py - Added tests for generic exception wrapping, malformed risk entry skipping
5. tests/test_error_handler.py - Added tests for handle_github_error/handle_ai_error fallback paths
6. tests/test_js_ts_analyzer.py - Added tests for parse failure returning empty list
7. tests/test_python_analyzer.py - Added tests for pickle.loads detection, empty except block
8. tests/test_risk_detector.py - Added tests for unsupported language returning empty

### Files Created
1. tests/integration/__init__.py
2. tests/integration/test_end_to_end.py - End-to-end CLI tests (analyze terminal/json/markdown, config commands, error handling)
3. tests/integration/test_analyzer_pipeline.py - Analyzer pipeline tests (RiskDetector, SummaryGenerator, ReviewGenerator, HybridAnalyzer)

### Key Learnings
- _retry_on_rate_limit decorator lines 109-139 are dead code: methods catch GithubException internally and map to custom exceptions before the decorator can see them
- SummaryGenerator language is set in __init__, not in generate_summary()
- detect_issues() returns a list of Risk objects directly, not an AnalysisResult
- socket.timeout line 198 in error_handler.py appears unreachable in test environment
- SummaryGenerator lines 229, 248 (fallback returns) are dead code since all ChangeType values are covered by if-chain

## Manual QA Testing (2026-05-29)

### QA Results Summary
- **³¡¾°**: 19/21 pass (90%)
- **¼¯³É**: 4/4 (CLI, Config, Analyze, Env Vars)
- **±ßÔµ°¸Àý**: 8 tested
- **½áÂÛ**: CLI functional with 2 bugs found

### Test Scenarios

#### CLI Help Commands (4/4 PASS)
| # | Command | Result | Notes |
|---|---------|--------|-------|
| 1 | --help | ? PASS | Shows usage, commands (analyze, config) |
| 2 | --version | ? PASS | Shows "ai-code-reviewer, version 0.1.0" |
| 3 | config --help | ? PASS | Shows subcommands (init, set, show) |
| 4 | nalyze --help | ? PASS | Shows all options (-f, -o, -p, --preview, -l, --config) |

#### Config Commands (6/8 PASS, 2 BUGS)
| # | Command | Result | Notes |
|---|---------|--------|-------|
| 1 | config init | ? PASS | Correctly prompts for overwrite when file exists |
| 2 | config show (no --config) | ?? BUG | Does NOT load config/default.yaml; only shows env vars + defaults |
| 3 | config show --config config/default.yaml | ? PASS | Shows config with masked secrets |
| 4 | config set github.token "test-token-1234" | ? PASS | Writes to YAML file correctly |
| 5 | config set ai.provider "claude" | ? PASS | Nested string value |
| 6 | config set analysis.enable_ast "false" | ? PASS | Auto-casts to boolean |
| 7 | config set ai.max_tokens "8192" | ? PASS | Auto-casts to integer |
| 8 | config set github.token "" | ? BUG | Empty value rejected by Click (Missing argument 'VALUE') |

#### Analyze Command (7/7 PASS)
| # | Command | Result | Notes |
|---|---------|--------|-------|
| 1 | nalyze "not-a-valid-url" | ? PASS | Error: Invalid PR URL format |
| 2 | nalyze "https://github.com/o/r/pull/123" | ? PASS | Shows missing tokens error |
| 3 | nalyze ... --config config/default.yaml | ? PASS | Only shows missing AI key (github token loaded) |
| 4 | nalyze "https://gitlab.com/..." | ? PASS | Error: Non-GitHub URL rejected |
| 5 | nalyze "https://github.com/o/r/pull/abc" | ? PASS | Error: Non-numeric PR number |
| 6 | nalyze (no args) | ? PASS | Error: Missing PR_URL argument |
| 7 | nalyze "http://github.com/o/r/pull/123" | ? PASS | HTTP URLs accepted (regex allows https?) |

#### Environment Variables (1/1 PASS)
| # | Test | Result | Notes |
|---|------|--------|-------|
| 1 | AI_CODE_REVIEWER_GITHUB_TOKEN | ? PASS | Correctly overrides config in config show |

#### Edge Cases Tested (8)
1. Trailing slash URL: https://github.com/owner/repo/pull/123/ ¡ú Passes (regex match, harmless)
2. Invalid key format: config set invalidkey "value" ¡ú Error: requires dot notation
3. Too many dot parts: config set "a.b.c" "value" ¡ú Error: requires 2 parts
4. Invalid provider: config set ai.provider "invalid-provider" ¡ú Accepted, but crashes config show --config with Pydantic ValidationError
5. Empty value: config set key "" ¡ú Click rejects (Missing argument)
6. Non-GitHub URL: https://gitlab.com/... ¡ú Error: Invalid PR URL
7. Non-numeric PR: pull/abc ¡ú Error: Invalid PR URL
8. Missing PR_URL argument ¡ú Error: Missing argument

### Bugs Found

**BUG-1: config show without --config ignores config/default.yaml** (Severity: Medium)
- Location: config.py:167-189 (Config.load())
- Root cause: Config.load(None) sets yaml_data = {} and never loads the default YAML file
- Config.from_yaml(None) correctly defaults to DEFAULT_CONFIG_PATH, but Config.load() does not
- Fix: In Config.load(), when config_path is None, fallback to DEFAULT_CONFIG_PATH
- Impact: Users cannot see their saved config with config show unless they pass --config

**BUG-2: config set accepts invalid values without validation** (Severity: Medium)
- Location: main.py:288-332 (config_set())
- Root cause: config set writes raw values to YAML without validating against Pydantic models
- Example: config set ai.provider "invalid-provider" succeeds, but later config show --config crashes
- Fix: Validate value against Pydantic model field before writing, or catch ValidationError on load
- Impact: Users can create invalid config files that crash the application

**BUG-3: config set key "" fails with Click error** (Severity: Low)
- Location: main.py:287 - Click treats "" as empty argument
- Root cause: Click framework behavior; empty string is parsed as missing argument
- Workaround: Use config set key " " or handle specially
- Impact: Cannot set empty string values (e.g., clearing a token)
