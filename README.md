# AI Code Reviewer - AI 代码评审助手

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18+-61DAFB.svg)](https://reactjs.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> 🤖 AI 辅助代码评审工具，自动分析 GitHub Pull Request，识别潜在问题，提供专业的评审建议

## ✨ 功能特性

- 📋 **变更总结** - 自动分析 PR 变更内容，生成结构化摘要
- ⚠️ **风险识别** - 识别潜在 Bug、安全漏洞、性能问题
- 💡 **改进建议** - 针对具体代码行给出优化建议
- 📊 **历史记录** - 保存分析历史，支持对比查看
- 🖥️ **桌面应用** - 支持打包成桌面软件，双击即用

## 🚀 快速开始

### 方式一：桌面版（推荐）

1. 下载项目
2. 双击 `启动器.py` 或 `快速启动.bat`
3. 浏览器自动打开 http://localhost:8000

### 方式二：手动启动

```bash
# 1. 安装后端依赖
cd backend
pip install -r requirements.txt

# 2. 构建前端
cd ../frontend
npm install
npm run build

# 3. 启动服务
cd ../backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 4. 访问 http://localhost:8000
```

### 方式三：Docker 部署

```bash
# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API Key

# 启动
docker-compose up -d

# 访问 http://localhost
```

## 📖 使用方法

1. 访问首页，输入 GitHub PR 链接
2. 填入 GitHub Token（推荐，避免 API 频率限制）
3. 点击「开始分析」
4. 等待 AI 分析完成（约 1-2 分钟）
5. 查看分析报告

### 获取 GitHub Token

1. 访问 https://github.com/settings/tokens
2. 点击「Generate new token」
3. 选择权限：`repo`（全部）
4. 生成并复制 Token

## 🏗️ 技术架构

```
┌─────────────────────────────────────────────────────┐
│                    用户界面层                         │
│              React + TailwindCSS                     │
└─────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│                    API 服务层                         │
│                 FastAPI (Python)                     │
│    ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│    │ 认证服务  │  │ 评审服务  │  │ GitHub   │        │
│    └──────────┘  └──────────┘  └──────────┘        │
└─────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│                    数据层                            │
│    ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│    │  SQLite  │  │ MiMo API │  │GitHub API│        │
│    └──────────┘  └──────────┘  └──────────┘        │
└─────────────────────────────────────────────────────┘
```

### 技术选型

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | React + TailwindCSS | 组件化开发，响应式设计 |
| 后端 | Python + FastAPI | 异步高性能，AI 集成方便 |
| 数据库 | SQLite | 轻量级，无需额外部署 |
| AI 模型 | MiMo v2.5 Pro | 小米推理模型，代码理解能力强 |
| GitHub | REST API | 获取 PR 数据和代码变更 |

### 设计思路

#### 模型选择

选择 MiMo v2.5 Pro 模型的原因：
- 国产模型，中文理解能力强
- 推理能力突出，适合代码分析场景
- 通过 OpenAI 兼容 API 调用，集成方便

#### 上下文获取方式

采用分层获取策略：
1. **Level 1**: PR 元数据（标题、描述、评论）
2. **Level 2**: 代码变更（diff）
3. **Level 3**: 完整文件内容（按需获取）

#### 误报与漏报控制

- 置信度评分：每个问题标注置信度（0.0-1.0）
- 分级展示：高置信度问题优先展示
- 上下文增强：获取更多上下文减少误判

## 📁 项目结构

```
ai-code-review/
├── README.md                  # 项目说明
├── PROJECT_REQUIREMENTS.md    # 需求文档
├── DEPLOYMENT.md              # 部署指南
├── 使用说明.txt               # 用户文档
├── 启动器.py                  # Python 启动器
├── 快速启动.bat               # 快速启动脚本
├── build-desktop.bat          # 打包桌面版
├── docker-compose.yml         # Docker 编排
├── .env.example               # 环境变量模板
│
├── backend/                   # 后端服务
│   ├── app/
│   │   ├── main.py            # FastAPI 主应用
│   │   ├── config.py          # 配置管理
│   │   ├── database.py        # 数据库模块
│   │   ├── api/               # API 路由
│   │   └── services/          # 业务服务
│   ├── requirements.txt       # Python 依赖
│   └── Dockerfile
│
├── frontend/                  # 前端应用
│   ├── src/
│   │   ├── pages/             # 页面组件
│   │   ├── components/        # 公共组件
│   │   └── services/          # API 服务
│   ├── package.json
│   └── Dockerfile
│
├── electron/                  # 桌面版配置
│   ├── main.js
│   └── package.json
│
└── dev-logs/                  # 开发日志
    └── 2025-05-29.md
    └── 2025-05-30.md
```

## 🗺️ 开发日志

### 2025-05-29 - 项目启动

- ✅ 需求分析与技术选型
- ✅ 后端框架搭建（FastAPI）
- ✅ 前端项目初始化（React + TailwindCSS）
- ✅ 核心功能实现
  - GitHub API 集成
  - MiMo AI 分析服务
  - PR 分析 API
  - 可视化报告页面

### 2025-05-30 - 功能优化

- ✅ 优化 MiMo prompt（提升中文输出质量）
- ✅ 添加加载动画组件
- ✅ 生产部署支持（Docker）
- ✅ 桌面版打包支持（Electron）

## 🔧 API 接口

### 评审相关

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/reviews/analyze | 创建 PR 分析任务 |
| GET | /api/reviews/history | 获取评审历史 |
| GET | /api/reviews/{id} | 获取评审详情 |
| DELETE | /api/reviews/{id} | 删除评审记录 |

### GitHub 相关

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/github/parse-url | 解析 PR URL |
| POST | /api/github/pr-info | 获取 PR 信息 |


## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 License

MIT License

## 🙏 致谢

- [FastAPI](https://fastapi.tiangolo.com/)
- [React](https://reactjs.org/)
- [TailwindCSS](https://tailwindcss.com/)
- [MiMo](https://github.com/XiaomiMiMo)

---

**开发者**: [Justinian-A](https://github.com/Justinian-A)
