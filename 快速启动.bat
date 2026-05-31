@echo off
title AI 代码评审助手
echo ========================================
echo   AI 代码评审助手 - 快速启动
echo ========================================
echo.

cd /d "%~dp0"

echo [1/2] 启动后端服务...
cd backend
start /b cmd /c "python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
cd ..

echo [2/2] 等待服务就绪...
timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo   启动成功！
echo.
echo   访问地址: http://localhost:8000
echo.
echo   关闭此窗口停止服务
echo ========================================
echo.

REM 打开浏览器
start http://localhost:8000

REM 保持窗口
pause
