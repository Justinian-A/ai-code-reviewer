# AI Code Reviewer Web界面

AI Code Reviewer提供了一个基于FastAPI的Web界面，用于分析GitHub Pull Request。

## 功能特性

- **PR分析**：输入GitHub PR URL，自动分析代码风险和建议
- **历史记录**：查看和管理历史分析记录
- **配置管理**：管理GitHub Token和AI API Key
- **成本统计**：查看API使用量和成本统计

## 安装

```bash
# 安装Web依赖
pip install -e ".[web]"

# 或者单独安装Web依赖
pip install fastapi uvicorn jinja2 python-multipart
```

## 启动

```bash
# 使用命令行启动
python -m ai_code_reviewer.web

# 或者使用脚本
python scripts/start_web.py
```

默认访问地址：http://localhost:8080

## 使用方法

1. 访问 http://localhost:8080
2. 配置GitHub Token和AI API Key
3. 输入PR URL进行分析
4. 查看分析结果

## API端点

### 健康检查

```
GET /api/health
```

返回服务状态和版本信息。

### 分析PR

```
POST /api/analyze
Content-Type: application/json

{
  "pr_url": "https://github.com/owner/repo/pull/123"
}
```

启动后台分析任务，返回分析ID。

### 获取分析结果

```
GET /api/analyses/{analysis_id}
```

获取指定分析的详细结果。

### 列出历史记录

```
GET /api/analyses?limit=50&offset=0
```

列出历史分析记录，支持分页。

### 删除分析记录

```
DELETE /api/analyses/{analysis_id}
```

删除指定的分析记录及其关联的成本记录。

### 获取配置

```
GET /api/config
```

获取当前配置（敏感信息已脱敏）。

### 更新配置

```
PUT /api/config
Content-Type: application/json

{
  "github_token": "ghp_xxx",
  "ai_provider": "deepseek",
  "ai_api_key": "sk-xxx",
  "ai_model": "deepseek-chat",
  "ai_max_tokens": 4096
}
```

### 测试配置

```
POST /api/config/test
```

测试当前配置的有效性。

### 获取成本统计

```
GET /api/costs?days=30
```

获取指定时间段的成本统计。

### 获取成本摘要

```
GET /api/costs/summary
```

获取所有分析的总成本摘要。

## 配置说明

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `github_token` | GitHub访问令牌 | 空 |
| `ai_provider` | AI提供商 | `deepseek` |
| `ai_api_key` | AI API密钥 | 空 |
| `ai_model` | AI模型 | `deepseek-v4-flash` |
| `ai_max_tokens` | 最大token数 | `4096` |

## 开发

```bash
# 运行测试
pytest tests/web/

# 启动开发服务器（带热重载）
uvicorn ai_code_reviewer.web.app:app --reload --host 0.0.0.0 --port 8080
```

## 架构

```
src/ai_code_reviewer/web/
├── app.py              # FastAPI应用主文件
├── database.py         # SQLite数据库操作
├── models.py           # 数据模型
├── __main__.py         # 启动入口
├── routers/
│   ├── analysis.py     # 分析相关API
│   ├── config.py       # 配置相关API
│   ├── costs.py        # 成本相关API
│   └── history.py      # 历史记录API
├── static/             # 静态资源
│   ├── css/
│   └── js/
└── templates/          # HTML模板
    ├── index.html
    ├── analyze.html
    ├── config.html
    ├── costs.html
    └── history.html
```
