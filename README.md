# Trash Video Tool

Ứng dụng tự động cắt và dựng video từ YouTube với nhiều tính năng mạnh mẽ.

## Tính năng

- 📥 Tải video, audio và thumbnail từ YouTube
- ✂️ Tự động cắt video thành nhiều phần
- 🎨 Editor layout với canvas trực quan
- 🎬 Hỗ trợ nhiều encoder (GPU/CPU)
- ⚡ Xử lý hàng chờ (queue) nhiều video
- 🎯 Điều chỉnh tốc độ phát video
- 🖼️ Thêm text, hình ảnh vào video
- 💾 Lưu template layout để tái sử dụng

## Yêu cầu hệ thống

- Windows 10/11
- Python 3.x (tự động cài đặt yt-dlp)
- FFmpeg (đã bundle trong ứng dụng)
- GPU NVIDIA/AMD/Intel (tùy chọn, để tăng tốc encoding)

## Cài đặt

1. Clone repository:
```bash
git clone https://github.com/luanvo1910/TrashVideoTool.git
cd TrashVideoTool
```

2. Cài đặt dependencies:
```bash
npm install
cd renderer
npm install
cd ..
```

3. Chạy ứng dụng:
```bash
npm start
```

## Build

Để build ứng dụng thành file cài đặt:

```bash
npm run build
```

File cài đặt sẽ được tạo trong thư mục `release`.

## Sử dụng

1. Thêm 3 links YouTube:
   - Link 1: Audio + Thumbnail
   - Link 2: Video 1 (chỉ video, không audio)
   - Link 3: Video 2 (chỉ video, không audio)

2. Điều chỉnh tốc độ phát cho Video 1 và Video 2 (mặc định: 1.0x)

3. Thiết lập số phần và thời lượng mỗi phần

4. Chọn encoder (khuyến nghị: NVIDIA H264 cho GPU)

5. Click "BẮT ĐẦU RENDER"

## Cấu trúc dự án

```
TrashTool/
├── main.js              # Electron main process
├── preload.js           # Preload script
├── editor.py            # Python script xử lý video
├── resources/           # Resources (FFmpeg, fonts, etc.)
├── renderer/            # React frontend
│   ├── src/
│   │   ├── App.jsx      # Main component
│   │   └── components/  # UI components
└── package.json
```

## License

ISC

## Author

LuanVo

