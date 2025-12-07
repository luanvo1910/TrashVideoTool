"""
Module tải video/audio từ YouTube bằng yt-dlp
"""
import sys
import os
import subprocess
from utils import get_executable_path

# --- TỰ ĐỘNG CÀI ĐẶT yt-dlp NẾU THIẾU ---
def ensure_yt_dlp():
    """Tự động cài đặt yt-dlp nếu chưa có"""
    try:
        import yt_dlp
        return True
    except ImportError:
        print("STATUS: Đang cài đặt yt-dlp...", flush=True)
        try:
            # Cài đặt yt-dlp bằng pip
            subprocess.check_call([
                sys.executable, '-m', 'pip', 'install', '--quiet', '--upgrade', 'yt-dlp'
            ], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            print("STATUS: Đã cài đặt yt-dlp thành công!", flush=True)
            # Import lại sau khi cài đặt
            import yt_dlp
            return True
        except subprocess.CalledProcessError as e:
            print(f"PYTHON_ERROR: Không thể cài đặt yt-dlp. Vui lòng cài đặt thủ công bằng lệnh: pip install yt-dlp", file=sys.stderr, flush=True)
            return False
        except Exception as e:
            print(f"PYTHON_ERROR: Lỗi khi cài đặt yt-dlp: {e}", file=sys.stderr, flush=True)
            return False

def ytdlp_progress_hook(d):
    """Callback để hiển thị progress khi download"""
    # Gửi % download (đã bị App.jsx ẩn đi)
    if d['status'] == 'downloading':
        try:
            percent_str = d.get('_percent_str', '0.0%').replace('%','').strip()
            percent = float(percent_str)
            print(f"PROGRESS:DOWNLOAD:{percent}", flush=True)
        except (ValueError, TypeError): 
            pass
    elif d['status'] == 'finished':
        print("PROGRESS:DOWNLOAD:100", flush=True)

def fetch_video_metadata(url, cookies_path):
    """Lấy metadata của video từ YouTube"""
    import yt_dlp
    ydl_opts = {
        'quiet': True, 
        'no_warnings': True, 
        'noplaylist': True,
        'encoding': 'utf-8',  # Force UTF-8 encoding
    }
    if cookies_path and os.path.exists(cookies_path): 
        ydl_opts['cookiefile'] = cookies_path
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl: 
            return ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as e:
        if 'HTTP Error 403' in str(e):
            print(f"PYTHON_ERROR: Video yêu cầu cookies. {e}", file=sys.stderr, flush=True)
            raise Exception(f"Video yêu cầu cookies: {e}")
        print(f"PYTHON_ERROR: {e}", file=sys.stderr, flush=True)
        raise Exception(f"Lỗi tải metadata: {e}")
    except Exception as e:
        # Bắt các lỗi encoding khác
        print(f"PYTHON_ERROR: {e}", file=sys.stderr, flush=True)
        raise Exception(f"Lỗi không xác định: {e}")

def download_main_video(url, ffmpeg_path, dest_path, cookies_path):
    """Tải video chính (có audio) từ YouTube"""
    import yt_dlp
    output_template = os.path.splitext(dest_path)[0]
    
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best', 
        'merge_output_format': 'mp4',
        'outtmpl': f'{output_template}.%(ext)s',
        'ffmpeg_location': os.path.dirname(ffmpeg_path),
        'progress_hooks': [ytdlp_progress_hook], 
        'concurrent_fragments': 10, 
        'noplaylist': True,
        'quiet': True, # Tắt log % download
        'no_warnings': True, # Tắt log cảnh báo
        'encoding': 'utf-8',  # Force UTF-8 encoding
    }
    
    if cookies_path and os.path.exists(cookies_path): 
        ydl_opts['cookiefile'] = cookies_path
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl: 
            ydl.download([url])
        final_dest_path_with_ext = f"{output_template}.mp4"
        if os.path.exists(final_dest_path_with_ext) and final_dest_path_with_ext != dest_path:
             os.rename(final_dest_path_with_ext, dest_path)
    except yt_dlp.utils.DownloadError as e:
        if 'HTTP Error 403' in str(e):
            print(f"PYTHON_ERROR: Video yêu cầu cookies. {e}", file=sys.stderr, flush=True)
            raise Exception(f"Video yêu cầu cookies: {e}")
        print(f"PYTHON_ERROR: {e}", file=sys.stderr, flush=True)
        raise Exception(f"Lỗi tải video: {e}")
    except Exception as e:
        # Bắt các lỗi encoding khác
        print(f"PYTHON_ERROR: {e}", file=sys.stderr, flush=True)
        raise Exception(f"Lỗi không xác định khi tải video: {e}")

def download_audio_only(url, ffmpeg_path, dest_path, cookies_path):
    """Tải audio từ YouTube"""
    import yt_dlp
    output_template = os.path.splitext(dest_path)[0]
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{output_template}.%(ext)s',
        'ffmpeg_location': os.path.dirname(ffmpeg_path),
        'progress_hooks': [ytdlp_progress_hook],
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'encoding': 'utf-8',
    }
    
    if cookies_path and os.path.exists(cookies_path): 
        ydl_opts['cookiefile'] = cookies_path
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            # yt-dlp sẽ tự động extract thành .mp3 với postprocessor
            # Tìm file .mp3 đã được tạo
            mp3_file = f"{output_template}.mp3"
            if os.path.exists(mp3_file) and mp3_file != dest_path:
                if os.path.exists(dest_path):
                    os.remove(dest_path)
                os.rename(mp3_file, dest_path)
            elif not os.path.exists(dest_path):
                # Nếu file chưa có extension .mp3, tìm file đã download
                base_name = os.path.basename(output_template)
                parent_dir = os.path.dirname(output_template)
                for file in os.listdir(parent_dir):
                    if file.startswith(base_name) and file.endswith('.mp3'):
                        old_path = os.path.join(parent_dir, file)
                        os.rename(old_path, dest_path)
                        break
    except yt_dlp.utils.DownloadError as e:
        if 'HTTP Error 403' in str(e):
            print(f"PYTHON_ERROR: Video yêu cầu cookies. {e}", file=sys.stderr, flush=True)
            raise Exception(f"Video yêu cầu cookies: {e}")
        print(f"PYTHON_ERROR: {e}", file=sys.stderr, flush=True)
        raise Exception(f"Lỗi tải audio: {e}")
    except Exception as e:
        print(f"PYTHON_ERROR: {e}", file=sys.stderr, flush=True)
        raise Exception(f"Lỗi không xác định khi tải audio: {e}")

def download_thumbnail(thumbnail_url, dest_path):
    """Tải thumbnail từ URL"""
    import urllib.request
    urllib.request.urlretrieve(thumbnail_url, dest_path)
    if not os.path.exists(dest_path): 
        raise FileNotFoundError("Could not download thumbnail")

