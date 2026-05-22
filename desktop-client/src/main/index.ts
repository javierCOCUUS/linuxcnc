import { app, BrowserWindow } from 'electron'

const CNC_URL = 'http://100.125.134.3:8069/cnc/bench'

app.whenReady().then(() => {
  const win = new BrowserWindow({
    width: 1400,
    height: 900,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    }
  })
  win.loadURL(CNC_URL)
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) win.show()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
