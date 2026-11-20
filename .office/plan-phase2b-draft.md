# Kế hoạch giai đoạn 2b: sửa các rủi ro đã biết của khối tìm lại (bản nháp, 2026-11-20) — CHƯA DUYỆT

Lập: 02 planner. Mẫu: `plan-phase2.md`. Quy tắc giữ nguyên: 07 viết test đỏ → 05 sửa → 08 rà; một SITL mỗi lúc; không sửa `onboard\dtrack` và `onboard\simtools` khi SITL chạy; mỗi đợt chỉ một bước chạm `config.py`.

## Mục tiêu
Trong mô phỏng: (A) bật tìm lại không làm chậm việc lấy lại hình ở ca bổ nhào; (B) tìm nguyên nhân gốc rồi sửa việc drone áp sát mục tiêu cuối bài khi mục tiêu dừng; (D) đủ ca leo cho C8. Việc (C), độ cao còn tăng +9,15 m sau khi đóng đợt, đang do 10 điều tra riêng; nếu ra lỗi mã thì chen vào cùng cổng với (B).

## Thiết kế (A): quét theo cửa sổ quanh góc dự đoán (đổi S-7, S-9)
Gốc: `search.py:131-143` quét cả `[scan_lo, scan_hi]` = 10–110° (`config.py:148-149`); `begin()` (`search.py:116`) chỉ nhận δ0, không nhận hướng nhìn nhớ.
- Chọn: cửa sổ `[c−w(t), c+w(t)]` giao `[lo, hi]`. `c(t)` = δ lúc mất hình + δ̇ nhớ × (t − t_mất), cắt ở ±`scan_rate`, ngoại suy tối đa 3 s. `w(t) = scan_window_deg + scan_widen_dps·t`, tới khi phủ cả dải thì thành hành vi cũ. Phản xạ ở biên như hiện nay; biên di động nên δ liên tục.
- Khóa mới trong `SearchConfig`: `scan_window_deg` (25; 0 = hành vi cũ), `scan_widen_dps` (đề xuất 10; chốt trong test). Ràng buộc chỉ áp khi `enabled=True`, cạnh `config.py:285-291`.
- Giao diện: `SearchPlanner.begin(...)` thêm đối số `ddelta0_rad_s` (mặc định 0); `supervisor.py` (chỗ gọi `begin`, quanh dòng 246-283) tính δ̇ từ góc khớp ~0,5 s trước. `step()`, `GimbalControl` (`gimbal_control.py:56-61`) và S-3 không đổi. Pha 2 dùng `max(lo2, c−w)`.
- Quy tắc mới ghi thành S-16 trong `design-search.md`.
- Đã loại: (1) nâng `scan_lo_deg` lên ~55°: chỉ đổi 8% thành khoảng 24% thời gian thấy mục tiêu, mù với mục tiêu ngoài dải cứng; (2) dừng lâu ở đầu thấp: kéo dài chu kỳ, thêm tham số thời gian, làm chậm ca bay thẳng; (3) giữ nguyên, chấp nhận ~3 s.
- Rủi ro (A): cửa sổ đặt sai chỗ khi mục tiêu đổi hướng lúc mất hình; giảm bằng nới cửa sổ, và giữ test mục tiêu dời chỗ (`test_search_scan_real_tracker.py:126`).

## Tiêu chí nghiệm thu
| # | Tiêu chí | Cách kiểm |
|---|---|---|
| D1 | Ca bổ nhào (−42…−34°, 48–77 m, drone treo): độ trễ từ hết mất hình tới TRACK, quét đều một chu kỳ pha, ≤ 1,0 s ở mọi pha (hiện 0–3,3 s) | Test mới ở bước 1, đỏ → xanh |
| D2 | SITL bổ nhào, mất 8 s, bật × 5 seed: trễ trung bình ≤ tắt + 1,0 s và từng seed ≤ tắt + 1,5 s (trước: ≈ +3 s). Quét độ dài mất hình 7,0–9,5 s bước 0,5 (6 lần, 1 seed) đều ≤ tắt + 1,5 s | `analyze_closed_loop.py`, cùng lệnh trước/sau; tắt × 3 (mất 7, 8, 9 s) |
| D3 | Không hồi quy tìm lại: bay thẳng mất 8 s bật × 5 seed, tìm lại 5/5, thời gian không chậm hơn bảng `srchG3` quá 0,5 s; ca mục tiêu dời chỗ vẫn xanh; cửa sổ phủ cả dải trong ≤ 8 s (test đơn vị) | Test + SITL |
| D4 | (B) ĐỀ XUẤT, chủ dự án chọn (câu hỏi 1): mặc định (a) khoảng cách nhỏ nhất cả chuyến ≥ 6 m ở 13/13 lần bay thẳng có mục tiêu dừng cuối bài (hiện 8 lần dưới 8 m, 5 lần dưới 6 m) | SITL cùng 13 ô, công cụ giữ sàn 6 m |
| D5 | C8: leo 10 m × 3 seed: độ cao tăng ≤ 11 m tới lúc tìm lại, khoảng cách ≥ 8 m; leo 20 m × 1 seed: ≤ 21 m, ≥ 8 m. Báo thêm độ cao tăng sau khi đóng đợt; nếu (C) là lỗi mã thì thêm ngưỡng sau-khi-đóng | SITL `search_plane_r15_climb10` / `_climb20`, mất 14 s |
| D6 | Hồi quy: pytest `onboard` ≥ 1368 + test mới passed, 0 failed, 1 xfailed; RTL mất 25 s: 20,0 ± 0,5 s; 3 ô bám C9 × 3 seed giữ mức đã đạt | Cùng lệnh pytest trước/sau; SITL |
| D7 | Tài liệu khớp số đo; README mục rủi ro cập nhật đúng trạng thái | 08 đối chiếu từng con số với csv |

## Các bước
| ID | Làm gì | Vai | Chạm | Kiểm chứng | Đợt |
|---|---|---|---|---|---|
| 1 | Test đỏ cho (A): hình học bổ nhào, quét đều pha, độ trễ tới TRACK; test cửa sổ (tâm, nới, phủ cả dải, S-3); test khóa cấu hình. Nộp bằng chứng đỏ đúng lý do | 07 | `tests\test_search_scan_dive_window.py` (mới), `tests\test_search_config.py` | pytest đỏ do thiếu cửa sổ | 1 |
| 2 | Điều tra nguyên nhân gốc (B): vì sao có đợt COAST thứ hai 4,6–5 s sau lệnh dừng, vì sao drone bay tới sát trên mục tiêu; đọc log 13 lần `srchG3`/`srchG4`, chạy lại `dtrack` trên đầu vào log. Cần số đo mới thì ghi ô SITL đề nghị (không tự chạy) | 10 | chỉ đọc `simtools\out\`, `dtrack\` | Báo cáo kèm tái hiện | 1 (song song bước 1) |
| 3 | Sửa (A): cửa sổ quét, truyền δ̇, khóa, hồ sơ `search_plane_r15*` | 05 | `dtrack\search.py`, `config.py`, `supervisor.py`, `simtools\configs\search_plane_r15*.json` | Bước 1 xanh; pytest D6 | 2 |
| 4 | CỔNG B: trưởng phòng đọc bước 2; lỗi gọn thì giao bước 5; đòi đổi hành vi bám lớn thì dừng trình chủ dự án (câu hỏi 2) | 01 | — | — | 2 |
| 5 | Test đỏ cho (B) theo nguyên nhân gốc; nộp bằng chứng đỏ | 07 | `tests\test_end_of_leg_*.py` (mới) | Đỏ đúng lý do | 2 (song song bước 3, khác file) |
| 6 | Rà (A): đọc diff, tự chạy pytest, đối chiếu S-16 | 08 | chỉ đọc | Vòng sửa theo quy trình | 3 |
| 7 | SITL (A), lô `srchH1`, 13 lần: bổ nhào bật × 5 (mất 8 s) + quét 7,0–9,5 s × 6 (một trùng) + tắt × 3 | 07 | `simtools\out\` | D2 | 4 |
| 8 | Đối chiếu bước 7, tự tính lại từ csv. CỔNG A: D2 không đạt thì dừng, sửa vòng ngắn | 08 | chỉ đọc | Bảng số | 5 |
| 9 | Sửa (B) | 05 | file do bước 2 chỉ ra (dự kiến `guidance.py` và/hoặc `supervisor.py`) | Bước 5 xanh; pytest | 5 |
| 10 | Rà (B) | 08 | chỉ đọc | Tự chạy pytest | 6 |
| 11 | SITL cuối, lô `srchH2`, khoảng 40 lần: 13 ô bay thẳng dừng cuối bài (D4); C8 leo 10 m × 3 + 20 m × 1 (D5); bổ nhào bật × 5 chạy lại nếu bước 9 đổi guidance (D2); bay thẳng × 5 (D3); RTL 25 s × 1; C9 3 ô × 3 (D6) | 07 | `simtools\out\` | D3–D6 | 7 |
| 12 | Đối chiếu bước 11 với D1–D6, tự tính lại | 08 | chỉ đọc | Bảng số | 8 |
| 13 | Cập nhật tài liệu, thêm S-16 (A), S-17 (B) vào thiết kế | 05 | `README.md`, `HANDOFF.md`, `onboard\README.md`, `.office\design-search.md` | Bước 14 | 9 |
| 14 | Rà cuối: số trong tài liệu so với csv, đối chiếu D1–D7 | 08 | chỉ đọc | Báo cáo cuối | 10 |

## Thứ tự và cổng
1 ∥ 2 → 3 ∥ 5 (sau cổng 4) → 6 → 7 → 8 (cổng A) → 9 → 10 → 11 → 12 → 13 → 14. Bước 9 không bắt đầu nếu bước 2 chưa có nguyên nhân gốc. Sửa (B) đòi đổi hành vi bám hoặc bật lại cơ chế hãm thì dừng trình. (C) có lỗi mã thì thêm một vòng 07 → 05 → 08 ngay trước bước 11.

## Ước lượng
- Lượt gọi vai: 14 bước + 6–10 lượt vòng sửa + 1–2 lượt (C) = 21–26 lượt. Vượt khoảng 36 thì dừng báo.
- SITL: 13 + 40 = 53 lần × 2,5–4,5 phút ≈ 2,2–4 giờ máy, chạy nền theo lô; trong lúc đó không game, không huấn luyện.

## Rủi ro chính
- Nguyên nhân (B) có thể nằm ở bộ bám hoặc khớp gimbal (mất hình lần hai khi mục tiêu dừng), không gọn một chỗ: cổng bước 4.
- Sửa (B) có thể làm lệch việc bám của giai đoạn 1: bước 11 chạy lại C9 và bổ nhào.
- Ngưỡng D1/D2 (1,0 / 1,5 s) và `scan_widen_dps` là tự đặt, chưa đo.
- C8 vẫn chỉ 3 + 1 ca: không tuyên bố thống kê.
- Mô phỏng không có nền thật; kết quả chỉ chứng minh logic.

## Việc khó hoàn tác
Không có trong 14 bước. Commit và push do trưởng phòng làm sau khi chủ dự án chấp nhận kết quả (commit bằng Git Bash, push bằng git của WSL; kiểm `git add -A -n` trước). `out\` không lên git.

## Không đụng
`vision\`, `pi\`, `lab\`, `gcs\`, `cad\`; việc trên Pi; mặc định camera; cơ chế "giả định mục tiêu hãm" (`blind_floor_m` giữ 0); `search.enabled` mặc định vẫn TẮT; phần nhận diện.

## Câu hỏi cho chủ dự án
1. Mức đạt (B): (a) khoảng cách nhỏ nhất cả chuyến ≥ 6 m ở 13/13 lần (khuyến nghị); (b) như (a) cộng góc nâng lúc gần nhất ≤ 60°; (c) chỉ đo.
2. Nếu nguyên nhân (B) buộc đổi hành vi bám giai đoạn 1 (ví dụ chậm lại khi mục tiêu dừng), có cho đổi không, hay chỉ ghi rủi ro?
3. Chấp nhận máy bận 2–4 giờ SITL (không game, không huấn luyện) cho hai lô?
