@echo off
title AI 代码评审助手
echo ========================================
echo   AI 代码评审助手 - 便携版
echo ========================================
echo.

REM 检查 Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 未安装 Python，请先安装 Python 3.8+
    echo 下载地址: https://www.python.org/
    pause
    exit /b 1
)

echo [1/3] 安装后端依赖...
cd backend
pip install -r requirements.txt -q
cd ..

echo [2/3] 构建前端...
cd frontend
call npm install -q
call npm run build
cd ..

echo [3/3] 启动服务...
echo.
echo 正在启动后端服务...
start /b cmd /c "cd backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

echo 等待服务就绪...
timeout /t 5 /nobreak >nul

echo.
echo ========================================
echo   启动成功！
echo.
echo   请在浏览器中访问:
echo   http://localhost:8000
echo.
echo   按 Ctrl+C 停止服务
echo ========================================
echo.

REM 打开浏览器
start http://localhost:8000

REM 保持窗口
pause
