# Drone-Tracking: bản bàn giao (cập nhật 2026-11-17, cuối phiên 2)

Phiên mới: đọc file này, rồi phần cuối `.office\ledger.md`, rồi các file trong
`.office\progress\`. Ba nguồn đó đủ để làm tiếp, không cần bản ghi trò chuyện cũ.

> **TRẠNG THÁI: ĐANG DỪNG theo yêu cầu người dùng (2026-11-17).** Không còn
> agent, tiến trình SITL hay lịch tự đánh thức nào chạy. Chỉ làm tiếp khi người
> dùng bảo làm tiếp; khi đó bắt đầu từ mục "Việc đầu tiên của phiên mới".

## 1. Mục tiêu và yêu cầu của người dùng

Drone quad 8 inch tự bay hành trình hoặc bay bám một drone khác (tốc độ tương
đương hoặc hơn), giữ khoảng cách an toàn. Mô phỏng trước, phần cứng sau. Mẫu
tham khảo: YouTube `k9n1h0rn9No` (quad Blackbird).

- Tốc độ thiết kế: **max 350 km/h, cruise 200–250 km/h**; 400 km/h là phấn đấu.
- Firmware: **ArduPilot (ArduCopter)** trên Matek H743-WING V3. Không dùng PX4.
- TX/RX (Radiomaster Pocket + XR4, **đã có sẵn**) chỉ dùng thử trong lab. Bay
  thật điều khiển qua trạm GCS.
- GCS: **Mission Planner** trên một thiết bị mang đi được, Windows 11, cảm ứng,
  10 hoặc 13 inch, **ngân sách 10–15 triệu đồng**. Cài một lần là dùng được.
  **Không cài gì lên máy này** (máy cá nhân). Ngoài sân GCS chủ yếu để bấm điểm.
- Phần mềm bám **viết từ đầu bằng subagent**, tham khảo trên mạng.
- Excel linh kiện cho cả lab và ra sân; **ưu tiên giá Taobao**.
- Taobao qua Claude in Chrome: **chỉ đọc**. Không thêm giỏ, không thanh toán,
  không đặt hàng, không nhắn người bán, không hỏi hay nhập mật khẩu.

## 2. Cách làm việc (yêu cầu của người dùng)

- Mô hình văn phòng theo `C:\Users\dctie\.claude\CLAUDE.md`: phiên chính là Lead,
  người làm không tự kiểm, sổ ghi chỉ ghi thêm, trả lời bằng tiếng Việt.
- Lead chia việc cho **nhiều agent chạy song song** theo luồng, miễn là các luồng
  không đụng file và tài nguyên của nhau (bảng ở mục 4).
- **Đổi ngày 2026-11-17 theo yêu cầu người dùng:** cơ chế riêng của dự án cho
  hạn mức 5 tiếng đã BỎ. `autoContinueAtUsageLimit` đã gỡ khỏi
  `d:\Personal\.claude\settings.local.json`, không đặt lại lịch CronCreate, và
  không ghi thêm file tiến trình `.office\progress\` nữa. Từ nay dùng cơ chế
  chung trong `C:\Users\dctie\.claude\CLAUDE.md`: tổng kết ở 85% và 95% (mod
  `usage-wrapup`), ghi `.office\checkpoint.md`, tự chạy tiếp khi nhận
  `[usage-resume]`.
- Các file cũ trong `.office\progress\` giữ lại làm hồ sơ: đọc để biết task
  dừng ở đâu, không ghi thêm vào đó.
- Trước khi làm tiếp phải lập lại kế hoạch tổng và trình người dùng duyệt (mục
  "Duyệt kế hoạch trước khi làm" trong `CLAUDE.md`). Lần chạy trước người dùng
  dừng vì đầu việc chạy loạn, không kiểm soát được.
- Agent của phiên cũ không gọi lại được từ phiên mới. Mở agent mới cùng vai, bảo
  nó đọc file tiến trình cũ của task rồi làm tiếp.
- Mỗi task kết thúc, báo người dùng ba phần: **Đã làm được gì · Chưa làm được gì
  · Cần làm gì tiếp**, kèm DONE hoặc FAILED. Bản giao việc cho agent cũng yêu cầu
  báo cáo cuối theo ba phần này.

## 3. Quyết định kỹ thuật đã có

| Hạng mục | Quyết định |
|---|---|
| FC | Matek H743-WING V3 + ArduCopter (FC chịu tối đa 36 V, cảm biến dòng khoảng 132 A) |
| Máy tính | Raspberry Pi 5 + AI HAT+ 26 TOPS (Hailo-8), boot thẻ microSD |
| Camera | Raspberry Pi Global Shutter (IMX296, 1456×1088, ngàm CS), lens 6 và 8 mm |
| Radio | Pocket + XR4 cho lab (đã có) |
| Khung | Apex HD 8 inch 362 mm làm đế, bọc vỏ in 3D kiểu tên lửa |
| Mô phỏng | ArduPilot SITL Copter-4.7.2 trong WSL2 `Ubuntu-24.04` |
| GCS | Mission Planner; ứng viên máy ở mục 4, luồng D |

Ràng buộc và phát hiện cần nhớ (số lực cản và công suất là **tính tay, chưa kiểm
bằng mô phỏng**):

- Apex trần khoảng 0.03 m² diện tích cản, tối đa khoảng 180–220 km/h. Có vỏ, ốp
  tay, chóp motor: khoảng 0.006–0.010 m², 350 km/h cần khoảng 6–9 kW điện.
- Motor 3110 (khoảng 0.9 kW mỗi cái) **không đủ**. Ứng viên: 3115, 3120, 3220,
  kèm ESC đơn 200 A. Chốt sau chặng 3.
- Mục tiêu bám được thực tế tối đa khoảng 270–290 km/h.
- Camera đơn không đo được khoảng cách: ước lượng từ kích thước khung bao.
- Mục tiêu 0.3 m ở 50 m chỉ chiếm 10–15 px: cắt vùng 640×640 ở độ phân giải gốc.
- ArduCopter giới hạn góc nghiêng 80°; 350–400 km/h cần khoảng 65–75°.
- Camera ở mũi, cất hạ cánh đứng trên đuôi: bay chậm thì camera nhìn lên trời.
- **Mô phỏng vòng kín xác nhận:** khi tăng hoặc giảm tốc, drone bám nghiêng
  20–45° và mục tiêu ra khỏi trường nhìn dọc của camera cố định.

Kiến trúc phần mềm bám: 8 module Python (capture, detect, tracker, range,
mavlink_io, guidance, supervisor, logger). Lệnh vận tốc NED ở chế độ GUIDED,
10–20 Hz, qua pymavlink. Hợp đồng dữ liệu chung: `onboard\dtrack\types.py`
(thế giới NED, thân FRD, camera x phải / y xuống / z trục quang; cờ `range_valid`).

## 4. Trạng thái từng luồng

| Luồng | Tài nguyên riêng | Việc kế theo thứ tự |
|---|---|---|
| A. Phần mềm bám | `onboard\`, SITL instance 0–1 | T9a → T9d → rà soát |
| B. Mô phỏng chặng 1 | `sim\`, SITL (chờ A nhả, vì T9a đọc `sim\`) | T2b → rà soát |
| C. Bộ cài GCS | `gcs\` | chờ máy GCS để cài thật |
| D. Giá Taobao + Excel | `bom\`, trình duyệt (phiên chính) | tra giá → thêm cột CNY |

### Luồng A: phần mềm bám (`onboard\`)

**Khối nhận biết (T9b, T9c): xong, còn lỗi chờ sửa.** File
`dtrack\{types,geometry,tracker,range_estimator,synthetic}.py`. Phiên chính tự
chạy: 71 test qua (trước khi có khối điều khiển). Rà soát T9c-V để lại T9d,
**chưa bắt đầu**:

- (a) CHẶN: detector co khung bao vào trong mép ảnh 3–8 px mà `range_valid` vẫn
  True, báo xa hơn thật 7–12 m (`range_estimator.py:109-111`, `edge_margin_px`).
- (b) CHẶN: mất mục tiêu rồi quay lại gần hơn thì vài mẫu báo xa hơn thật hơn
  100 m (`range_estimator.py:160`).
- (c) `_pending` bị xóa khi `update` gọi nhanh hơn detector, mất khoảng 3 s
  (`tracker.py:275-276`).
- (d) Ghi vào `types.py` rằng điều kiện σ/r dùng sigma của bộ lọc; sigma công bố
  không tăng khi mất đo.
- (e) Test yếu: biến thể rel=0.25 không phân biệt được hành vi cũ; biến thể
  rel=0.0 chập chờn (6/10 nhóm seed hỏng ở 60 m/s).

**Khối điều khiển (T9a): DỞ DANG, chưa đạt, chưa rà soát.** Agent dừng vì hết hạn
mức lúc đang viết README và requirements; chưa có báo cáo cuối. Đã có
`dtrack\{config,guidance,supervisor,mavlink_io,logger,app}.py`,
`simtools\{sim_truth_source,sim_helper,analyze_closed_loop}.py`,
`simtools\run_closed_loop.sh`, `tests\{test_guidance,test_supervisor}.py`. Agent
ghi 174 test qua; **phiên chính chưa tự chạy lại**. Kết quả vòng kín SITL (phiên
chính đọc `simtools\out\*\result.txt`; nghiệm thu: sai số trung bình dưới 3 m,
không bao giờ dưới 8 m):

| Kịch bản | Kết quả |
|---|---|
| 10 m/s, seed 1 | không có `result.txt` |
| 10 m/s, seed 2 | sai số TB 0.94 m, TRACK 100%, min 7.15 m: FAIL |
| 10 m/s, seed 3 | sai số TB 14.95 m, TRACK 82.4%: FAIL |
| 20 m/s | TRACK 1.9%, min 4.38 m: FAIL |
| Mất hình 3 s | min 5.21 m, TB 8.18 m: FAIL |
| Phi công giành quyền | ngừng gửi lệnh sau 0.021 s: PASS |

`progress\T9a.md` mới ghi tới "bước 5", thiếu các lần chạy sau. Việc kế: xử lý
gốc vấn đề trường nhìn (cần quyết định camera ở mục 5) trước khi chỉnh tiếp bộ
điều khiển; rồi T9d; rồi `checker` rà cả T9a và T9d một lượt.

### Luồng B: mô phỏng chặng 1 (`sim\`)

File: `run_sitl.sh, run_chase.sh, chase.parm, target.py, chaser.py, chaselib.py,
analyze.py, README.md`. Bám 15 m bằng vị trí chuẩn của mục tiêu. Trong cửa sổ đo
120 s: 10 m/s sai số TB 0.18 m, min 14.16 m, PASS; 20 m/s 0.56 m, 13.09 m, PASS;
phiên chính chạy lại 10 m/s: 0.32 m, 13.89 m, PASS.

Rà soát T2-V để lại T2b, **chưa bắt đầu**:

- CHẶN C1: hết cửa sổ đo, chaser ngừng gửi lệnh mà không phanh
  (`chaser.py:125-133`), target phanh về 0 (`target.py:49,66`), FC giữ lệnh cũ
  3 s. Khoảng cách thật tụt còn 0.76 / 0.14 / 6.61 m (đọc từ log BIN). CSV không
  ghi đoạn này nên báo cáo "min toàn chuyến bay ≥ 8 m" là sai.
- Chaser không kiểm tuổi dữ liệu target, không kiểm mode và arm.
- `analyze.py` thiếu kiểm khoảng trống dữ liệu, bỏ qua mã thoát của chaser.
- `run_chase.sh:27,32` dùng `pkill -x arducopter` bừa.
- README ghi sai SPEEDUP.

Sửa xong thì chạy lại 10 và 20 m/s, chấm toàn chuyến bay, đối chiếu vị trí thật
trong BIN.

### Luồng C: bộ cài GCS (`gcs\`)

File: `manifest.json, Get-GcsPackages.ps1, Install-Gcs.ps1, Test-Gcs.ps1,
Uninstall-Gcs.ps1, GcsLogic.ps1, tests\Test-GcsLogic.ps1, README.md,
config\dtrack-failsafe.param, config\checklist-truoc-bay.md`. Cài vào `C:\GCS`.

Qua bốn lượt sửa và rà soát (T10 → T10d). Lượt cuối, `security-auditor` kết luận
**đủ an toàn để chép sang máy GCS và thử cài**. Phiên chính tự kiểm: ParseFile
mọi script 0 lỗi; `Test-GcsLogic.ps1` PASS=171 FAIL=0; `C:\GCS` không tồn tại
trên máy này.

Còn lại:

- **Chưa chạy thật lần nào** (cần máy đích, quyền admin). Chữ ký số thật của các
  gói chưa xem; `expectedPublisher` trong `manifest.json` còn rỗng.
- Hai mục mức thấp: máy dùng chính sách chủ sở hữu "Object creator" thì lần chạy
  thứ hai có thể dừng; script duyệt cả cây trước khi quyết định dừng (chỉ chậm).

### Luồng D: Excel và giá Taobao (`bom\`)

`Drone-Tracking-BOM.xlsx` sinh từ `bom_data.json` bằng `build_bom.py`. Sheet:
Tổng quan, A - Lab, B - Ra sân, Động lực (chờ chốt), GCS, Rủi ro. Giá phần lớn
là USD từ shop nước ngoài, tỷ giá giả định 26 000 đồng/USD.

Giá Taobao đã có:

- **Dell Latitude 7220 Rugged cũ** (shop 麦可本本, item 661045301318), i5-8365U:
  8G/256G ¥2136.8; 16G/512G ¥2631.8; trang ghi gửi thẳng Việt Nam. Đã vào Excel.
- Chỉ là giá "từ" của tin gộp nhiều cấu hình, **chưa vào Excel**: Surface Pro cũ
  ¥1058–1582, Pro 7+ i5 8G/128G ¥2858; Pi 5 ¥450–640, bộ 8G ¥1420–1506. Trang
  Pi 5 của Yahboom (item 752562699439) đã mở, chưa đọc được giá bản 8GB.

Ứng viên máy GCS trong sheet GCS: Dell 7220 cũ, Surface Pro 7 cũ, Chuwi Hi10 Max,
Surface Go 3, Xiaomi Pad 7 (Android, để so sánh).

Vướng: tiện ích Claude in Chrome bắt người dùng bấm Allow cho **từng thao tác**
trên Taobao, không có mục "luôn cho phép", không gộp batch được. Tra giá chỉ làm
khi người dùng ngồi máy, hoặc người dùng gửi link sản phẩm. Trình duyệt hiện đã
ngắt kết nối. Việc kế: các máy GCS còn lại → linh kiện "Mua ngay" → ứng viên
động lực; thêm cột giá CNY vào `build_bom.py`.

## 5. Quyết định còn chờ người dùng

1. **Camera:** camera cố định, trường nhìn hẹp không giữ được mục tiêu khi drone
   cơ động. Ba hướng: lens góc rộng hơn (mục tiêu nhỏ đi trong ảnh); gimbal một
   trục bù góc nghiêng (thêm khối lượng và độ phức tạp ở mũi); giới hạn gia tốc
   drone bám (bám kém khi mục tiêu đổi hướng). Lead nghiêng về gimbal một trục.
2. **Máy GCS** mua loại nào.
3. Có bật lại chế độ tự làm tiếp sau giờ nghỉ không.
4. Bản trình duyệt cuối (diff tổng hợp, test, rà soát) theo CLAUDE.md **chưa làm**.

## 6. Môi trường và lệnh

- WSL: luôn `wsl -d Ubuntu-24.04` (distro mặc định của máy là BambuStudio). User
  `drone`, sudo không mật khẩu. Venv `~/venv-ardupilot` tự nạp khi dùng
  `bash -lc`: pymavlink 2.4.50, MAVProxy 1.8.75, numpy, pytest, openpyxl.
- Binary SITL: `~/ardupilot/build/sitl/bin/arducopter`.
- Gọi WSL từ PowerShell 5.1: dấu `"` lồng và dấu `\` bị mất. Viết lệnh dài vào
  file `.sh` hoặc `.py` rồi chạy file đó; bỏ CRLF bằng `tr -d '\r'`.
- Tên tham số 4.7.2 đã kiểm: `MAV_SYSID`, `ATC_ANGLE_MAX`, `WP_SPD`, `WP_ACC`,
  `GUID_TIMEOUT` (3 s), `RTL_ALT_M`, `FENCE_TYPE` (bitmask: 1 trần cao, 2 tròn,
  4 đa giác, 8 sàn thấp), `ARMING_SKIPCHK`. Cổng SITL: SERIAL0 = 5760 + 10·I,
  SERIAL1 = 5762 + 10·I. Bay 20 m/s cần model `X:@ROMFS/models/freestyle.json`.
  type_mask lệnh vận tốc GUIDED: 3527 (chỉ vận tốc), 2503 (vận tốc + yaw).
- Dựng lại Excel:
  `wsl -d Ubuntu-24.04 -- bash -lc 'cd /mnt/d/Personal/Drone-Tracking/bom; ~/venv-ardupilot/bin/python build_bom.py'`
- Test logic bộ cài GCS: `powershell -File gcs\tests\Test-GcsLogic.ps1`
- Test phần mềm bám (lệnh suy ra, chưa chạy đúng dạng này):
  `wsl -d Ubuntu-24.04 -- bash -lc 'cd /mnt/d/Personal/Drone-Tracking/onboard; python -m pytest -q'`
- Vòng kín: `onboard\simtools\run_closed_loop.sh`; chặng 1: `sim\run_chase.sh`
  (cách dùng trong `sim\README.md` và `progress\T9a.md`).
- Kiểm không còn SITL chạy: `wsl -d Ubuntu-24.04 -- pgrep arducopter`.

## 7. Việc đầu tiên của phiên mới

1. Đọc phần cuối `.office\ledger.md` và `.office\progress\T9a.md`.
2. Hỏi người dùng hai quyết định chặn luồng A: hướng camera, và có bật lại tự
   chạy tiếp không. Các luồng không phụ thuộc thì giao song song ngay.
3. Luồng A: tự chạy lại `pytest` trong `onboard\` để có số của phiên chính. Mở
   `backend-engineer` mới, cho đọc `progress\T9a.md` và bảng kết quả ở mục 4,
   hoàn tất T9a theo hướng camera đã chốt. Rồi T9d, rồi `checker`.
4. Luồng B: sau khi A nhả SITL, giao T2b cho `backend-engineer`, rồi `checker`.
5. Luồng D: tra Taobao khi người dùng có mặt.
6. Cuối cùng: bản trình duyệt tổng hợp theo CLAUDE.md.

## 8. Lộ trình sau đó

- Chặng 2: camera mô phỏng (Gazebo), YOLO, ước lượng khoảng cách từ ảnh.
- Chặng 3: mô hình lực cản thân tên lửa, nâng dần lên 250–350 km/h, chốt motor,
  ESC, pin, prop.
- Module camera + Hailo trên phần cứng thật.

Repo tham khảo: `D:\Personal\DHTT-UAV-Testing-CLEAN` (bản sao một phần; phần dẫn
đường viết cho PX4 ở 6.5 m/s nên không dùng lại; model `best.pt` dùng lại được).
