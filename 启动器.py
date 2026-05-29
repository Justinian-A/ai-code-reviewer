"""
AI 代码评审助手 - 启动器
双击运行此文件即可启动应用
"""
import os
import sys
import time
import webbrowser
import subprocess
import threading
from pathlib import Path

# 获取当前目录
BASE_DIR = Path(__file__).parent
BACKEND_DIR = BASE_DIR / "backend"
FRONTEND_DIR = BASE_DIR / "frontend"

def check_python():
    """检查 Python 版本"""
    if sys.version_info < (3, 8):
        print("错误: 需要 Python 3.8 或更高版本")
        print(f"当前版本: {sys.version}")
        input("按回车键退出...")
        sys.exit(1)

def install_backend_deps():
    """安装后端依赖"""
    print("正在安装后端依赖...")
    requirements = BACKEND_DIR / "requirements.txt"
    subprocess.run([
        sys.executable, "-m", "pip", "install",
        "-r", str(requirements), "-q"
    ], check=True)

def build_frontend():
    """构建前端"""
    print("正在构建前端...")

    # 检查是否已构建
    dist_dir = FRONTEND_DIR / "dist"
    if dist_dir.exists() and (dist_dir / "index.html").exists():
        print("前端已构建，跳过...")
        return

    # 安装依赖
    subprocess.run(["npm", "install"], cwd=FRONTEND_DIR, check=True, shell=True)

    # 构建
    subprocess.run(["npm", "run", "build"], cwd=FRONTEND_DIR, check=True, shell=True)

def start_backend():
    """启动后端服务"""
    print("正在启动后端服务...")

    # 启动 uvicorn
    process = subprocess.Popen([
        sys.executable, "-m", "uvicorn",
        "app.main:app",
        "--host", "127.0.0.1",
        "--port", "8000"
    ], cwd=BACKEND_DIR)

    return process

def wait_for_server(url, timeout=30):
    """等待服务器就绪"""
    import urllib.request

    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = urllib.request.urlopen(url)
            if response.status == 200:
                return True
        except:
            pass
        time.sleep(0.5)

    return False

def open_browser():
    """打开浏览器"""
    time.sleep(2)
    webbrowser.open("http://localhost:8000")

def main():
    """主函数"""
    print("=" * 50)
    print("   AI 代码评审助手")
    print("=" * 50)
    print()

    # 检查 Python
    check_python()

    # 安装依赖
    try:
        install_backend_deps()
    except Exception as e:
        print(f"安装依赖失败: {e}")
        input("按回车键退出...")
        sys.exit(1)

    # 构建前端
    try:
        build_frontend()
    except Exception as e:
        print(f"构建前端失败: {e}")
        print("提示: 请确保已安装 Node.js")
        input("按回车键退出...")
        sys.exit(1)

    # 启动后端
    backend_process = start_backend()

    # 等待服务就绪
    print("等待服务启动...")
    if wait_for_server("http://127.0.0.1:8000/health"):
        print()
        print("=" * 50)
        print("   启动成功！")
        print()
        print("   访问地址: http://localhost:8000")
        print()
        print("   按 Ctrl+C 停止服务")
        print("=" * 50)

        # 在新线程中打开浏览器
        threading.Thread(target=open_browser, daemon=True).start()

        try:
            # 保持运行
            backend_process.wait()
        except KeyboardInterrupt:
            print("\n正在停止服务...")
            backend_process.terminate()
            backend_process.wait()
            print("服务已停止")
    else:
        print("启动失败: 服务超时")
        backend_process.terminate()
        input("按回车键退出...")

if __name__ == "__main__":
    main()
