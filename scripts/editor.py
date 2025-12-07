"""
Main script điều phối - xử lý video từ YouTube
"""
import sys
import os
import io
import json
import argparse
import base64
import math
import shutil

# --- SETUP ENCODING NGAY TỪ ĐẦU (giống ProjectRB) ---
# Phải setup encoding TRƯỚC khi import bất kỳ module nào để tránh lỗi
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

# Import các module (sau khi đã setup encoding)
from utils import get_executable_path, sanitize_filename
from downloader import (
    ensure_yt_dlp, fetch_video_metadata, download_main_video, 
    download_audio_only, download_thumbnail
)
from video_processor import (
    run_command_with_live_output, get_video_duration, build_ffmpeg_filter
)

def process_video(audio_url, video_url, video_speed,
                  num_parts, save_path, part_duration, layout_file, encoder, 
                  resources_path, user_data_path):
    """Xử lý: tải audio+thumb từ link 1, video từ link 2, áp dụng tốc độ phát, ghép lại, duplicate nếu cần, rồi cắt"""
    with open(layout_file, 'r', encoding='utf-8') as f: 
        layout = json.load(f)

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
        try:
            audio_info = fetch_video_metadata(audio_url, cookies_path_to_use)
            audio_title, audio_id, thumbnail_url = audio_info['title'], audio_info['id'], audio_info['thumbnail']
            sanitized_title = sanitize_filename(audio_title)
        except Exception as e:
            print(f"PYTHON_ERROR: Lỗi khi lấy metadata từ Link 1: {e}", flush=True)
            raise Exception(f"Lỗi khi lấy metadata từ Link 1: {e}")
        
        # Tải audio và thumbnail từ link 1
        print("STATUS: Tải audio từ Link 1...", flush=True)
        try:
            audio_path = os.path.join(temp_dir, f"{audio_id}_audio.mp3")
            download_audio_only(audio_url, ffmpeg_path, audio_path, cookies_path_to_use)
            if not os.path.exists(audio_path):
                raise Exception(f"Audio không được tải thành công: {audio_path}")
        except Exception as e:
            print(f"PYTHON_ERROR: Lỗi khi tải audio từ Link 1: {e}", flush=True)
            raise
        
        print("STATUS: Tải thumbnail từ Link 1...", flush=True)
        try:
            thumbnail_path = os.path.join(temp_dir, f"{audio_id}_thumb.jpg")
            download_thumbnail(thumbnail_url, thumbnail_path)
            if not os.path.exists(thumbnail_path):
                raise Exception(f"Thumbnail không được tải thành công: {thumbnail_path}")
        except Exception as e:
            print(f"PYTHON_ERROR: Lỗi khi tải thumbnail từ Link 1: {e}", flush=True)
            raise
        
        # Lấy thông tin từ link 2 (video)
        print("STATUS: Lấy thông tin từ Link 2 (Video)...", flush=True)
        try:
            video_info = fetch_video_metadata(video_url, cookies_path_to_use)
            video_id = video_info['id']
        except Exception as e:
            print(f"PYTHON_ERROR: Lỗi khi lấy metadata từ Link 2: {e}", flush=True)
            raise Exception(f"Lỗi khi lấy metadata từ Link 2: {e}")
        
        # Hàm helper để tải video không audio
        # Luôn tải video+audio rồi tách audio để tránh phải chờ download 2 lần
        def download_video_no_audio(url, video_id, output_path):
            print(f"STATUS: Tải video+audio rồi tách audio...", flush=True)
            temp_video_with_audio = os.path.join(temp_dir, f"{video_id}_temp.mp4")
            try:
                download_main_video(url, ffmpeg_path, temp_video_with_audio, cookies_path_to_use)
                if not os.path.exists(temp_video_with_audio):
                    raise Exception(f"Video không được tải thành công: {temp_video_with_audio}")
                print(f"STATUS: Tách audio khỏi video...", flush=True)
                cmd = [ffmpeg_path, '-y', '-i', temp_video_with_audio, '-c:v', 'copy', '-an', output_path]
                run_command_with_live_output(cmd)
                if not os.path.exists(output_path):
                    raise Exception(f"Video sau khi tách audio không tồn tại: {output_path}")
            except Exception as e:
                print(f"PYTHON_ERROR: Lỗi khi tải video: {e}", flush=True)
                raise
            finally:
                # Dọn dẹp file tạm
                if os.path.exists(temp_video_with_audio):
                    try:
                        os.remove(temp_video_with_audio)
                    except:
                        pass
        
        # Tải video (không audio)
        print("STATUS: Tải video từ Link 2 (không audio)...", flush=True)
        try:
            video_path = os.path.join(temp_dir, f"{video_id}_video.mp4")
            download_video_no_audio(video_url, video_id, video_path)
            if not os.path.exists(video_path):
                raise Exception(f"Video không được tải thành công: {video_path}")
        except Exception as e:
            print(f"PYTHON_ERROR: Lỗi khi tải video: {e}", flush=True)
            raise
        
        # Lấy độ dài audio và video (trước khi áp dụng speed)
        audio_duration = get_video_duration(audio_path, ffmpeg_path)
        original_video_duration = get_video_duration(video_path, ffmpeg_path)
        
        if audio_duration <= 0:
            raise Exception("Không thể lấy độ dài audio.")
        if original_video_duration <= 0:
            raise Exception("Không thể lấy độ dài video.")
        
        # Áp dụng tốc độ phát cho video nếu khác 1.0
        if video_speed != 1.0:
            print(f"STATUS: Áp dụng tốc độ phát {video_speed}x cho Video...", flush=True)
            speeded_video_path = os.path.join(temp_dir, f"{video_id}_video_speeded.mp4")
            cmd = [
                ffmpeg_path, '-y', '-i', video_path,
                '-filter:v', f'setpts=PTS/{video_speed}',
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
            cmd.append(speeded_video_path)
            run_command_with_live_output(cmd)
            video_path = speeded_video_path
            # Duration sau khi áp dụng speed = original_duration / speed
            video_duration = original_video_duration / video_speed
        else:
            video_duration = original_video_duration
        
        # Nếu video ngắn hơn audio, duplicate video cho bằng audio
        if video_duration < audio_duration:
            print(f"STATUS: Video ({video_duration:.2f}s) ngắn hơn Audio ({audio_duration:.2f}s). Đang duplicate video...", flush=True)
            loop_count = int(math.ceil(audio_duration / video_duration))
            looped_video_path = os.path.join(temp_dir, f"{video_id}_video_looped.mp4")
            cmd = [
                ffmpeg_path, '-y', '-stream_loop', str(loop_count), '-i', video_path,
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
            cmd.append(looped_video_path)
            run_command_with_live_output(cmd)
            video_path = looped_video_path
            video_duration = audio_duration
        
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
            part_num = i + 1
            start_time = i * part_duration
            
            output_path = os.path.join(output_dir, f"{sanitized_title}_Part_{part_num}.mp4")
            print(f"STATUS: Render Part {part_num}/{actual_num_parts}...", flush=True)
            
            # Không dùng hwaccel cuda vì filter phức tạp (setpts, scale, overlay) không hỗ trợ CUDA format
            # Decode trên CPU, encode trên GPU (nếu dùng GPU encoder)
            cmd = [ffmpeg_path, '-y', '-hide_banner', '-loglevel', 'error']
            cmd += ['-i', video_path, '-i', thumbnail_path]
            
            input_map = {'video-placeholder': 0, 'thumbnail-placeholder': 1}
            image_index = 3
            for item in layout:
                if item['type'] == 'image' and item['source'] and item['source'].startswith('data:image'):
                    try:
                        header, encoded = item['source'].split(',', 1)
                        image_format = header.split(';')[0].split('/')[1]
                        image_data = base64.b64decode(encoded)
                        temp_image_path = os.path.join(temp_dir, f"temp_img_{item['id']}.{image_format}")
                        with open(temp_image_path, 'wb') as img_f: 
                            img_f.write(image_data)
                        cmd += ['-i', temp_image_path]
                        input_map[item['id']] = image_index
                        image_index += 1
                    except Exception as e: 
                        print(f"Warning: Could not process image {item['id']}: {e}")
            
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
    parser.add_argument('--video-url', type=str, required=True)
    parser.add_argument('--video-speed', type=float, default=1.0)
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
        process_video(
            args.audio_url, args.video_url, args.video_speed,
            args.parts, args.save_path, 
            args.part_duration, args.layout_file, args.encoder, 
            args.resources_path, args.user_data_path
        )
        sys.exit(0)  # Thành công
    except Exception as e:
        # Lỗi đã được xử lý trong process_video, chỉ cần exit với code lỗi
        sys.exit(1)  # Lỗi
