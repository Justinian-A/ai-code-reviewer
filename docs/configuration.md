# Configuration Reference

AI Code Reviewer uses a YAML configuration file with environment variable overrides.

## Config File Location

Default: `config/default.yaml` (relative to working directory)

Custom path via CLI:

```bash
ai-code-reviewer analyze <pr_url> --config /path/to/config.yaml
```

## Initialize Config

```bash
ai-code-reviewer config init
```

Creates `config/default.yaml` with sensible defaults.

## Configuration Sections

### github

GitHub API access.

```yaml
github:
  token: "ghp_xxxxxxxxxxxx"
```

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `token` | string | `""` | GitHub Personal Access Token |

Env var: `AI_CODE_REVIEWER_GITHUB_TOKEN`

### ai

AI provider settings.

```yaml
ai:
  provider: "deepseek"
  api_key: "sk-xxxxxxxxxxxx"
  model: "deepseek-chat"
  max_tokens: 4096
```

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `provider` | string | `"deepseek"` | AI provider: `deepseek`, `claude`, `openai` |
| `api_key` | string | `""` | API key for the provider |
| `model` | string | `"deepseek-chat"` | Model name |
| `max_tokens` | int | `4096` | Max tokens in AI response |

Env vars: `AI_CODE_REVIEWER_AI_PROVIDER`, `AI_CODE_REVIEWER_AI_API_KEY`, `AI_CODE_REVIEWER_AI_MODEL`, `AI_CODE_REVIEWER_AI_MAX_TOKENS`

#### Provider Defaults

If you don't specify a model, these defaults are used:

| Provider | Default Model |
|----------|--------------|
| deepseek | `deepseek-chat` |
| claude | `claude-sonnet-4-20250514` |
| openai | `gpt-4o` |

### analysis

Analysis engine toggles.

```yaml
analysis:
  enable_ast: true
  enable_ai: true
```

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enable_ast` | bool | `true` | Enable AST-based static analysis |
| `enable_ai` | bool | `true` | Enable AI-powered analysis |

Env vars: `AI_CODE_REVIEWER_ENABLE_AST`, `AI_CODE_REVIEWER_ENABLE_AI`

Set `enable_ai: false` to skip LLM calls (useful for fast, offline-only checks).

### output

Output preferences.

```yaml
output:
  format: "terminal"
```

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `format` | string | `"terminal"` | Output format: `terminal`, `markdown`, `json` |

Env var: `AI_CODE_REVIEWER_OUTPUT_FORMAT`

## Environment Variable Precedence

Environment variables always override config file values. This is useful for CI/CD:

```bash
export AI_CODE_REVIEWER_GITHUB_TOKEN="ghp_ci_token"
export AI_CODE_REVIEWER_AI_API_KEY="sk_ci_key"
ai-code-reviewer analyze https://github.com/org/repo/pull/42
```

All env vars use the prefix `AI_CODE_REVIEWER_`.

## CLI Config Commands

### config init

```bash
ai-code-reviewer config init
```

Creates or overwrites `config/default.yaml` with defaults.

### config show

```bash
ai-code-reviewer config show
```

Displays current config. Secrets are masked (only last 4 chars shown).

### config set

```bash
ai-code-reviewer config set <key> <value>
```

Key uses dot notation: `github.token`, `ai.provider`, `analysis.enable_ast`, etc.

Examples:

```bash
ai-code-reviewer config set github.token "ghp_xxx"
ai-code-reviewer config set ai.provider "claude"
ai-code-reviewer config set ai.model "claude-sonnet-4-20250514"
ai-code-reviewer config set analysis.enable_ast false
ai-code-reviewer config set output.format "json"
```

Boolean values: `true`, `false` (case-insensitive).

Integer values: parsed automatically.

## Full Config Example

```yaml
# config/default.yaml

github:
  token: "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

ai:
  provider: "claude"
  api_key: "sk-ant-xxxxxxxxxxxxxxxxxxxxxxxx"
  model: "claude-sonnet-4-20250514"
  max_tokens: 8192

analysis:
  enable_ast: true
  enable_ai: true

output:
  format: "markdown"
```
