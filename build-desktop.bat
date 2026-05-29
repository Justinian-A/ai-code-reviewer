@echo off
echo ========================================
echo   AI 代码评审助手 - 桌面版构建脚本
echo ========================================
echo.

REM 检查 Node.js
where node >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 未安装 Node.js，请先安装 Node.js
    echo 下载地址: https://nodejs.org/
    pause
    exit /b 1
)

REM 检查 Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 未安装 Python，请先安装 Python
    echo 下载地址: https://www.python.org/
    pause
    exit /b 1
)

echo [1/5] 安装前端依赖...
cd frontend
call npm install
if %errorlevel% neq 0 (
    echo [错误] 前端依赖安装失败
    pause
    exit /b 1
)

echo [2/5] 构建前端...
call npm run build
if %errorlevel% neq 0 (
    echo [错误] 前端构建失败
    pause
    exit /b 1
)
cd ..

echo [3/5] 准备后端环境...
cd backend
if not exist "venv" (
    python -m venv venv
)
call venv\Scripts\activate
pip install -r requirements.txt -q
cd ..

echo [4/5] 复制文件到 Electron 目录...
if exist "electron\frontend" rmdir /s /q electron\frontend
if exist "electron\backend" rmdir /s /q electron\backend

xcopy /E /I /Y frontend\dist electron\frontend\dist
xcopy /E /I /Y backend electron\backend

echo [5/5] 安装 Electron 依赖并打包...
cd electron
call npm install
call npm run build:win

echo.
echo ========================================
echo   构建完成！
echo   安装包位置: electron\dist\
echo ========================================
pause
