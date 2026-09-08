# Vietnamese TTS Dataset Builder (Local Windows/Linux)

Ứng dụng Python xử lý và cắt file audio audiobook tiếng Việt dài theo transcript đã căn mốc thời gian (start, end, text) thành bộ Dataset chuẩn phục vụ fine-tune các mô hình Text-To-Speech (VITS, XTTS v2, F5-TTS, StyleTTS 2, Piper, FastSpeech 2).

## 🌟 Tính Năng Nổi Bật

1. **Audio Decoding chuẩn xác:**
   - Hỗ trợ nguồn: MP3, WAV, M4A, FLAC, OGG.
   - Giải mã nguồn 1 lần duy nhất sang 16-bit PCM s16le Mono tại 24,000 Hz (hoặc 44,100 Hz / 48,000 Hz) trước khi cắt. Không decode lặp lại.
2. **Quy tắc cắt và bảo toàn ngữ âm:**
   - Cấu hình đệm đầu/cuối `padding_before` (mặc định 0.15s) và `padding_after` (mặc định 0.20s).
   - Tự động chống chồng lấn (clamp overlap) với câu liền kề.
3. **VAD / Silence Refinement:**
   - Tìm kiếm ±300ms quanh mốc thời gian để dò khoảng lặng (silence) hoặc ranh giới bắt đầu/kết thúc phát âm gần nhất, tránh bị cắt cụt phụ âm đầu hoặc đuôi câu mà không làm thay đổi nội dung transcript.
4. **Tự động ghép câu ngắn (Auto Merge):**
   - Tự động gộp các câu `< min_duration` (ví dụ: "Không.", "Được.") với câu kế tiếp nếu khoảng lặng giữa hai câu nhỏ hơn ngưỡng cho phép và tổng độ dài `<= max_duration`.
5. **Làm sạch văn bản tiếng Việt:**
   - Chuẩn hóa Unicode NFC, xóa khoảng trắng thừa trước dấu câu, loại bỏ thẻ HTML, giữ nguyên dấu thanh tiếng Việt và tên riêng.
6. **Kiểm tra chất lượng (Quality Check & Validator):**
   - Kiểm tra RMS, Peak, Clipping, tỷ lệ Silence, thời lượng và chấm điểm Quality Score (0 - 100).
   - Tự động tách các câu hỏng/lỗi vào `rejected.csv`.
7. **Khả năng Phục hồi (Resume Capability):**
   - Lưu trạng thái tiến trình qua SQLite. Nếu đang cắt 5,000 câu mà bị tắt giữa chừng, lần sau mở lại sẽ tiếp tục từ câu chưa cắt.
8. **Xem trước Waveform & Sửa mốc thời gian:**
   - Nghe thử từng câu trong UI, cho phép sửa lại text/start/end và nhấn **Regenerate** để cắt lại ngay lập tức.
9. **Xuất gói ZIP 1-Click:**
   - Xuất ra file `dataset.zip` gồm `wavs/`, `metadata.csv` (chuẩn LJSpeech `000001.wav|Văn bản`), `metadata.json`, `rejected.csv`, `dataset_report.json`.

---

## 🚀 Cài Đặt & Sử Dụng trên Windows

### Bước 1: Cài đặt Python và FFmpeg
1. **Python 3.10 hoặc 3.11:** Tải tại [python.org](https://www.python.org/downloads/). Nhớ tích chọn **"Add Python to PATH"**.
2. **FFmpeg:** Mở PowerShell và gõ:
   ```powershell
   winget install Gyan.FFmpeg
   ```
   *(Hoặc tải từ https://www.gyan.dev/ffmpeg/builds/ và thêm `bin` vào Environment PATH).*

### Bước 2: Chạy ứng dụng
- **Cách 1:** Nhấp đúp chuột vào file `run_windows.bat`
- **Cách 2:** Mở Terminal tại thư mục này và gõ:
  ```bash
  pip install -r requirements.txt
  python app.py
  ```
- Mở trình duyệt tại: **http://127.0.0.1:7860**

---

## 📁 Cấu Trúc Dataset Đầu Ra

```
output_dataset/
│
├── wavs/
│   ├── 000001.wav
│   ├── 000002.wav
│   └── ...
│
├── metadata.csv        # 000001.wav|Ta mỗi ngày nhận được một hệ thống mới.
├── metadata.json       # Chi tiết mốc thời gian, duration, metrics
├── rejected.csv        # Các mẫu bị từ chối kèm lý do
└── dataset_report.json # Thống kê số lượng, tổng thời lượng, biểu đồ phân bố
```
