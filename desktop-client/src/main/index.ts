import { app, BrowserWindow } from 'electron'
import { join } from 'path'
import { registerIpcHandlers } from './ipc-handlers'
import { getHost, setHost, getToken } from './token-store'

function createWindow(): void {
  const win = new BrowserWindow({
    width: 1400,
    height: 900,
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      webviewTag: true,
      contextIsolation: true,
      nodeIntegration: false,
    }
  })

  if (process.env.ELECTRON_RENDERER_URL) {
    win.loadURL(process.env.ELECTRON_RENDERER_URL)
  } else {
    win.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

app.whenReady().then(async () => {
  const [host, token] = await Promise.all([getHost(), getToken()])
  const isValidBackend = /^https?:\/\/.+:\d{4}/.test(host)
  if (!isValidBackend) {
    await setHost('http://100.125.134.3:8006')
    console.log('[config] backend reset (was:', host, ')')
  }
  console.log('[config] backend:', isValidBackend ? host : 'http://100.125.134.3:8006')
  console.log('[config] token:', token ? '(set)' : '(NOT SET)')
  registerIpcHandlers()
  createWindow()
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
