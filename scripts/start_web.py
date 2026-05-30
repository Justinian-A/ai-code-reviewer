#!/usr/bin/env python3
"""启动AI Code Reviewer Web服务"""

import sys
import time
import webbrowser
import subprocess
from pathlib import Path

def main():
    # 获取项目根目录
    project_root = Path(__file__).parent.parent
    
    # 启动uvicorn服务
    cmd = [
        sys.executable, "-m", "uvicorn",
        "ai_code_reviewer.web.app:app",
        "--host", "0.0.0.0",
        "--port", "8080",
        "--reload"
    ]
    
    print("启动AI Code Reviewer Web服务...")
    print("访问地址: http://localhost:8080")
    print("按Ctrl+C停止服务")
    
    # 延迟打开浏览器
    def open_browser():
        time.sleep(2)
        webbrowser.open("http://localhost:8080")
    
    import threading
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()
    
    # 启动服务
    subprocess.run(cmd, cwd=project_root)

if __name__ == "__main__":
    main()
