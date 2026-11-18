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
echo 'mat-khau-dai-it-nhat-12-ky-tu' > ~/labview.pw && chmod 600 ~/labview.pw     # đặt NGOÀI thư mục git
python -m labview --source file:... --allow-network --host 192.168.1.50 --password-file ~/labview.pw
# hoặc: export LABVIEW_PASSWORD=...  rồi --allow-network --host <địa chỉ mạng nội bộ>
```
Không mật khẩu (hoặc < 12 ký tự) thì chương trình từ chối khởi động (mã thoát 2). `--password-file` bị từ chối
(mã 2) nếu nhóm/người khác đọc được (quyền rộng hơn 600, kiểm trên Unix/WSL; file nằm trên `/mnt/c|d` luôn là 777 nên
đặt trong `~`). Trình duyệt hỏi đăng nhập: tên `lab`, mật khẩu như đã đặt. Không có mật khẩu mặc định; mật khẩu không được ghi vào log.
Lưu ý: HTTP Basic qua HTTP thường không mã hóa, chỉ dùng trong mạng lab tin cậy.
- Giới hạn đoán mật khẩu: sai 5 lần/phút từ một IP thì IP đó bị chặn: mọi lần thử, KỂ CẢ đúng, nhận 429 (kèm `Retry-After`)
  tới hết thời gian chặn; mọi lần sai đều được đếm (kể cả khi đang bị chặn, nên dò tiếp thì chặn kéo dài). TỔNG 20 lần sai/phút từ mọi IP
  thì khóa toàn cục 60 s: yêu cầu chưa xác thực và máy lạ nhận 429 dù đúng hay sai; chỉ máy đã đăng nhập ĐÚNG trong 1 giờ qua (chủ máy) và
  không đang bị chặn theo IP vào được bằng mật khẩu đúng (cho mọi mật khẩu đúng qua thì 429 thành "máy dò" và giới hạn vô nghĩa).
  429 không kèm hộp đăng nhập: trình duyệt của chủ chỉ hỏi lại mật khẩu khi tải lại trang SAU khi hết chặn (đợi hết `Retry-After`, thường 60 s).
- Tiêu đề Host: chế độ mạng chỉ nhận Host thuộc danh sách (mặc định: địa chỉ `--host`, `localhost`, tên máy; thêm bằng
  `--allowed-host <tên>`, lặp được); Host lạ nhận 403. Dùng `--allow-network` mà không `--host` thì nghe MỌI giao diện và có cảnh báo:
  nên chỉ rõ địa chỉ mạng nội bộ. Với `--host 0.0.0.0` (hoặc không `--host`), truy cập bằng địa chỉ IP sẽ bị 403 trừ khi thêm `--allowed-host <IP>`
  (`0.0.0.0` không phải tên khách gõ); chương trình in cảnh báo này khi khởi động.

## Điểm cuối HTTP
| Method | Đường dẫn | Việc |
|---|---|---|
| GET | `/`, `/static/app.js`, `/static/app.css` | trang (file cố định nạp sẵn, không đọc file theo đường dẫn người dùng) |
| GET | `/stream.mjpg` | luồng MJPEG (tối đa 4 người xem; nguồn đứng thì gửi lại khung cuối mỗi 2 s để phát hiện người xem đã ngắt và trả chỗ; nguồn hết thì đóng luồng) |
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
- Gán lại khóa khi bộ theo dõi đổi ID (`lock.py`, bật mặc định, tắt bằng `--no-reacquire`): trong thời gian chờ, nếu có track MỚI
  (ID chưa có mặt ở khung cuối còn thấy mục tiêu) nằm gần vị trí dự đoán (tâm cuối + vận tốc ảnh ~0,5 s gần nhất, ngoại suy tối đa 1 s)
  và bề rộng tỉ lệ trong [`--reacq-size-min`=0,5; `--reacq-size-max`=2,0] so với khung cuối, conf >= `--reacq-min-conf` (mặc định = `--conf`),
  thì khóa chuyển sang track đó; nhiều ứng viên thì lấy cái gần nhất. Vị trí dự đoán bị kẹp trong khung hình; khung bao cuối sát mép ảnh
  (< 0,5 cạnh) mà đang đi ra ngoài thì coi là đã rời khung, không gán lại. Sau mỗi lần gán lại, vận tốc ước lượng lại từ track mới.
  Cổng khoảng cách = cạnh lớn khung bao cuối x (`--reacq-gate`=1,0 + `--reacq-gate-per-s`=1,5 x giây mất dấu).
  Không có ứng viên thì giữ hành vi cũ (hết hạn thì bỏ khóa). Trạng thái `lock.state` = `tracking` (bám) | `searching` (đang tìm lại) |
  `reacquired` (vừa gán lại, 2 s) và `lock.reacquired` (số lần gán lại từ lúc khóa) có trong `/api/state`, trên hình và trên trang.

## Chuyển sang Raspberry Pi 5 (chưa làm)
- Thêm `Picamera2Source(FrameSource)`: `Picamera2().create_video_configuration(main={"size":(1280,720),"format":"RGB888"})`, `capture_array()` trả khung (RGB888 của picamera2 thực chất là BGR cho OpenCV), `live=True`.
- `--hfov` cho Camera Module 3 Wide khoảng 102 độ (theo nhà sản xuất, CHƯA kiểm); góc rộng có méo ống kính, cần hiệu chỉnh nếu muốn góc chính xác.
- Suy luận trên Pi 5 cần NCNN/ONNX thay `.pt`; tốc độ khung hình chưa đo.

## Dùng lại từ `AI-6` (chỉ đọc ý tưởng/mẫu)
`YOLOv8/video_processor.py`: mô hình luồng camera/suy luận tách rời, `grab()+retrieve()` lấy khung mới nhất, mở V4L2 MJPG buffer 1; `frame_processor.py`: gọi `model.track(persist=True, bytetrack)`. `AI-6` không có mã picamera2 (chỉ comment V4L2). Không dùng `drone_tg\`.

## Công cụ kiểm chứng
`e2e_check.sh` (chạy thật bằng curl, tự tắt máy chủ), `fp_check.py` (đếm khung "drone" giả), `tools_to_png.py`, `bench_reacquire.py` (đo trước/sau gán lại khóa trên file video, không cần máy chủ; mỗi lần gán lại in cách vị trí dự đoán (theo cạnh khung bao), tỉ lệ cỡ, thời gian mất, và đếm lần "đáng ngờ": cách > 2 cạnh hoặc tỉ lệ cỡ ngoài 0,67-1,5).
Lưu ý: "tỉ lệ khung còn khóa" chỉ đo MẤT KHÓA ÍT HƠN (tăng cả khi gán nhầm), chưa đo BÁM ĐÚNG HƠN; không có nhãn thật, độ đúng chỉ kiểm bằng mắt trên vài video. Đo 14 video: cổng 1,5/2,0 gán lại 17 lần (2 đáng ngờ, còn khóa 84,4%); cổng 1,0/1,5 (mặc định) 16 lần (1 đáng ngờ, 78,7%); cổng 1,0/1,0 chỉ 4 lần (68,6%). Ảnh chụp: `docs/`.
