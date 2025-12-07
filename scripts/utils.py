"""
Module tiện ích - các hàm helper và setup encoding
"""
import sys
import os
import io
import subprocess
import re

# --- SETUP ENCODING (phải làm trước khi import module khác) ---
if sys.stdout.encoding != 'utf-8': 
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if sys.stderr.encoding != 'utf-8': 
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    os.environ['PYTHONUTF8'] = '1'
    # Đảm bảo console output dùng UTF-8 trên Windows
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# --- PATCH subprocess.Popen để luôn dùng UTF-8 encoding ---
# Fix quan trọng: yt-dlp gọi subprocess internally mà không set encoding
_original_popen = subprocess.Popen
class UTF8Popen(_original_popen):
    def __init__(self, *args, **kwargs):
        # Nếu text=True hoặc universal_newlines=True nhưng không có encoding
        if (kwargs.get('text') or kwargs.get('universal_newlines')) and 'encoding' not in kwargs:
            kwargs['encoding'] = 'utf-8'
            kwargs['errors'] = 'replace'  # Ignore các ký tự không decode được
        super().__init__(*args, **kwargs)
subprocess.Popen = UTF8Popen

# --- CÁC HÀM TIỆN ÍCH ---
def get_executable_path(name, resources_path):
    """Lấy đường dẫn đến executable (ffmpeg, ffprobe, etc.)"""
    executable_name = name if sys.platform != 'win32' else f"{name}.exe"
    return os.path.join(resources_path, executable_name)

def sanitize_filename(name):
    """Loại bỏ các ký tự không hợp lệ trong tên file"""
    return re.sub(r'[\\/*?:"<>|]', "", name)

def hex_to_ffmpeg_color(hex_color, alpha='ff'):
    """Chuyển đổi hex color sang format ffmpeg"""
    try:
        hex_color = hex_color.lstrip('#')
        if len(hex_color) != 6: 
            raise ValueError
        return f"0x{hex_color}{alpha}"
    except:
        return "0xFFFFFFFF"

def ffmpeg_safe_path(path):
    """Chuyển đổi path sang format an toàn cho ffmpeg"""
    path = path.replace("\\", "/")
    if sys.platform == "win32":
        return path.replace(":", "\\:")
    return path

