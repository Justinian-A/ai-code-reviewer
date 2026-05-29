# AI Code Reviewer

基于AI的代码审查工具，专为GitHub Pull Request设计。结合AST静态分析与LLM语义审查，捕捉人工审查容易遗漏的风险代码。

## 功能特性

**核心能力**
- PR变更摘要自动生成
- 风险代码识别（安全漏洞、逻辑错误、架构问题）
- 可操作的Review建议输出
- 直接发布审查结果到GitHub PR

**语言支持**
- Python
- JavaScript / TypeScript

**AI模型**
- DeepSeek (deepseek-chat)
- Claude (claude-sonnet-4-20250514)
- GPT-4o

通过LiteLLM统一调用，切换模型只需修改配置。

**输出方式**
- 终端彩色输出（Rich）
- Markdown文件
- JSON结构化数据
- 中英文双语报告

**交互方式**
- CLI命令行工具
- Web管理界面（FastAPI + Bootstrap 5）

## 安装

**环境要求**: Python 3.11+

**通过pip安装**

```bash
pip install ai-code-reviewer
```

**从源码安装**

```bash
git clone https://github.com/Justinian-A/ai-code-reviewer.git
cd ai-code-reviewer
pip install -e .
```

**安装Web界面依赖**

```bash
pip install -e ".[web]"
```

**安装开发依赖**

```bash
pip install -e ".[dev]"
```

## 使用方法

### CLI命令行

**初始化配置**

```bash
ai-code-reviewer config init
```

**设置凭据**

```bash
ai-code-reviewer config set github.token "ghp_your_token"
ai-code-reviewer config set ai.api_key "your_api_key"
ai-code-reviewer config set ai.provider "deepseek"
```

**分析PR**

```bash
# 基本分析
ai-code-reviewer analyze https://github.com/owner/repo/pull/123

# 输出Markdown到文件
ai-code-reviewer analyze https://github.com/owner/repo/pull/123 -f markdown -o review.md

# 输出JSON
ai-code-reviewer analyze https://github.com/owner/repo/pull/123 -f json -o review.json

# 发布审查到GitHub
ai-code-reviewer analyze https://github.com/owner/repo/pull/123 --publish

# 发布前预览
ai-code-reviewer analyze https://github.com/owner/repo/pull/123 --preview

# 生成中文报告
ai-code-reviewer analyze https://github.com/owner/repo/pull/123 -l zh
```

**查看配置**

```bash
ai-code-reviewer config show
```

**环境变量**

可通过环境变量覆盖配置文件，前缀为 `AI_CODE_REVIEWER_`：

```bash
export AI_CODE_REVIEWER_GITHUB_TOKEN="ghp_xxx"
export AI_CODE_REVIEWER_AI_API_KEY="sk-xxx"
export AI_CODE_REVIEWER_AI_PROVIDER="claude"
```

### Web界面

```bash
# 安装Web依赖
pip install -e ".[web]"

# 启动服务
python -m ai_code_reviewer.web
```

访问 `http://localhost:8080`，支持：
- 输入PR URL进行在线分析
- 查看历史分析记录
- 管理API配置
- 查看用量和成本统计

详细文档见 [Web界面文档](docs/web.md)。

## 技术架构

```
┌─────────────────────────────────────────────────┐
│                   用户界面层                       │
│         CLI (Click + Rich)  │  Web (FastAPI)      │
├─────────────────────────────────────────────────┤
│                   核心引擎层                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ GitHub   │  │ AST分析器 │  │ LLM审查器 │       │
│  │ API客户端 │  │(Tree-sitter)│ │(LiteLLM) │       │
│  └──────────┘  └──────────┘  └──────────┘       │
├─────────────────────────────────────────────────┤
│                   数据层                          │
│       SQLite数据库  │  YAML配置文件               │
└─────────────────────────────────────────────────┘
```

**工作流程**

1. 从GitHub API获取PR元数据和文件差异
2. Tree-sitter进行AST解析，识别结构问题
3. 将差异发送给LLM进行语义风险检测
4. 合并、去重、优先级排序发现项
5. 生成摘要和可执行建议
6. 输出到终端、文件或GitHub

**风险分类**

| 类别 | 示例 |
|------|------|
| 安全 | SQL注入、XSS、硬编码密钥、不安全加密 |
| 逻辑 | 空引用、边界错误、竞态条件、异常处理 |
| 架构 | 紧耦合、循环依赖、SOLID违反 |

风险等级: `critical` > `high` > `medium` > `low` > `info`

## 开发指南

```bash
# 克隆仓库
git clone https://github.com/Justinian-A/ai-code-reviewer.git
cd ai-code-reviewer

# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest

# 代码检查
ruff check .

# 格式化检查
black --check .

# 类型检查
mypy src/
```

**项目结构**

```
ai-code-reviewer/
├── src/ai_code_reviewer/    # 源代码
│   ├── analyzers/           # AST分析器
│   ├── github/              # GitHub API集成
│   ├── llm/                 # LLM调用封装
│   ├── web/                 # Web界面
│   └── main.py              # CLI入口
├── tests/                   # 测试文件
├── docs/                    # 文档
├── config/                  # 配置模板
└── pyproject.toml           # 项目配置
```

## 文档

- [安装指南](docs/installation.md)
- [配置参考](docs/configuration.md)
- [使用指南](docs/usage.md)
- [示例](docs/examples.md)
- [Web界面文档](docs/web.md)

## 许可证

MIT License

## 项目地址

https://github.com/Justinian-A/ai-code-reviewer
