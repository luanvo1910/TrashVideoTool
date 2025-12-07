const { app, BrowserWindow, ipcMain, dialog, Menu, nativeImage } = require('electron');
const path = require('path');
const { spawn, execSync } = require('child_process');
const Store = require('electron-store');
const fs = require('fs');
const os = require('os');
const { autoUpdater } = require('electron-updater');

const store = new Store();
let mainWindow;
let cachedFonts = null;
let cachedPythonExecutable = null;

function sendUpdateMessage(channel, ...args) {
  if (mainWindow) {
    mainWindow.webContents.send(channel, ...args);
  }
}

/**
 * Tìm Python executable bằng cách thử nhiều lệnh khác nhau
 * @returns {string} Đường dẫn hoặc tên lệnh Python (fallback về 'py' nếu không tìm thấy)
 */
function findPythonExecutable() {
  // Nếu đã cache, dùng lại
  if (cachedPythonExecutable) {
    return cachedPythonExecutable;
  }

  // Danh sách các lệnh để thử (theo thứ tự ưu tiên)
  const commandsToTry = process.platform === 'win32' 
    ? ['python', 'py', 'python3'] 
    : ['python3', 'python'];

  for (const cmd of commandsToTry) {
    try {
      // Thử chạy lệnh với --version để kiểm tra
      execSync(`${cmd} --version`, { 
        stdio: 'ignore',
        timeout: 2000,
        windowsHide: true
      });
      // Nếu thành công, cache và trả về
      cachedPythonExecutable = cmd;
      console.log(`Found Python executable: ${cmd}`);
      return cmd;
    } catch (error) {
      // Lệnh không tồn tại, thử lệnh tiếp theo
      continue;
    }
  }

  // Không tìm thấy Python, fallback về 'py' như ProjectRB
  console.warn('Python executable not found. Falling back to "py"');
  cachedPythonExecutable = 'py';
  return 'py';
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1600,
    height: 900,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
    },
  });
  const isDev = !app.isPackaged;
  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, 'renderer', 'dist', 'index.html'));
  }
}

async function loadFonts() {
  try {
    const resourcesPath = app.isPackaged ? process.resourcesPath : __dirname;
    const fontsDir = app.isPackaged 
      ? path.join(resourcesPath, 'assets')
      : path.join(resourcesPath, 'resources', 'assets');

    const readFontAsDataUrl = (filePath, mimeType) => {
      try {
        const fileData = fs.readFileSync(filePath);
        const base64Data = fileData.toString('base64');
        return `data:${mimeType};base64,${base64Data}`;
      } catch (e) {
        console.error(`Lỗi khi đọc file font: ${filePath}`, e);
        return null;
      }
    };
    
    const defaultFontPath = path.join(fontsDir, 'arial.ttf');
    const defaultFonts = [{ 
      name: 'Arial (Mặc định)', 
      file: 'arial.ttf', 
      dataUrl: readFontAsDataUrl(defaultFontPath, 'font/ttf')
    }];

    if (!fs.existsSync(fontsDir)) {
        console.error(`Không tìm thấy thư mục font tại: ${fontsDir}`);
        cachedFonts = defaultFonts.filter(f => f.dataUrl);
        return cachedFonts;
    }

    const fontFiles = fs.readdirSync(fontsDir);
    const fontList = fontFiles
      .filter(file => file.toLowerCase().endsWith('.ttf') || file.toLowerCase().endsWith('.otf'))
      .map(file => {
          let name = path.parse(file).name;
          name = name.charAt(0).toUpperCase() + name.slice(1).replace(/-/g, ' ');
          
          const fullPath = path.join(fontsDir, file);
          const mimeType = file.endsWith('.ttf') ? 'font/ttf' : 'font/otf';
          
          return { 
            name: name, 
            file: file, 
            dataUrl: readFontAsDataUrl(fullPath, mimeType)
          };
      });
    
    const allFonts = [...defaultFonts, ...fontList].filter(f => f.dataUrl); 
    const uniqueFonts = Array.from(new Map(allFonts.map(font => [font.file, font])).values());
    
    cachedFonts = uniqueFonts;
    return cachedFonts;

  } catch (err) {
    console.error("Lỗi nghiêm trọng khi đọc thư mục font:", err);
    cachedFonts = [];
    return []; 
  }
}

// --- CẤU HÌNH CACHE ĐỂ TRÁNH LỖI TRUY CẬP ---
// Set cache directory an toàn hơn để tránh lỗi "Access is denied" trên máy khác
// Phải set TRƯỚC khi app ready
if (app.isPackaged) {
  // Khi build, dùng userData directory (luôn có quyền truy cập)
  const userDataPath = app.getPath('userData');
  const cachePath = path.join(userDataPath, 'cache');
  const gpuCachePath = path.join(userDataPath, 'GPUCache');
  
  // Tạo thư mục cache nếu chưa có
  try {
    if (!fs.existsSync(cachePath)) {
      fs.mkdirSync(cachePath, { recursive: true });
    }
    if (!fs.existsSync(gpuCachePath)) {
      fs.mkdirSync(gpuCachePath, { recursive: true });
    }
  } catch (err) {
    console.warn('Không thể tạo cache directory, sẽ dùng mặc định:', err.message);
  }
  
  // Set cache directory cho Electron (chỉ khi packaged)
  try {
    app.setPath('cache', cachePath);
    app.setPath('userCache', cachePath);
  } catch (err) {
    console.warn('Không thể set cache path, sẽ dùng mặc định:', err.message);
  }
}

app.whenReady().then(() => {
  createWindow();
  loadFonts();
  if (!app.isPackaged) {
    console.log('Update check skipped in development mode.');
  } else {
    autoUpdater.checkForUpdates();
  }
});

app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });

// --- CÁC HÀM XỬ LÝ IPC ---
ipcMain.handle('templates:get', () => store.get('templates', []));
ipcMain.handle('templates:save', (event, template) => {
  const templates = store.get('templates', []);
  const existingIndex = templates.findIndex(t => t.id === template.id);
  if (existingIndex > -1) { templates[existingIndex] = template; } else { templates.push(template); }
  store.set('templates', templates);
  return true;
});
ipcMain.handle('templates:delete', (event, templateId) => {
  const templates = store.get('templates', []);
  store.set('templates', templates.filter(t => t.id !== templateId));
  return true;
});

ipcMain.handle('fonts:get', async () => {
  if (cachedFonts) {
    return cachedFonts;
  }
  return await loadFonts();
});

ipcMain.on('show-context-menu', (event, { elementId, elementType }) => {
    const commands = [
      { label: 'Đưa lên trên 1 lớp', click: () => sendCommand('bring-forward', elementId) },
      { label: 'Đưa xuống dưới 1 lớp', click: () => sendCommand('send-backward', elementId) },
    ];
    if (elementType === 'image' || (elementType === 'text' && elementId !== 'text-placeholder')) {
      commands.push({ type: 'separator' });
      commands.push({ label: 'Xóa đối tượng', click: () => sendCommand('delete-element', elementId) });
    }
    function sendCommand(action, id) { event.sender.send('context-menu-command', { action, elementId: id }); }
    Menu.buildFromTemplate(commands).popup({ window: BrowserWindow.fromWebContents(event.sender) });
});
  
ipcMain.handle('dialog:openImage', async () => {
  const { canceled, filePaths } = await dialog.showOpenDialog(mainWindow, {
    properties: ['openFile'],
    filters: [{ name: 'Images', extensions: ['png', 'jpg', 'jpeg', 'webp', 'gif'] }],
  });
  if (canceled || !filePaths || filePaths.length === 0) { return null; }
  try {
    const filePath = filePaths[0];
    const fileData = fs.readFileSync(filePath);
    
    const image = nativeImage.createFromBuffer(fileData);
    const size = image.getSize(); 

    const base64Data = fileData.toString('base64');
    const mimeType = `image/${path.extname(filePath).substring(1)}`;
    
    return {
      dataUrl: `data:${mimeType};base64,${base64Data}`,
      width: size.width,
      height: size.height
    };
  } catch (error) { 
    console.error("Lỗi đọc ảnh:", error);
    return null; 
  }
});

ipcMain.handle('dialog:openDirectory', async () => {
  const { canceled, filePaths } = await dialog.showOpenDialog(mainWindow, { properties: ['openDirectory'] });
  return canceled ? null : filePaths[0];
});
ipcMain.handle('cookies:update', async () => {
  const { canceled, filePaths } = await dialog.showOpenDialog(mainWindow, {
    title: 'Chọn file cookies.txt mới', properties: ['openFile'],
    filters: [{ name: 'Text Files', extensions: ['txt'] }]
  });
  if (canceled || !filePaths || filePaths.length === 0) {
    return { success: false, message: 'Hủy chọn file.' };
  }
  try {
    const selectedCookiePath = filePaths[0];
    const userDataPath = app.getPath('userData');
    const finalCookiePath = path.join(userDataPath, 'cookies.txt');
    fs.copyFileSync(selectedCookiePath, finalCookiePath);
    return { success: true, message: `Cập nhật cookies thành công! File đã được lưu tại: ${finalCookiePath}` };
  } catch (error) {
    return { success: false, message: `Lỗi khi sao chép file cookies: ${error.message}` };
  }
});


ipcMain.on('video:runProcessWithLayout', (event, { audioUrl, videoUrl, videoSpeed, parts, partDuration, savePath, layout, encoder }) => {
    const resourcesPath = app.isPackaged ? process.resourcesPath : __dirname;
    
    // Khi build, editor.py nằm trong process.resourcesPath (thư mục resources)
    // Khi dev, editor.py nằm trong thư mục scripts/
    const pythonScriptPath = app.isPackaged
      ? path.join(process.resourcesPath, 'editor.py')
      : path.join(__dirname, 'scripts', 'editor.py');
      
    const resourcesPathForPython = app.isPackaged
      ? process.resourcesPath
      : path.join(__dirname, 'resources'); 
      
    const userDataPath = app.getPath('userData');
    const layoutFilePath = path.join(os.tmpdir(), `layout-${Date.now()}.json`);
    fs.writeFileSync(layoutFilePath, JSON.stringify(layout));
  
    const args = [
      pythonScriptPath, '--resources-path', resourcesPathForPython, '--user-data-path', userDataPath,
      '--audio-url', audioUrl, '--video-url', videoUrl, 
      '--video-speed', String(videoSpeed || 1.0),
      '--parts', String(parts), '--save-path', savePath, '--part-duration', String(partDuration), 
      '--layout-file', layoutFilePath, '--encoder', encoder || 'h264_nvenc'
    ];

    // Tìm Python executable (sẽ fallback về 'py' nếu không tìm thấy)
    const commandToRun = findPythonExecutable();
    
    // Debug: In ra đường dẫn để kiểm tra (chỉ khi build)
    if (app.isPackaged) {
      const debugInfo = `DEBUG: Python script path: ${pythonScriptPath}\nDEBUG: Resources path: ${resourcesPathForPython}\nDEBUG: Script exists: ${fs.existsSync(pythonScriptPath)}\nDEBUG: Resources exists: ${fs.existsSync(resourcesPathForPython)}\nDEBUG: Python executable: ${commandToRun}`;
      console.log(debugInfo);
      sendUpdateMessage('process:log', debugInfo);
    }
    
    // Kiểm tra file tồn tại trước khi chạy
    if (!fs.existsSync(pythonScriptPath)) {
      const errorMsg = `Python script không tồn tại: ${pythonScriptPath}\nResources path: ${resourcesPath}\nIs packaged: ${app.isPackaged}`;
      console.error(errorMsg);
      sendUpdateMessage('process:log', `PYTHON_ERROR: ${errorMsg}`);
      sendUpdateMessage('process:log', `--- Tiến trình kết thúc với lỗi (mã 1) ---`);
      sendUpdateMessage('process:progress', { type: 'DONE', value: 100 });
      return;
    }
    
    // Kiểm tra resources path
    if (!fs.existsSync(resourcesPathForPython)) {
      const errorMsg = `Resources path không tồn tại: ${resourcesPathForPython}`;
      console.error(errorMsg);
      sendUpdateMessage('process:log', `PYTHON_ERROR: ${errorMsg}`);
      sendUpdateMessage('process:log', `--- Tiến trình kết thúc với lỗi (mã 1) ---`);
      sendUpdateMessage('process:progress', { type: 'DONE', value: 100 });
      return;
    }
    
    // Kiểm tra FFmpeg có tồn tại không (quan trọng cho xử lý video)
    const ffmpegPath = path.join(resourcesPathForPython, process.platform === 'win32' ? 'ffmpeg.exe' : 'ffmpeg');
    if (!fs.existsSync(ffmpegPath)) {
      const errorMsg = `FFmpeg không tìm thấy tại: ${ffmpegPath}\nFFmpeg là bắt buộc để xử lý video.`;
      console.error(errorMsg);
      sendUpdateMessage('process:log', `PYTHON_ERROR: ${errorMsg}`);
      sendUpdateMessage('process:log', `--- Tiến trình kết thúc với lỗi (mã 1) ---`);
      sendUpdateMessage('process:progress', { type: 'DONE', value: 100 });
      return;
    }

    // Test script Python có thể compile được không (kiểm tra syntax)
    // Điều này giúp phát hiện lỗi syntax ngay từ đầu
    try {
      // Lấy thư mục chứa script để thêm vào PYTHONPATH
      // Python cần tìm thấy các module (utils, downloader, video_processor) trong cùng thư mục
      const scriptDir = path.dirname(pythonScriptPath);
      const testCommand = `${commandToRun} -m py_compile "${pythonScriptPath}"`;
      
      execSync(testCommand, {
        encoding: 'utf8',
        timeout: 5000,
        windowsHide: true,
        stdio: 'ignore',
        env: {
          ...process.env,
          // Thêm thư mục chứa script vào PYTHONPATH để Python tìm thấy các module
          PYTHONPATH: scriptDir + (process.env.PYTHONPATH ? path.delimiter + process.env.PYTHONPATH : ''),
          PYTHONIOENCODING: 'utf-8',
          PYTHONUTF8: '1'
        }
      });
      console.log('Python script syntax check passed');
    } catch (testError) {
      // Nếu compile thất bại, có thể là lỗi syntax hoặc không tìm thấy module
      const errorMsg = `PYTHON_ERROR: Script Python có lỗi syntax hoặc không thể compile.\nLỗi: ${testError.message}\n\nVui lòng kiểm tra script: ${pythonScriptPath}\nĐảm bảo các file utils.py, downloader.py, video_processor.py có trong cùng thư mục.`;
      console.error(errorMsg);
      sendUpdateMessage('process:log', errorMsg);
      sendUpdateMessage('process:log', `--- Tiến trình kết thúc với lỗi (mã 1) ---`);
      sendUpdateMessage('process:progress', { type: 'DONE', value: 100 });
      return;
    }

    // Thêm PYTHONPATH vào environment để Python tìm thấy các module
    const scriptDir = path.dirname(pythonScriptPath);
    const pythonEnv = {
      ...process.env,
      PYTHONIOENCODING: 'utf-8',
      PYTHONUTF8: '1',
      PYTHONLEGACYWINDOWSSTDIO: '0',
      // Thêm thư mục chứa script vào PYTHONPATH để import modules
      PYTHONPATH: scriptDir + (process.env.PYTHONPATH ? path.delimiter + process.env.PYTHONPATH : '')
    };
    
    const pythonProcess = spawn(commandToRun, args, { 
      env: pythonEnv,
      stdio: ['ignore', 'pipe', 'pipe'] // Đảm bảo stdout và stderr được pipe
    });
    
    let hasLinkSuccess = false;
    let hasLinkError = false;
    let stdoutBuffer = '';
    let stderrBuffer = '';
    let hasReceivedOutput = false;
    
    pythonProcess.stdout.on('data', (data) => {
        hasReceivedOutput = true;
        const text = data.toString('utf8');
        stdoutBuffer += text;
        const lines = text.split(/(\r\n|\n|\r)/);
        for (const line of lines) {
            const logLine = line.trim();
            if (!logLine) continue;
            if (logLine.startsWith('PROGRESS:')) {
                sendUpdateMessage('process:progress', { type: line.split(':')[1], value: parseFloat(line.split(':')[2]) });
            } else {
                sendUpdateMessage('process:log', logLine);
                // Theo dõi LINK_SUCCESS và LINK_ERROR
                if (logLine.includes('LINK_SUCCESS')) {
                    hasLinkSuccess = true;
                } else if (logLine.includes('LINK_ERROR:')) {
                    hasLinkError = true;
                }
            }
        }
    });
    
    pythonProcess.stderr.on('data', (data) => {
        hasReceivedOutput = true;
        const text = data.toString('utf8');
        stderrBuffer += text;
        const lines = text.split(/(\r\n|\n|\r)/);
        for (const line of lines) {
            const logLine = line.trim();
            if (!logLine) continue;
            // In tất cả stderr để debug
            sendUpdateMessage('process:log', logLine);
            if (logLine.includes('LINK_ERROR:') || logLine.includes('PYTHON_ERROR:')) {
                hasLinkError = true;
            }
        }
    });
    
    // Bắt lỗi khi không thể spawn process
    pythonProcess.on('error', (err) => {
        let errorMsg;
        if (err.code === 'ENOENT') {
            errorMsg = `FATAL_ERROR: Không tìm thấy Python executable "${commandToRun}".\nVui lòng cài đặt Python từ https://www.python.org/downloads/\nĐảm bảo đã chọn "Add Python to PATH" khi cài đặt.\nScript path: ${pythonScriptPath}`;
        } else {
            errorMsg = `FATAL_ERROR: Không thể khởi chạy Python. ${err.message}\nCommand: ${commandToRun}\nScript path: ${pythonScriptPath}`;
        }
        console.error(errorMsg);
        sendUpdateMessage('process:log', errorMsg);
        hasLinkError = true;
    });
    pythonProcess.on('close', (code) => {
        // Đợi một chút để đảm bảo tất cả output đã được đọc
        setTimeout(() => {
            if (code === 403) {
                sendUpdateMessage('process:cookie-required');
            }
            
            // Nếu không có output nào và code !== 0, có thể Python không chạy được
            if (code !== 0 && !hasLinkError && !hasLinkSuccess) {
                let errorMsg = `PYTHON_ERROR: Python process exited with code ${code}.\n`;
                
                // Nếu có output trong buffer, hiển thị nó
                if (stdoutBuffer.trim() || stderrBuffer.trim()) {
                    errorMsg += `\nOutput từ Python:\n`;
                    if (stdoutBuffer.trim()) {
                        errorMsg += `STDOUT:\n${stdoutBuffer.trim()}\n\n`;
                    }
                    if (stderrBuffer.trim()) {
                        errorMsg += `STDERR:\n${stderrBuffer.trim()}\n\n`;
                    }
                } else if (!hasReceivedOutput) {
                    // Không có output nào cả - có thể script không chạy được
                    errorMsg += `Không nhận được output nào từ Python script.\n`;
                    errorMsg += `Điều này có thể do:\n`;
                    errorMsg += `1. Script không thể thực thi được (lỗi syntax, import, v.v.)\n`;
                    errorMsg += `2. Python script exit quá nhanh trước khi in output\n`;
                    errorMsg += `3. Thiếu thư viện Python cần thiết (ví dụ: yt-dlp)\n\n`;
                    errorMsg += `Vui lòng thử chạy script thủ công để xem lỗi:\n`;
                    errorMsg += `${commandToRun} "${pythonScriptPath}" --help\n\n`;
                }
                
                errorMsg += `Thông tin debug:\n`;
                errorMsg += `- Python executable: ${commandToRun}\n`;
                errorMsg += `- Script path: ${pythonScriptPath}\n`;
                errorMsg += `- Resources path: ${resourcesPathForPython}\n`;
                errorMsg += `- Exit code: ${code}`;
                
                sendUpdateMessage('process:log', errorMsg);
                hasLinkError = true;
            }
            
            // Chỉ hiển thị thành công nếu có LINK_SUCCESS và không có LINK_ERROR
            let statusMsg;
            if (hasLinkSuccess && !hasLinkError && code === 0) {
                statusMsg = '--- Tiến trình kết thúc thành công ---';
            } else if (hasLinkError || code !== 0) {
                statusMsg = `--- Tiến trình kết thúc với lỗi (mã ${code}) ---`;
            } else {
                statusMsg = `--- Tiến trình kết thúc (mã ${code}) ---`;
            }
            sendUpdateMessage('process:log', statusMsg);
            sendUpdateMessage('process:progress', { type: 'DONE', value: 100 });
            if (fs.existsSync(layoutFilePath)) fs.unlinkSync(layoutFilePath);
        }, 100); // Đợi 100ms để đảm bảo output được flush
    });
});


// --- Xử lý Auto-Update thủ công ---
autoUpdater.on('update-available', (info) => {
  sendUpdateMessage('update:available', info);
});
autoUpdater.on('update-not-available', (info) => {
  sendUpdateMessage('update:message', 'Bạn đang dùng phiên bản mới nhất.');
});
autoUpdater.on('download-progress', (progressObj) => {
  sendUpdateMessage('update:progress', progressObj.percent);
});
autoUpdater.on('update-downloaded', (info) => {
  sendUpdateMessage('update:downloaded', info);
});
autoUpdater.on('error', (err) => {
  sendUpdateMessage('update:message', `Lỗi cập nhật: ${err.message}`);
});

ipcMain.on('updater:start-download', () => {
  autoUpdater.downloadUpdate();
});
ipcMain.on('updater:quit-and-install', () => {
  autoUpdater.quitAndInstall();
});