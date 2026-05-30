# Examples and API Reference

## Real-World Examples

### Review a Security-Focused PR

```bash
# Review with terminal output (default)
ai-code-reviewer analyze https://github.com/myorg/auth-service/pull/88

# Save as Markdown for team review
ai-code-reviewer analyze https://github.com/myorg/auth-service/pull/88 \
  -f markdown -o auth-review.md

# Post directly to GitHub
ai-code-reviewer analyze https://github.com/myorg/auth-service/pull/88 --publish
```

### CI/CD Integration

```yaml
# .github/workflows/ai-review.yml
name: AI Code Review
on:
  pull_request:
    types: [opened, synchronize]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install ai-code-reviewer
      - run: |
          ai-code-reviewer analyze \
            "${{ github.event.pull_request.html_url }}" \
            --publish
        env:
          AI_CODE_REVIEWER_GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          AI_CODE_REVIEWER_AI_API_KEY: ${{ secrets.AI_API_KEY }}
          AI_CODE_REVIEWER_AI_PROVIDER: "deepseek"
```

### Batch Review Multiple PRs

```bash
#!/bin/bash
# review-open-prs.sh - Review all open PRs in a repo

PRS=$(gh pr list --repo myorg/myrepo --json number --jq '.[].number')

for pr in $PRS; do
  echo "Reviewing PR #$pr..."
  ai-code-reviewer analyze \
    "https://github.com/myorg/myrepo/pull/$pr" \
    -f markdown \
    -o "reviews/pr-${pr}.md"
done
```

### Compare Providers

```bash
# DeepSeek (default, cost-effective)
AI_CODE_REVIEWER_AI_PROVIDER=deepseek \
  ai-code-reviewer analyze https://github.com/org/repo/pull/1 -f json > deepseek.json

# Claude
AI_CODE_REVIEWER_AI_PROVIDER=claude \
  ai-code-reviewer analyze https://github.com/org/repo/pull/1 -f json > claude.json

# GPT-4o
AI_CODE_REVIEWER_AI_PROVIDER=openai \
  ai-code-reviewer analyze https://github.com/org/repo/pull/1 -f json > gpt4o.json
```

### AST-Only (No AI Cost)

```bash
# Fast, free, offline analysis
ai-code-reviewer config set analysis.enable_ai false
ai-code-reviewer analyze https://github.com/org/repo/pull/42
```

### Chinese Report

```bash
ai-code-reviewer analyze https://github.com/org/repo/pull/42 -l zh -f markdown -o review-zh.md
```

## API Reference

### Python API

Import the core modules for programmatic use:

```python
from ai_code_reviewer.config import Config, load_config
from ai_code_reviewer.github.client import GitHubClient
from ai_code_reviewer.analyzer.hybrid_analyzer import HybridAnalyzer
from ai_code_reviewer.models import AnalysisResult, Risk, RiskLevel
```

#### Load Configuration

```python
# From default config file
config = load_config()

# From custom path
config = load_config("/path/to/config.yaml")

# From environment variables only
config = Config.from_env()

# From YAML file explicitly
config = Config.from_yaml("/path/to/config.yaml")
```

#### Fetch PR Data

```python
client = GitHubClient(token="ghp_xxx")

# Get PR metadata
pr = client.get_pull_request("owner", "repo", 42)
print(pr.title, pr.author)

# Get file changes
files = client.get_pr_files("owner", "repo", 42)
for f in files:
    print(f.file_path, f.change_type, f"+{f.additions}/-{f.deletions}")

client.close()
```

#### Run Analysis

```python
config = load_config()
analyzer = HybridAnalyzer(config)

# Analyze a full PR
result: AnalysisResult = analyzer.analyze_pr(pr, files)

# Access results
print(result.summary)
for risk in result.risks:
    print(f"[{risk.level.value}] {risk.category.value}: {risk.message}")
    print(f"  File: {risk.file_path}:{risk.line_number}")
    if risk.suggestion:
        print(f"  Suggestion: {risk.suggestion}")

for suggestion in result.suggestions:
    print(f"  {suggestion.file_path}: {suggestion.message}")

if result.cost:
    print(f"Tokens: {result.cost.input_tokens} in / {result.cost.output_tokens} out")
    print(f"Cost: ${result.cost.total_cost_usd:.4f}")
```

#### Analyze a Single File

```python
from ai_code_reviewer.models import FileChange, ChangeType

file = FileChange(
    file_path="src/auth.py",
    change_type=ChangeType.FIX,
    additions=15,
    deletions=3,
    diff_content="@@ -10,3 +10,15 @@\n+def login(user, pass):\n+    ..."
)

risks = analyzer.analyze_file(file)
for risk in risks:
    print(risk.level.value, risk.message)
```

#### Generate Reports

```python
from ai_code_reviewer.report.markdown import MarkdownReporter
from ai_code_reviewer.report.terminal import TerminalReporter

# Terminal output
terminal = TerminalReporter()
terminal.print_summary(result.pr, result.summary or "")
terminal.print_risks(result.risks)
terminal.print_suggestions(result.suggestions)
if result.cost:
    terminal.print_cost_report(result.cost)

# Markdown output
md = MarkdownReporter(language="en")
markdown_text = md.generate_report(result)
md.save_report(result, "report.md")
```

### Data Models

#### AnalysisResult

```python
class AnalysisResult(BaseModel):
    pr: PullRequest
    files_changed: List[FileChange]
    risks: List[Risk]
    suggestions: List[ReviewSuggestion]
    cost: Optional[CostReport]
    summary: Optional[str]
    analyzed_at: datetime
```

#### Risk

```python
class Risk(BaseModel):
    level: RiskLevel        # critical, high, medium, low, info
    category: RiskCategory  # security, logic, architecture
    message: str
    file_path: str
    line_number: Optional[int]
    suggestion: Optional[str]
```

#### PullRequest

```python
class PullRequest(BaseModel):
    number: int
    title: str
    description: Optional[str]
    author: str
    repository: str
    base_branch: str
    head_branch: str
    created_at: datetime
    updated_at: datetime
```

#### FileChange

```python
class FileChange(BaseModel):
    file_path: str
    change_type: ChangeType  # feature, fix, refactor, docs, test, chore
    additions: int
    deletions: int
    diff_content: Optional[str]
    language: Optional[str]
```

#### CostReport

```python
class CostReport(BaseModel):
    input_tokens: int
    output_tokens: int
    total_cost_usd: float
    model_name: Optional[str]
```

## Common Patterns

### Pre-merge Check Script

```bash
#!/bin/bash
# pre-merge-check.sh - Review PR and fail if critical risks found

RESULT=$(ai-code-reviewer analyze "$1" -f json 2>/dev/null)
CRITICAL=$(echo "$RESULT" | python -c "
import sys, json
data = json.load(sys.stdin)
count = sum(1 for r in data['risks'] if r['level'] == 'critical')
print(count)
")

if [ "$CRITICAL" -gt 0 ]; then
  echo "❌ Found $CRITICAL critical risks. Review required."
  exit 1
fi

echo "✅ No critical risks found."
```

### Custom Report Template

```python
import json
from ai_code_reviewer.config import load_config
from ai_code_reviewer.github.client import GitHubClient
from ai_code_reviewer.analyzer.hybrid_analyzer import HybridAnalyzer

def custom_review(owner: str, repo: str, pr_num: int) -> str:
    config = load_config()
    gh = GitHubClient(token=config.github.token)
    pr = gh.get_pull_request(owner, repo, pr_num)
    files = gh.get_pr_files(owner, repo, pr_num)
    gh.close()

    analyzer = HybridAnalyzer(config)
    result = analyzer.analyze_pr(pr, files)

    lines = [
        f"# Review: {pr.title}",
        f"Author: {pr.author}",
        f"Files: {len(files)}",
        "",
        "## Risks",
    ]
    for r in result.risks:
        lines.append(f"- **{r.level.value}** [{r.category.value}] {r.message}")

    return "\n".join(lines)
```

## Frequently Asked Questions

### Q: How much does it cost per review?

Depends on PR size and provider. A typical 10-file PR costs roughly:
- DeepSeek: $0.01-0.03
- Claude: $0.05-0.15
- GPT-4o: $0.05-0.20

Use `--preview` or `-f json` to check the `cost` field.

### Q: Can I use it without AI?

Yes. Disable AI analysis:

```bash
ai-code-reviewer config set analysis.enable_ai false
```

This runs AST-only analysis, which is free and works offline.

### Q: Does it work with private repos?

Yes, as long as your GitHub token has access to the repository.

### Q: What languages are supported?

Python, JavaScript, and TypeScript. The AST analyzers handle these. AI analysis works on any language (it reads the diff text).

### Q: Can I use multiple AI providers?

Not simultaneously. Set one provider at a time. Switch via config:

```bash
ai-code-reviewer config set ai.provider "claude"
```

Or use environment variables per invocation.

### Q: How do I debug issues?

Check config first:

```bash
ai-code-reviewer config show
```

Common issues:
- Empty token: `github.token` or `AI_CODE_REVIEWER_GITHUB_TOKEN` not set
- Wrong API key: provider key doesn't match the configured provider
- Rate limits: GitHub (5000/hr with token) or AI provider quotas

### Q: Can I customize the prompts?

Not via config. The prompts are built into the codebase at `src/ai_code_reviewer/ai/prompts.py`. Fork the project to customize.
