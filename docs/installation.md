# Installation Guide

## Requirements

- Python 3.11 or higher
- pip (Python package manager)
- GitHub Personal Access Token
- AI provider API key (DeepSeek, Claude, or OpenAI)

## Install from PyPI

```bash
pip install ai-code-reviewer
```

## Install from Source

```bash
git clone https://github.com/your-org/ai-code-reviewer.git
cd ai-code-reviewer
pip install -e .
```

## Development Installation

For contributors and developers:

```bash
git clone https://github.com/your-org/ai-code-reviewer.git
cd ai-code-reviewer
pip install -e ".[dev]"
```

This installs additional tools: pytest, black, ruff, mypy.

## Verify Installation

```bash
ai-code-reviewer --version
```

Expected output: `ai-code-reviewer, version 0.1.0`

## Get a GitHub Token

1. Go to GitHub Settings > Developer settings > Personal access tokens
2. Click "Generate new token (classic)"
3. Select scopes: `repo` (full control of private repositories)
4. Copy the token

## Get an AI API Key

Pick one provider:

**DeepSeek** (recommended, cost-effective):
- Sign up at https://platform.deepseek.com
- Create an API key in the dashboard

**Claude**:
- Sign up at https://console.anthropic.com
- Create an API key

**OpenAI**:
- Sign up at https://platform.openai.com
- Create an API key in API keys section

## Initial Setup

```bash
# Create config file
ai-code-reviewer config init

# Set your GitHub token
ai-code-reviewer config set github.token "ghp_your_token_here"

# Set your AI provider and key
ai-code-reviewer config set ai.provider "deepseek"
ai-code-reviewer config set ai.api_key "sk_your_key_here"

# Verify configuration
ai-code-reviewer config show
```

## Troubleshooting

### "Python version" error

AI Code Reviewer requires Python 3.11+. Check your version:

```bash
python --version
```

If you have multiple Python versions, use:

```bash
python3.11 -m pip install ai-code-reviewer
```

### "Command not found" error

If `ai-code-reviewer` is not found after install, ensure your pip scripts directory is in PATH:

```bash
# Check where pip installs scripts
python -m site --user-base

# Add the Scripts subdirectory to PATH
# Windows: %APPDATA%\Python\Python311\Scripts
# macOS/Linux: ~/.local/bin
```

### GitHub API rate limits

Unauthenticated GitHub API has a 60 requests/hour limit. With a token, you get 5,000. If you see rate limit errors, make sure your token is set correctly.

### AI API errors

Common causes:
- Invalid API key
- Insufficient credits/quota
- Network connectivity issues

Run `ai-code-reviewer config show` to verify your key is set (masked output).
