const { app, BrowserWindow, shell } = require('electron')
const path = require('path')
const { spawn } = require('child_process')
const http = require('http')

let mainWindow = null
let backendProcess = null

const BACKEND_PORT = 8000
const FRONTEND_PORT = 3000

// 检查端口是否可用
function isPortAvailable(port) {
  return new Promise((resolve) => {
    const server = http.createServer()
    server.listen(port, () => {
      server.close()
      resolve(true)
    })
    server.on('error', () => {
      resolve(false)
    })
  })
}

// 等待服务就绪
function waitForService(url, timeout = 30000) {
  return new Promise((resolve, reject) => {
    const startTime = Date.now()

    const check = () => {
      http.get(url, (res) => {
        if (res.statusCode === 200) {
          resolve()
        } else {
          retry()
        }
      }).on('error', () => {
        retry()
      })
    }

    const retry = () => {
      if (Date.now() - startTime > timeout) {
        reject(new Error('Service timeout'))
      } else {
        setTimeout(check, 500)
      }
    }

    check()
  })
}

// 启动后端服务
async function startBackend() {
  const isAvailable = await isPortAvailable(BACKEND_PORT)
  if (!isAvailable) {
    console.log(`Port ${BACKEND_PORT} is already in use`)
    return
  }

  const backendPath = path.join(__dirname, 'backend')
  const pythonPath = path.join(backendPath, 'venv', 'Scripts', 'python.exe')
  const appPath = path.join(backendPath, 'app', 'main.py')

  // 检查是否打包后的环境
  const isPackaged = app.isPackaged

  if (isPackaged) {
    // 打包后使用嵌入的 Python
    const embeddedPython = path.join(process.resourcesPath, 'python', 'python.exe')
    backendProcess = spawn(embeddedPython, ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', BACKEND_PORT], {
      cwd: backendPath,
      stdio: 'pipe'
    })
  } else {
    // 开发环境使用系统 Python
    backendProcess = spawn('python', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', BACKEND_PORT], {
      cwd: backendPath,
      stdio: 'pipe'
    })
  }

  backendProcess.stdout.on('data', (data) => {
    console.log(`Backend: ${data}`)
  })

  backendProcess.stderr.on('data', (data) => {
    console.error(`Backend Error: ${data}`)
  })

  backendProcess.on('close', (code) => {
    console.log(`Backend process exited with code ${code}`)
  })
}

// 创建主窗口
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    title: 'AI 代码评审助手',
    icon: path.join(__dirname, 'icon.png'),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    }
  })

  // 加载前端页面
  const frontendPath = path.join(__dirname, 'frontend', 'dist', 'index.html')
  mainWindow.loadFile(frontendPath)

  // 处理外部链接
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

// 应用就绪后启动
app.whenReady().then(async () => {
  // 启动后端
  await startBackend()

  // 等待后端就绪
  try {
    await waitForService(`http://127.0.0.1:${BACKEND_PORT}/health`)
    console.log('Backend is ready')
  } catch (error) {
    console.error('Backend failed to start:', error)
  }

  // 创建窗口
  createWindow()
})

// 所有窗口关闭后
app.on('window-all-closed', () => {
  // 停止后端
  if (backendProcess) {
    backendProcess.kill()
    backendProcess = null
  }

  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('activate', () => {
  if (mainWindow === null) {
    createWindow()
  }
})

// 应用退出前清理
app.on('before-quit', () => {
  if (backendProcess) {
    backendProcess.kill()
    backendProcess = null
  }
})
