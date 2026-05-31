# AI Code Reviewer - AI 代码评审助手

基于 AI 的 GitHub Pull Request 代码评审工具，帮助开发者提升 Review 效率与质量。

## ✨ 功能特性

- 🤖 **AI 智能分析** - 使用 MiMo 模型分析代码变更
- 📊 **风险识别** - 自动识别 Bug、安全漏洞、性能问题
- 💡 **改进建议** - 提供具体的代码优化建议
- 📝 **变更总结** - 自动生成 PR 变更摘要
- 🔍 **问题筛选** - 按严重程度、类别筛选问题
- 🎨 **代码高亮** - Diff 视图和语法高亮
- 🌙 **暗色模式** - 支持深色主题
- 👤 **用户系统** - 注册登录、个人记录管理

## 🎬 演示视频

[![演示视频](https://img.shields.io/badge/▶_观看演示视频-red?style=for-the-badge&logo=youtube)](https://github.com/Justinian-A/ai-code-reviewer/blob/main/demo.mp4)

> 点击上方按钮观看项目演示视频，或直接下载 [demo.mp4](demo.mp4)

## 🚀 快速开始

### 前置要求

- Python 3.8+
- Node.js 16+

### 安装与运行

**Windows 用户（推荐）**

```bash
# 1. 克隆项目
git clone https://github.com/Justinian-A/ai-code-reviewer.git
cd ai-code-reviewer

# 2. 双击启动
快速启动.bat
```

**手动启动**

```bash
# 终端 1：启动后端
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 终端 2：启动前端
cd frontend
npm install
npm run dev
```

**访问应用**: http://localhost:3000

## 📖 使用方法

### 1. 注册登录
- 首次使用需注册账号
- 登录后可管理个人分析记录

### 2. 分析 PR
1. 在首页输入 GitHub PR 链接
   ```
   https://github.com/用户名/仓库/pull/PR编号
   ```
2. （可选）输入 GitHub Token（用于私有仓库）
3. 点击"开始分析"

### 3. 查看结果
- **变更总结** - PR 做了什么改动
- **风险等级** - 高/中/低
- **问题列表** - 按严重程度分类
- **改进建议** - 具体的代码建议
- **代码变更** - Diff 视图

### 4. 筛选问题
- 点击统计卡片按严重程度筛选
- 点击类别标签按类型筛选
- 再次点击取消筛选

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 18 + TailwindCSS + Vite |
| 后端 | Python + FastAPI |
| 数据库 | SQLite + aiosqlite |
| AI 模型 | MiMo v2.5 Pro |
| GitHub | REST API |

## 📁 项目结构

```
ai-code-review/
├── backend/                # 后端服务
│   ├── app/
│   │   ├── api/           # API 路由
│   │   ├── services/      # 业务服务
│   │   ├── main.py        # 应用入口
│   │   ├── config.py      # 配置管理
│   │   └── database.py    # 数据库
│   └── requirements.txt
├── frontend/               # 前端界面
│   ├── src/
│   │   ├── pages/         # 页面组件
│   │   ├── components/    # 通用组件
│   │   ├── contexts/      # React Context
│   │   └── services/      # API 服务
│   └── package.json
├── electron/               # 桌面应用
├── 启动器.py              # Python 启动脚本
├── 快速启动.bat           # Windows 快速启动
└── 使用说明.md            # 详细使用文档
```

## 🔧 配置

### 环境变量

在 `backend/.env` 中配置：

```env
# MiMo API 配置
MIMO_API_KEY=your_api_key
MIMO_BASE_URL=https://api.xiaomimimo.com/v1
MIMO_MODEL=mimo-v2.5-pro

# JWT 配置
SECRET_KEY=your_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### GitHub Token

分析私有仓库需要 GitHub Token：

1. 访问 https://github.com/settings/tokens
2. 生成新 Token，勾选 `repo` 权限
3. 在分析时填入

## 📚 文档

- [使用说明](使用说明.md) - 详细使用指南
- [开发日志](dev-logs/) - 开发过程记录

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

## 🔗 链接

- **GitHub**: https://github.com/Justinian-A/ai-code-reviewer
- **Issues**: https://github.com/Justinian-A/ai-code-reviewer/issues
