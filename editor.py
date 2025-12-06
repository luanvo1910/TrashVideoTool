import sys
import os
import subprocess
import json
import re
import argparse
import urllib.request
import shutil
import base64
import io
import threading
import math

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

if sys.stdout.encoding != 'utf-8': sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if sys.stderr.encoding != 'utf-8': sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


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
    executable_name = name if sys.platform != 'win32' else f"{name}.exe"
    return os.path.join(resources_path, executable_name)

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name)

def hex_to_ffmpeg_color(hex_color, alpha='ff'):
    try:
        hex_color = hex_color.lstrip('#')
        if len(hex_color) != 6: raise ValueError
        return f"0x{hex_color}{alpha}"
    except:
        return "0xFFFFFFFF"

def ffmpeg_safe_path(path):
    path = path.replace("\\", "/")
    if sys.platform == "win32":
        return path.replace(":", "\\:")
    return path

# --- LOGIC TẢI XUỐNG BẰNG THƯ VIỆN YT-DLP ---
# Lưu ý: yt_dlp sẽ được import sau khi setup path trong __main__

def ytdlp_progress_hook(d):
    # Gửi % download (đã bị App.jsx ẩn đi)
    if d['status'] == 'downloading':
        try:
            percent_str = d.get('_percent_str', '0.0%').replace('%','').strip()
            percent = float(percent_str)
            print(f"PROGRESS:DOWNLOAD:{percent}", flush=True)
        except (ValueError, TypeError): pass
    elif d['status'] == 'finished':
        print("PROGRESS:DOWNLOAD:100", flush=True)

def fetch_video_metadata(url, cookies_path):
    ydl_opts = {
        'quiet': True, 
        'no_warnings': True, 
        'noplaylist': True,
        'encoding': 'utf-8',  # Force UTF-8 encoding
    }
    if cookies_path and os.path.exists(cookies_path): ydl_opts['cookiefile'] = cookies_path
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl: return ydl.extract_info(url, download=False)
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
    
    if cookies_path and os.path.exists(cookies_path): ydl_opts['cookiefile'] = cookies_path
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([url])
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
    
    if cookies_path and os.path.exists(cookies_path): ydl_opts['cookiefile'] = cookies_path
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

# --- CÁC HÀM XỬ LÝ FFMPEG ---
def run_command_with_live_output(cmd, total_duration=None):
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        encoding='utf-8', errors='replace', creationflags=creationflags
    )
    stdout_output, stderr_output = [], []
    ffmpeg_time_regex = re.compile(r"time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})")
    
    def stream_reader(stream, output_list, is_stderr=False):
        for line in iter(stream.readline, ''):
            trimmed_line = line.strip()
            output_list.append(trimmed_line)
            
            if total_duration and is_stderr:
                match = ffmpeg_time_regex.search(trimmed_line)
                if match:
                    h, m, s, ms = map(int, match.groups())
                    current_time_seconds = h * 3600 + m * 60 + s + ms / 100
                    percent = min(100, (current_time_seconds / total_duration) * 100)
                    print(f"PROGRESS:RENDER:{'%.2f' % percent}", flush=True)
                    continue
            
            if trimmed_line and not is_stderr: 
                print(trimmed_line, flush=True)
                
    stdout_thread = threading.Thread(target=stream_reader, args=(process.stdout, stdout_output))
    stderr_thread = threading.Thread(target=stream_reader, args=(process.stderr, stderr_output, True))
    stdout_thread.start(); stderr_thread.start(); stdout_thread.join(); stderr_thread.join()
    process.wait()
    
    if process.returncode != 0:
        for line in stderr_output:
            if line: print(f"FFMPEG_ERROR: {line}", flush=True)
        raise subprocess.CalledProcessError(process.returncode, cmd, output='\n'.join(stdout_output), stderr='\n'.join(stderr_output))

def download_thumbnail(thumbnail_url, dest_path):
    urllib.request.urlretrieve(thumbnail_url, dest_path)
    if not os.path.exists(dest_path): raise FileNotFoundError("Could not download thumbnail")

def get_video_duration(video_path, ffmpeg_path):
    """Lấy độ dài video bằng ffprobe"""
    try:
        ffprobe_path = get_executable_path("ffprobe", os.path.dirname(ffmpeg_path))
        cmd = [
            ffprobe_path, '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1', video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        duration = float(result.stdout.strip())
        return duration
    except Exception as e:
        print(f"WARNING: Không thể lấy độ dài video: {e}", flush=True)
        return 0

def build_ffmpeg_filter(layout, input_map, start, duration, part_num, resources_path):
    layout.sort(key=lambda x: int(x.get('zIndex', 0)))
    filters, last_stream = ["color=s=720x1280:c=black[canvas]"], "canvas"
    overlay_count = 0
    
    for item in layout:
        if item.get('type') == 'text' or item.get('id') not in input_map: continue
        
        input_index = input_map.get(item['id'])
        w = item.get('width', 720) 
        h = item.get('height', 1280)
        x = item.get('x', 0) 
        y = item.get('y', 0) 
        
        scaled_stream, output_stream = f"s{overlay_count}", f"bg{overlay_count + 1}"
        
        # Ưu tiên GPU: sử dụng GPU-accelerated scale nếu có NVIDIA GPU
        # scale_npp chỉ hoạt động với CUDA frames (cần hwaccel cuda)
        # Nếu không có CUDA, dùng CPU scale
        scale_filter = f"scale={w}:{h},setsar=1"
        
        if item['type'] == 'video': filters.append(f"[{input_index}:v]trim=start={start}:duration={duration},setpts=PTS-STARTPTS,{scale_filter}[{scaled_stream}]")
        else: filters.append(f"[{input_index}:v]{scale_filter}[{scaled_stream}]") 
        
        filters.append(f"[{last_stream}][{scaled_stream}]overlay={x}:{y}[{output_stream}]")
        last_stream, overlay_count = output_stream, overlay_count + 1
    
    for item in layout:
      if item.get('type') == 'text':
        style = item.get("textStyle", {}); content = item.get("content", " ")
        text_to_draw = f"Part {part_num}" if item.get('id') == 'text-placeholder' else str(content)
        text_to_draw = text_to_draw.replace("'", "’").replace(":", "\\:").replace("%", "\\%")
        font_size = style.get("fontSize", 70); font_color = hex_to_ffmpeg_color(style.get("fontColor", "#FFFFFF"))
        border_w = style.get("outlineWidth", 2); border_color = hex_to_ffmpeg_color(style.get("outlineColor", "#000000"))
        shadow_color = hex_to_ffmpeg_color(style.get("shadowColor", "#000000"), "80")
        shadow_x = style.get("shadowDepth", 2); shadow_y = style.get("shadowDepth", 2)
        font_family_name = style.get("fontFamily", "arial.ttf").replace("'", "").replace(":", "\\:")

        text_x_base = item.get('x', 0)
        text_w_base = item.get('width', 720) 
        text_y_base = item.get('y', 0)
        text_h_base = item.get('height', 100)
        
        text_x = (text_x_base or 0) + ((text_w_base or 720) / 2)
        text_y = (text_y_base or 0) + ((text_h_base or 100) / 2)

        box_color_hex = style.get("boxColor", "#000000")
        box_opacity = style.get("boxOpacity", 0.5) 
        box_padding = style.get("boxPadding", 10) 
        box_opacity_hex = format(int(box_opacity * 255), 'x').zfill(2)
        box_color_ffmpeg = hex_to_ffmpeg_color(box_color_hex, box_opacity_hex)
        font_filename = font_family_name if font_family_name else "arial.ttf"
        font_file_path = os.path.join(resources_path, 'assets', font_filename)
        safe_font_file_path = ffmpeg_safe_path(font_file_path)

        drawtext_filter = (
            f"drawtext="
            f"fontfile='{safe_font_file_path}':" 
            f"text='{text_to_draw}':"
            f"fontsize={font_size}:"
            f"fontcolor={font_color}:"
            f"x={text_x}-(text_w/2):"
            f"y={text_y}-(text_h/2):"
            f"borderw={border_w}:"
            f"bordercolor={border_color}:"
            f"shadowcolor={shadow_color}:"
            f"shadowx={shadow_x}:"
            f"shadowy={shadow_y}:"
            f"box=1:"
            f"boxcolor={box_color_ffmpeg}:"
            f"boxborderw={box_padding}"
        )
        
        output_stream = f"txt{overlay_count}"; filters.append(f"[{last_stream}]{drawtext_filter}[{output_stream}]")
        last_stream = output_stream; overlay_count += 1
        
    if last_stream != "canvas": filters.append(f"[{last_stream}]copy[final_v]")
    else: filters.append(f"[canvas]copy[final_v]")
    filters.append(f"[0:a]atrim=start={start}:duration={duration},asetpts=PTS-STARTPTS[final_a]")
    return ";".join(filters), "final_v"

def process_video(audio_url, video_url1, video_url2, video_speed1, video_speed2, num_parts, save_path, part_duration, layout_file, encoder, resources_path, user_data_path):
    """Xử lý: tải audio+thumb từ link 1, 2 video từ link 2 và 3, áp dụng tốc độ phát, ghép lại, duplicate nếu cần, rồi cắt"""
    with open(layout_file, 'r', encoding='utf-8') as f: layout = json.load(f)

    output_dir = save_path or os.path.join(user_data_path, "output")
    temp_dir = os.path.join(user_data_path, "temp_files")
    
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(temp_dir, exist_ok=True)
    
    ffmpeg_path = get_executable_path("ffmpeg", resources_path)
    user_cookie_path = os.path.join(user_data_path, 'cookies.txt')
    cookies_path_to_use = user_cookie_path if os.path.exists(user_cookie_path) else ""

    try:
        # Lấy thông tin từ link 1 (audio + thumbnail)
        print("STATUS: Lấy thông tin từ Link 1 (Audio + Thumbnail)...", flush=True)
        audio_info = fetch_video_metadata(audio_url, cookies_path_to_use)
        audio_title, audio_id, thumbnail_url = audio_info['title'], audio_info['id'], audio_info['thumbnail']
        sanitized_title = sanitize_filename(audio_title)
        
        # Tải audio và thumbnail từ link 1
        print("STATUS: Tải audio từ Link 1...", flush=True)
        audio_path = os.path.join(temp_dir, f"{audio_id}_audio.mp3")
        download_audio_only(audio_url, ffmpeg_path, audio_path, cookies_path_to_use)
        
        print("STATUS: Tải thumbnail từ Link 1...", flush=True)
        thumbnail_path = os.path.join(temp_dir, f"{audio_id}_thumb.jpg")
        download_thumbnail(thumbnail_url, thumbnail_path)
        
        # Lấy thông tin từ link 2 (video 1)
        print("STATUS: Lấy thông tin từ Link 2 (Video 1)...", flush=True)
        video_info1 = fetch_video_metadata(video_url1, cookies_path_to_use)
        video_id1 = video_info1['id']
        
        # Lấy thông tin từ link 3 (video 2)
        print("STATUS: Lấy thông tin từ Link 3 (Video 2)...", flush=True)
        video_info2 = fetch_video_metadata(video_url2, cookies_path_to_use)
        video_id2 = video_info2['id']
        
        # Hàm helper để tải video không audio
        def download_video_no_audio(url, video_id, output_path):
            output_template = os.path.splitext(output_path)[0]
            ydl_opts = {
                'format': 'bestvideo[ext=mp4]/bestvideo',
                'outtmpl': f'{output_template}.%(ext)s',
                'ffmpeg_location': os.path.dirname(ffmpeg_path),
                'progress_hooks': [ytdlp_progress_hook],
                'noplaylist': True,
                'quiet': True,
                'no_warnings': True,
                'encoding': 'utf-8',
            }
            if cookies_path_to_use and os.path.exists(cookies_path_to_use): 
                ydl_opts['cookiefile'] = cookies_path_to_use
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                    downloaded_files = [f for f in os.listdir(temp_dir) if f.startswith(os.path.basename(output_template)) and not f.endswith('.mp4')]
                    if downloaded_files:
                        downloaded_file = os.path.join(temp_dir, downloaded_files[0])
                        if not downloaded_file.endswith('.mp4'):
                            cmd = [ffmpeg_path, '-y', '-i', downloaded_file, '-c:v', 'copy', '-an', output_path]
                            run_command_with_live_output(cmd)
                            os.remove(downloaded_file)
                        else:
                            os.rename(downloaded_file, output_path)
                    else:
                        final_video_path = f"{output_template}.mp4"
                        if os.path.exists(final_video_path):
                            if os.path.exists(output_path):
                                os.remove(output_path)
                            os.rename(final_video_path, output_path)
            except Exception as e:
                print(f"STATUS: Không tải được video only, đang tải video+audio rồi tách audio...", flush=True)
                temp_video_with_audio = os.path.join(temp_dir, f"{video_id}_temp.mp4")
                download_main_video(url, ffmpeg_path, temp_video_with_audio, cookies_path_to_use)
                cmd = [ffmpeg_path, '-y', '-i', temp_video_with_audio, '-c:v', 'copy', '-an', output_path]
                run_command_with_live_output(cmd)
                if os.path.exists(temp_video_with_audio):
                    os.remove(temp_video_with_audio)
        
        # Tải video 1
        print("STATUS: Tải video 1 từ Link 2 (không audio)...", flush=True)
        video_path1 = os.path.join(temp_dir, f"{video_id1}_video1.mp4")
        download_video_no_audio(video_url1, video_id1, video_path1)
        
        # Tải video 2 (không audio) từ link 3
        print("STATUS: Tải video 2 từ Link 3 (không audio)...", flush=True)
        video_path2 = os.path.join(temp_dir, f"{video_id2}_video2.mp4")
        download_video_no_audio(video_url2, video_id2, video_path2)
        
        # Lấy độ dài audio và các video (trước khi áp dụng speed)
        audio_duration = get_video_duration(audio_path, ffmpeg_path)
        original_video_duration1 = get_video_duration(video_path1, ffmpeg_path)
        original_video_duration2 = get_video_duration(video_path2, ffmpeg_path)
        
        if audio_duration <= 0:
            raise Exception("Không thể lấy độ dài audio.")
        if original_video_duration1 <= 0:
            raise Exception("Không thể lấy độ dài video 1.")
        if original_video_duration2 <= 0:
            raise Exception("Không thể lấy độ dài video 2.")
        
        # Áp dụng tốc độ phát cho video 1 nếu khác 1.0
        if video_speed1 != 1.0:
            print(f"STATUS: Áp dụng tốc độ phát {video_speed1}x cho Video 1...", flush=True)
            speeded_video_path1 = os.path.join(temp_dir, f"{video_id1}_video1_speeded.mp4")
            cmd = [
                ffmpeg_path, '-y', '-i', video_path1,
                '-filter:v', f'setpts=PTS/{video_speed1}',
                '-an'
            ]
            if 'nvenc' in encoder:
                cmd += ['-c:v', encoder, '-preset', 'p5', '-cq', '23', '-b:v', '0']
            elif 'amf' in encoder:
                cmd += ['-c:v', encoder, '-quality', 'balanced', '-qp', '23']
            elif 'qsv' in encoder:
                cmd += ['-c:v', encoder, '-preset', 'medium', '-global_quality', '23']
            else:
                cmd += ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23', '-threads', '4']
            cmd.append(speeded_video_path1)
            run_command_with_live_output(cmd)
            video_path1 = speeded_video_path1
            # Duration sau khi áp dụng speed = original_duration / speed
            video_duration1 = original_video_duration1 / video_speed1
        else:
            video_duration1 = original_video_duration1
        
        # Áp dụng tốc độ phát cho video 2 nếu khác 1.0
        if video_speed2 != 1.0:
            print(f"STATUS: Áp dụng tốc độ phát {video_speed2}x cho Video 2...", flush=True)
            speeded_video_path2 = os.path.join(temp_dir, f"{video_id2}_video2_speeded.mp4")
            cmd = [
                ffmpeg_path, '-y', '-i', video_path2,
                '-filter:v', f'setpts=PTS/{video_speed2}',
                '-an'
            ]
            if 'nvenc' in encoder:
                cmd += ['-c:v', encoder, '-preset', 'p5', '-cq', '23', '-b:v', '0']
            elif 'amf' in encoder:
                cmd += ['-c:v', encoder, '-quality', 'balanced', '-qp', '23']
            elif 'qsv' in encoder:
                cmd += ['-c:v', encoder, '-preset', 'medium', '-global_quality', '23']
            else:
                cmd += ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23', '-threads', '4']
            cmd.append(speeded_video_path2)
            run_command_with_live_output(cmd)
            video_path2 = speeded_video_path2
            # Duration sau khi áp dụng speed = original_duration / speed
            video_duration2 = original_video_duration2 / video_speed2
        else:
            video_duration2 = original_video_duration2
        
        # Nếu video ngắn hơn audio, duplicate video cho bằng audio
        if video_duration1 < audio_duration:
            print(f"STATUS: Video 1 ({video_duration1:.2f}s) ngắn hơn Audio ({audio_duration:.2f}s). Đang duplicate video 1...", flush=True)
            loop_count = int(math.ceil(audio_duration / video_duration1))
            looped_video_path1 = os.path.join(temp_dir, f"{video_id1}_video1_looped.mp4")
            cmd = [
                ffmpeg_path, '-y', '-stream_loop', str(loop_count), '-i', video_path1,
                '-t', str(audio_duration), '-an'
            ]
            if 'nvenc' in encoder:
                cmd += ['-c:v', encoder, '-preset', 'p5', '-cq', '23', '-b:v', '0']
            elif 'amf' in encoder:
                cmd += ['-c:v', encoder, '-quality', 'balanced', '-qp', '23']
            elif 'qsv' in encoder:
                cmd += ['-c:v', encoder, '-preset', 'medium', '-global_quality', '23']
            else:
                cmd += ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23', '-threads', '4']
            cmd.append(looped_video_path1)
            run_command_with_live_output(cmd)
            video_path1 = looped_video_path1
            video_duration1 = audio_duration
        
        if video_duration2 < audio_duration:
            print(f"STATUS: Video 2 ({video_duration2:.2f}s) ngắn hơn Audio ({audio_duration:.2f}s). Đang duplicate video 2...", flush=True)
            loop_count = int(math.ceil(audio_duration / video_duration2))
            looped_video_path2 = os.path.join(temp_dir, f"{video_id2}_video2_looped.mp4")
            cmd = [
                ffmpeg_path, '-y', '-stream_loop', str(loop_count), '-i', video_path2,
                '-t', str(audio_duration), '-an'
            ]
            if 'nvenc' in encoder:
                cmd += ['-c:v', encoder, '-preset', 'p5', '-cq', '23', '-b:v', '0']
            elif 'amf' in encoder:
                cmd += ['-c:v', encoder, '-quality', 'balanced', '-qp', '23']
            elif 'qsv' in encoder:
                cmd += ['-c:v', encoder, '-preset', 'medium', '-global_quality', '23']
            else:
                cmd += ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23', '-threads', '4']
            cmd.append(looped_video_path2)
            run_command_with_live_output(cmd)
            video_path2 = looped_video_path2
            video_duration2 = audio_duration
        
        # Tính toán số phần và thời lượng mỗi phần
        try:
            part_duration = float(part_duration)
        except ValueError:
            part_duration = 0.0

        if part_duration <= 0: 
            actual_num_parts = num_parts
            part_duration = audio_duration / num_parts 
        else:
            total_parts_by_duration = math.ceil(audio_duration / part_duration)
            actual_num_parts = min(num_parts, total_parts_by_duration)
        
        actual_num_parts = int(actual_num_parts)
        
        # Cắt thành các phần như app cũ
        for i in range(actual_num_parts):
            part_num = i + 1; start_time = i * part_duration
            
            output_path = os.path.join(output_dir, f"{sanitized_title}_Part_{part_num}.mp4")
            print(f"STATUS: Render Part {part_num}/{actual_num_parts}...", flush=True)
            
            # Ưu tiên GPU: thêm hwaccel để decode video trên GPU nếu dùng NVIDIA encoder
            cmd = [ffmpeg_path, '-y', '-hide_banner', '-loglevel', 'error']
            if 'nvenc' in encoder:
                # Decode video trên GPU để giảm tải CPU
                cmd += ['-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda']
            cmd += ['-i', video_path1, '-i', video_path2, '-i', thumbnail_path]
            
            input_map = {'video-placeholder-1': 0, 'video-placeholder-2': 1, 'thumbnail-placeholder': 2}; image_index = 3
            for item in layout:
                if item['type'] == 'image' and item['source'] and item['source'].startswith('data:image'):
                    try:
                        header, encoded = item['source'].split(',', 1); image_format = header.split(';')[0].split('/')[1]
                        image_data = base64.b64decode(encoded)
                        temp_image_path = os.path.join(temp_dir, f"temp_img_{item['id']}.{image_format}")
                        with open(temp_image_path, 'wb') as img_f: img_f.write(image_data)
                        cmd += ['-i', temp_image_path]; input_map[item['id']] = image_index; image_index += 1
                    except Exception as e: print(f"Warning: Could not process image {item['id']}: {e}")
            
            # Thêm audio input
            # Tính audio_input_index bằng cách đếm số lượng -i đã có trong cmd
            audio_input_index = cmd.count('-i')
            cmd += ['-i', audio_path]
            
            filter_complex, final_video_stream = build_ffmpeg_filter(layout, input_map, start_time, part_duration, part_num, resources_path)
            
            # Cập nhật filter để lấy audio từ input đúng (audio_input_index)
            filter_complex = filter_complex.replace('[0:a]', f'[{audio_input_index}:a]')
            
            cmd += ['-filter_complex', filter_complex, '-map', f'[{final_video_stream}]', '-map', '[final_a]']
            # Ưu tiên GPU: giảm CPU threads xuống 1 khi dùng GPU encoder để GPU làm nhiều việc hơn
            if 'nvenc' in encoder: 
                cmd += ['-c:v', encoder, '-preset', 'p5', '-cq', '23', '-b:v', '0', '-threads', '1']
            elif 'amf' in encoder: 
                cmd += ['-c:v', encoder, '-quality', 'balanced', '-qp', '23', '-threads', '1']
            elif 'qsv' in encoder: 
                cmd += ['-c:v', encoder, '-preset', 'medium', '-global_quality', '23', '-threads', '1']
            else: 
                # CPU encoder: dùng nhiều threads hơn
                import os
                cpu_count = os.cpu_count() or 4
                threads = min(cpu_count - 1, 6)  # Giữ lại 1 core cho hệ thống, tối đa 6 threads
                cmd += ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23', '-threads', str(threads)]
            cmd += ['-c:a', 'aac', '-b:a', '192k', '-r', '30', '-shortest', output_path]
            print(f"STATUS: Khởi tạo FFMPEG cho Part {part_num} (có thể mất vài phút)...", flush=True)
            
            run_command_with_live_output(cmd, total_duration=part_duration)
            print(f"RESULT:{output_path}", flush=True)
        print("STATUS: Hoàn tất tất cả các phần!", flush=True)
        print("LINK_SUCCESS", flush=True)
    except Exception as e:
        error_msg = str(e)
        print(f"PYTHON_ERROR: {error_msg}", file=sys.stderr, flush=True)
        print(f"LINK_ERROR: {error_msg}", flush=True)
    finally:
        print("STATUS: Dọn dẹp file tạm...", flush=True)
        if os.path.exists(temp_dir): 
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                print(f"WARNING: Không thể xóa thư mục tạm: {e}", flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Video Processing Script")
    parser.add_argument('--resources-path', required=True)
    parser.add_argument('--user-data-path', required=True)
    parser.add_argument('--audio-url', type=str, required=True)
    parser.add_argument('--video-url1', type=str, required=True)
    parser.add_argument('--video-url2', type=str, required=True)
    parser.add_argument('--video-speed1', type=float, default=1.0)
    parser.add_argument('--video-speed2', type=float, default=1.0)
    parser.add_argument('--layout-file', type=str, required=True)
    parser.add_argument('--parts', type=int, default=1)
    parser.add_argument('--save-path', type=str, default="")
    parser.add_argument('--part-duration', type=str, default="0")
    parser.add_argument('--encoder', type=str, default='libx264')
    args = parser.parse_args()
    
    # Tự động cài đặt yt-dlp nếu chưa có
    if not ensure_yt_dlp():
        sys.exit(1)
    
    # Import yt_dlp (đã được cài đặt hoặc đã có sẵn)
    import yt_dlp
    
    try:
        process_video(args.audio_url, args.video_url1, args.video_url2, args.video_speed1, args.video_speed2, args.parts, args.save_path, args.part_duration, args.layout_file, args.encoder, args.resources_path, args.user_data_path)
        sys.exit(0)  # Thành công
    except Exception as e:
        # Lỗi đã được xử lý trong process_video, chỉ cần exit với code lỗi
        sys.exit(1)  # Lỗi