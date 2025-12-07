"""
Module xử lý video với ffmpeg
"""
import sys
import os
import subprocess
import re
import threading
from utils import get_executable_path, hex_to_ffmpeg_color, ffmpeg_safe_path

def run_command_with_live_output(cmd, total_duration=None):
    """Chạy command và hiển thị output real-time, track progress nếu có"""
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
    stdout_thread.start()
    stderr_thread.start()
    stdout_thread.join()
    stderr_thread.join()
    process.wait()
    
    if process.returncode != 0:
        for line in stderr_output:
            if line: 
                print(f"FFMPEG_ERROR: {line}", flush=True)
        raise subprocess.CalledProcessError(
            process.returncode, cmd, 
            output='\n'.join(stdout_output), 
            stderr='\n'.join(stderr_output)
        )

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
    """Xây dựng filter complex cho ffmpeg từ layout"""
    layout.sort(key=lambda x: int(x.get('zIndex', 0)))
    filters, last_stream = ["color=s=720x1280:c=black[canvas]"], "canvas"
    overlay_count = 0
    
    # Xử lý video và image
    for item in layout:
        if item.get('type') == 'text' or item.get('id') not in input_map: 
            continue
        
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
        
        if item['type'] == 'video': 
            filters.append(f"[{input_index}:v]trim=start={start}:duration={duration},setpts=PTS-STARTPTS,{scale_filter}[{scaled_stream}]")
        else: 
            filters.append(f"[{input_index}:v]{scale_filter}[{scaled_stream}]") 
        
        filters.append(f"[{last_stream}][{scaled_stream}]overlay={x}:{y}[{output_stream}]")
        last_stream, overlay_count = output_stream, overlay_count + 1
    
    # Xử lý text
    for item in layout:
        if item.get('type') == 'text':
            style = item.get("textStyle", {})
            content = item.get("content", " ")
            text_to_draw = f"Part {part_num}" if item.get('id') == 'text-placeholder' else str(content)
            text_to_draw = text_to_draw.replace("'", "’").replace(":", "\\:").replace("%", "\\%")
            font_size = style.get("fontSize", 70)
            font_color = hex_to_ffmpeg_color(style.get("fontColor", "#FFFFFF"))
            border_w = style.get("outlineWidth", 2)
            border_color = hex_to_ffmpeg_color(style.get("outlineColor", "#000000"))
            shadow_color = hex_to_ffmpeg_color(style.get("shadowColor", "#000000"), "80")
            shadow_x = style.get("shadowDepth", 2)
            shadow_y = style.get("shadowDepth", 2)
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
            
            output_stream = f"txt{overlay_count}"
            filters.append(f"[{last_stream}]{drawtext_filter}[{output_stream}]")
            last_stream = output_stream
            overlay_count += 1
    
    if last_stream != "canvas": 
        filters.append(f"[{last_stream}]copy[final_v]")
    else: 
        filters.append(f"[canvas]copy[final_v]")
    filters.append(f"[0:a]atrim=start={start}:duration={duration},asetpts=PTS-STARTPTS[final_a]")
    return ";".join(filters), "final_v"

