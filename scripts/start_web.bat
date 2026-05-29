@echo off
echo 启动AI Code Reviewer Web服务...
echo 访问地址: http://localhost:8080
echo 按Ctrl+C停止服务
echo.

cd /d "%~dp0.."
python scripts/start_web.py

pause
