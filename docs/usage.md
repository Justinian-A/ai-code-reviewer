# Usage Guide

## CLI Overview

```
ai-code-reviewer [command] [options]
```

Commands:

- `analyze` - Analyze a GitHub pull request
- `config` - Manage configuration (`init`, `show`, `set`)

## Analyzing a Pull Request

### Basic Usage

```bash
ai-code-reviewer analyze https://github.com/owner/repo/pull/123
```

The tool fetches the PR, runs analysis, and prints results to the terminal.

### PR URL Format

The URL must match:

```
https://github.com/{owner}/{repo}/pull/{number}
```

### Output Formats

**Terminal** (default): Colored, structured output in your terminal.

```bash
ai-code-reviewer analyze https://github.com/owner/repo/pull/123
```

**Markdown**: Generates a Markdown report.

```bash
ai-code-reviewer analyze https://github.com/owner/repo/pull/123 -f markdown
```

**JSON**: Machine-readable JSON output.

```bash
ai-code-reviewer analyze https://github.com/owner/repo/pull/123 -f json
```

### Save to File

Use `-o` to write output to a file instead of stdout:

```bash
ai-code-reviewer analyze https://github.com/owner/repo/pull/123 -f markdown -o review.md
ai-code-reviewer analyze https://github.com/owner/repo/pull/123 -f json -o review.json
```

### Publish to GitHub

Post the review as a comment on the PR:

```bash
ai-code-reviewer analyze https://github.com/owner/repo/pull/123 --publish
```

Preview before publishing (prints the review without posting):

```bash
ai-code-reviewer analyze https://github.com/owner/repo/pull/123 --preview
```

### Language

Generate reports in Chinese:

```bash
ai-code-reviewer analyze https://github.com/owner/repo/pull/123 -l zh
```

Default is English (`-l en`).

### Custom Config

Use a specific config file:

```bash
ai-code-reviewer analyze https://github.com/owner/repo/pull/123 --config ./my-config.yaml
```

## Command Reference

### `analyze`

```
ai-code-reviewer analyze <PR_URL> [options]
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--output-format` | `-f` | `terminal` | Output format: `terminal`, `markdown`, `json` |
| `--output-file` | `-o` | stdout | Write output to file |
| `--publish` | `-p` | off | Publish review to GitHub PR |
| `--preview` | | off | Preview review without publishing |
| `--language` | `-l` | `en` | Report language: `en`, `zh` |
| `--config` | | default | Path to YAML config file |

### `config init`

```bash
ai-code-reviewer config init
```

Creates `config/default.yaml` with default values.

### `config show`

```bash
ai-code-reviewer config show
```

Prints current configuration. Secrets are masked.

### `config set`

```bash
ai-code-reviewer config set <key> <value>
```

Sets a config value. Key uses dot notation (e.g., `ai.provider`).

## Analysis Output

### Terminal Output

The terminal report includes:

1. **PR Summary**: Title, author, branch info, file count
2. **Change Summary**: What the PR does
3. **Risks Found**: Sorted by severity (critical first)
4. **Suggestions**: Actionable review comments
5. **Cost Report**: Token usage and estimated cost (when AI is enabled)

### Markdown Output

A structured Markdown document with sections for summary, risks, and suggestions. Suitable for pasting into GitHub issues or documentation.

### JSON Output

Machine-readable JSON with the full `AnalysisResult` model:

```json
{
  "pr": { "number": 123, "title": "...", "author": "...", ... },
  "files_changed": [...],
  "risks": [
    {
      "level": "high",
      "category": "security",
      "message": "Potential SQL injection...",
      "file_path": "src/db.py",
      "line_number": 42,
      "suggestion": "Use parameterized queries"
    }
  ],
  "suggestions": [...],
  "cost": { "input_tokens": 1234, "output_tokens": 567, "total_cost_usd": 0.01 },
  "summary": "This PR adds user authentication...",
  "analyzed_at": "2026-05-29T12:00:00Z"
}
```

## Risk Levels

| Level | Meaning |
|-------|---------|
| `critical` | Must fix before merge. Security holes, data loss risks. |
| `high` | Should fix. Logic bugs, error handling gaps. |
| `medium` | Consider fixing. Code quality, maintainability. |
| `low` | Nice to have. Minor improvements. |
| `info` | FYI only. Style notes, observations. |

## Risk Categories

| Category | What It Catches |
|----------|----------------|
| `security` | SQL injection, XSS, hardcoded secrets, insecure crypto, path traversal |
| `logic` | Null dereference, off-by-one, race conditions, missing error handling |
| `architecture` | Tight coupling, circular deps, SOLID violations, god classes |

## Analysis Modes

### AST-only Mode

Disable AI for fast, offline analysis:

```bash
ai-code-reviewer config set analysis.enable_ai false
ai-code-reviewer analyze https://github.com/owner/repo/pull/123
```

Good for: CI pipelines, cost savings, air-gapped environments.

### AI-only Mode

Disable AST for pure LLM analysis:

```bash
ai-code-reviewer config set analysis.enable_ast false
ai-code-reviewer analyze https://github.com/owner/repo/pull/123
```

### Hybrid Mode (Default)

Both enabled. AST catches structural issues, AI catches semantic issues. Results are merged and deduplicated.

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (missing config, invalid URL, API failure) |
