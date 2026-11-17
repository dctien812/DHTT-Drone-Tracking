# lab - màn hình lab Drone Tracking (mốc L0)

Chương trình Python đọc hình (file video hoặc webcam), nhận diện drone + theo dõi ID bằng YOLO,
phát trang web: hình trực tiếp có khung/ID, bấm khung để KHÓA, nút "Khóa"/"Hủy", hiện góc lệch và
khoảng cách ước lượng của vật thể đang khóa, log có dấu thời gian.
**Chỉ hiển thị và chọn mục tiêu: không gửi lệnh tới drone, bộ điều khiển bay hay thiết bị nào.**

## Chạy thử trên PC (WSL), chỉ localhost
```
wsl -d Ubuntu-24.04 -- bash /mnt/d/Personal/Drone-Tracking/lab/run_demo.sh [video] [cổng]
```
Mở `http://localhost:8080/` bằng trình duyệt Windows. Dừng: Ctrl+C. Chạy trực tiếp:
`cd lab && ~/venv-vision/bin/python -m labview --source file:/đường/dẫn/video.mp4 --port 8080`
(`--source camera:0` cho webcam, `--help` xem hết tham số). Test: `cd lab && ~/venv-vision/bin/python -m pytest -q`.
Gói thêm (đã cài vào venv): `flask`, `pytest` (xem `requirements.txt`).

## Mở ra mạng nội bộ (laptop khác mở trang) - BẮT BUỘC mật khẩu
```
echo 'mat-khau-dai-it-nhat-8-ky-tu' > ~/labview.pw && chmod 600 ~/labview.pw     # đặt NGOÀI thư mục git
python -m labview --source file:... --allow-network --password-file ~/labview.pw
# hoặc: export LABVIEW_PASSWORD=...  rồi --allow-network
```
Không mật khẩu (hoặc < 8 ký tự) thì chương trình từ chối khởi động (mã thoát 2). Trình duyệt hỏi
đăng nhập: tên `lab`, mật khẩu như đã đặt. Không có mật khẩu mặc định; mật khẩu không được ghi vào log.
Lưu ý: HTTP Basic qua HTTP thường không mã hóa, chỉ dùng trong mạng lab tin cậy. Sai mật khẩu 5 lần/phút từ một IP thì bị chặn 1 phút.

## Điểm cuối HTTP
| Method | Đường dẫn | Việc |
|---|---|---|
| GET | `/`, `/static/app.js`, `/static/app.css` | trang (file cố định nạp sẵn, không đọc file theo đường dẫn người dùng) |
| GET | `/stream.mjpg` | luồng MJPEG (tối đa 4 người xem) |
| GET | `/snapshot.jpg` | khung hiện tại (đã vẽ) |
| GET | `/api/state` | JSON: fps, ms xử lý, độ trễ, CPU, tracks, lock, notice, events |
| POST | `/api/lock` | body JSON đúng một dạng: `{"x":0..1,"y":0..1}` (tọa độ bấm chuẩn hóa) / `{"track_id":N}` / `{"best":true}` |
| POST | `/api/release` | `{}` bỏ khóa |
POST cần `Content-Type: application/json`, `Origin` (nếu có) phải trùng `Host`, và xác thực khi có mật khẩu.

## Kiến trúc
- Luồng 1 `capture`: `FrameSource.read()` -> giữ KHÔNG xếp hàng, chỉ "khung mới nhất" (suy luận chậm thì bỏ khung cũ).
- Luồng 2 `infer`: thu nhỏ (<=960 px) -> `Detector.track()` (YOLO + ByteTrack) -> `LockManager.update()` -> hình học -> `LockSink.on_lock()` -> vẽ -> JPEG -> công bố.
- Luồng HTTP (werkzeug threaded) chỉ đọc kết quả công bố.
- Giao diện mở rộng: `FrameSource` (`sources.py`: file, camera OpenCV; thêm `picamera2` bằng lớp con + đăng ký ở `make_source`), `Detector`, `LockSink` (`outputs.py`: hiện có `LogSink`; sau này `ServoSink` một trục gật, đọc trạng thái FC).
- Hình học (`geometry.py`): góc = atan((u-cx)/fx), atan((cy-v)/fy) (+ = phải/lên); khoảng cách = fx * rộng_thật / rộng_khung_bao, mặc định rộng 0,30 m (`--real-width`), luôn hiện "giả định mục tiêu rộng X m". `fx` mặc định suy từ `--hfov` (66 độ) và khung hình; ghi đè bằng `--fx --fy --cx --cy` (pixel của khung ĐÃ xử lý, sau thu nhỏ).
- Tự bỏ khóa khi mất vật thể quá `--lost-timeout` (2 s), báo trên màn hình và trong log.

## Chuyển sang Raspberry Pi 5 (chưa làm)
- Thêm `Picamera2Source(FrameSource)`: `Picamera2().create_video_configuration(main={"size":(1280,720),"format":"RGB888"})`, `capture_array()` trả khung (RGB888 của picamera2 thực chất là BGR cho OpenCV), `live=True`.
- `--hfov` cho Camera Module 3 Wide khoảng 102 độ (theo nhà sản xuất, CHƯA kiểm); góc rộng có méo ống kính, cần hiệu chỉnh nếu muốn góc chính xác.
- Suy luận trên Pi 5 cần NCNN/ONNX thay `.pt`; tốc độ khung hình chưa đo.

## Dùng lại từ `AI-6` (chỉ đọc ý tưởng/mẫu)
`YOLOv8/video_processor.py`: mô hình luồng camera/suy luận tách rời, `grab()+retrieve()` lấy khung mới nhất, mở V4L2 MJPG buffer 1; `frame_processor.py`: gọi `model.track(persist=True, bytetrack)`. `AI-6` không có mã picamera2 (chỉ comment V4L2). Không dùng `drone_tg\`.

## Công cụ kiểm chứng
`e2e_check.sh` (chạy thật bằng curl, tự tắt máy chủ), `fp_check.py` (đếm khung "drone" giả), `tools_to_png.py`. Ảnh chụp: `docs/`.
