"""
AI Code Reviewer - FastAPI 主应用
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from app.api import auth, reviews, github
from app.database import init_db

# 前端静态文件目录
FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend" / "dist"

app = FastAPI(
    title="AI Code Reviewer",
    description="AI 辅助代码评审工具",
    version="0.1.0",
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理"""
    import traceback
    error_msg = f"{type(exc).__name__}: {str(exc)}"
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": error_msg},
    )

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React 开发服务器
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(reviews.router, prefix="/api/reviews", tags=["评审"])
app.include_router(github.router, prefix="/api/github", tags=["GitHub"])


@app.on_event("startup")
async def startup():
    """应用启动时初始化数据库"""
    await init_db()


@app.get("/health")
async def health():
    return {"status": "healthy"}


# 提供前端静态文件
if FRONTEND_DIR.exists():
    # 提供静态资源
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

    # 所有其他路由返回前端 index.html（支持前端路由）
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # 尝试返回静态文件
        file_path = FRONTEND_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        # 否则返回 index.html
        return FileResponse(FRONTEND_DIR / "index.html")
else:
    @app.get("/")
    async def root():
        return {
            "message": "AI Code Reviewer API",
            "version": "0.1.0",
            "note": "Frontend not built. Run 'npm run build' in frontend directory."
        }
