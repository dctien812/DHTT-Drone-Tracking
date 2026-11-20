# Kế hoạch giai đoạn 2b (2026-11-20) — ĐÃ DUYỆT (người dùng, 2026-11-20)

Lập: 02 planner (bản nháp `plan-phase2b-draft.md`). Phản biện: 08 checker. Trưởng phòng đã thu gọn theo phản biện. Quy tắc giữ nguyên: 07 viết test đỏ → 05 sửa → 08 rà; một SITL mỗi lúc; không sửa `onboard\dtrack`, `onboard\simtools` khi SITL chạy.

## Mục tiêu
Trong mô phỏng: (A) bật tìm lại không làm chậm việc lấy lại hình ở ca mục tiêu bổ nhào; (B) tìm ra nguyên nhân gốc của việc drone áp sát mục tiêu cuối bài (CHỈ ĐIỀU TRA, chưa sửa); (T) sửa các số sai trong tài liệu đã công khai.

## Thay đổi so với bản nháp (theo phản biện của 08)
- Thiết kế (A) đổi: không tính tâm quét theo góc khớp gimbal lúc mất hình (sai mốc 4 s và lệch khi thân drone đổi tư thế lúc phanh về treo). Thay bằng "giữ rồi mới quét": ở pha 1, gimbal tiếp tục ngắm hướng dự đoán của mục tiêu theo hệ thế giới (`Guidance.predicted_rel` hoặc `last_aim`, đổi sang góc khớp mỗi tick bằng `elev_to_delta`), đúng như cơ chế đang chạy khi tắt tìm lại; khi bộ nhớ dự đoán hết hạn (8 s) mới quét cả dải như hiện nay. Không thêm tham số nới cửa sổ.
- Cắt: sửa (B), chạy bù C8, trần chênh cao khi bám xa, các lô SITL lớn. Để sau khi thử lab, vì khối tìm lại mặc định tắt và tốc độ servo thật sẽ khác mô hình.
- SITL giảm từ 53 xuống khoảng 19 lần.

## Tiêu chí nghiệm thu
| # | Tiêu chí | Cách kiểm |
|---|---|---|
| E1 | Test đơn vị ca bổ nhào (drone treo, mục tiêu ở góc ngẩng −42…−34°, cự ly 48–77 m; mục tiêu "thấy được" tính từ hình học camera thật của hồ sơ, không dùng ngưỡng tự chọn): độ trễ từ lúc hình trở lại tới TRACK ≤ 1,0 s với mọi thời điểm hết mất hình trong 8 s đầu của pha 1 | Test mới: đỏ trước, xanh sau |
| E2 | SITL bổ nhào 25°, mất hình 8 s: bật × 5 seed và tắt × 5 CÙNG seed; trễ trung bình bật ≤ tắt + 1,0 s (trước: ≈ +3 s). Thêm mất hình 7 s và 9 s, mỗi độ dài bật × 1 + tắt × 1 cùng seed | `analyze_closed_loop.py`, cùng lệnh cho hai bên |
| E3 | Không hồi quy: bay thẳng mất 8 s bật × 3 seed tìm lại 3/3; mất hình 25 s → RTL ở 20,0 ± 0,5 s; mất hình 14 s vẫn tìm lại (quét cả dải sau khi hết bộ nhớ); test mục tiêu dời chỗ vẫn xanh | SITL 5 lần + pytest |
| E4 | pytest `onboard`: số passed ≥ số nền đo lại ở bước 0 + test mới; 0 failed; 1 xfailed | Cùng lệnh trước/sau |
| E5 | (B): báo cáo nguyên nhân gốc có tái hiện bằng dữ liệu đã có, giả thuyết đã loại, hướng sửa và ước lượng tác động tới việc bám giai đoạn 1 | 08 đọc lại |
| E6 | Tài liệu: số "+9,15 m" được sửa (đỉnh thật +20,47 m ở giây 25,4; đúng thiết kế do giữ góc −12° ở xa; C8 chỉ đo tới lúc tìm lại); mục rủi ro cập nhật theo kết quả (A), (B) | 08 đối chiếu từng số |

## Các bước
| ID | Làm gì | Vai | Chạm | Kiểm chứng | Song song |
|---|---|---|---|---|---|
| 0 | Đo nền: pytest `onboard` trước khi sửa | 07 (gộp vào bước 1) | — | Số passed | — |
| 1 | Test đỏ cho (A) theo E1; test "hết bộ nhớ thì quét cả dải"; test S-3 (tạm ngừng rồi tiếp tục) không đổi. Nộp bằng chứng đỏ đúng lý do | 07 | `onboard\tests\test_search_hold_then_sweep.py` (mới) | pytest đỏ | với 2, 3 |
| 2 | Điều tra (B): vì sao có đợt mất hình thứ hai 4,6–5 s sau lệnh dừng mục tiêu và vì sao drone trượt tới sát trên mục tiêu; kiểm cả khả năng bộ bám rớt TRACK do mục tiêu hết chuyển động. Dùng log 13 lần `srchG3`/`srchG4` | 10 | chỉ đọc `onboard\simtools\out\`, `onboard\dtrack\` | E5 | với 1, 3 |
| 3 | Sửa số sai trong tài liệu (T) | 05 | `README.md`, `HANDOFF.md`, `onboard\README.md`, `.office\checkpoint.md` | grep "+9,15" = 0 | với 1, 2 |
| 4 | Sửa (A): pha 1 giữ ngắm hướng dự đoán tới khi hết bộ nhớ rồi quét | 05 | `onboard\dtrack\search.py`, `supervisor.py`, `gimbal_control.py` (nếu cần); không đổi `config.py` trừ khi bắt buộc | Bước 1 xanh; E4 | sau 1 |
| 5 | Rà (A) và (T): đọc diff, tự chạy pytest | 08 | chỉ đọc | Vòng sửa theo quy trình | sau 4 |
| 6 | SITL lô `srchH1`, khoảng 19 lần (E2: 14 lần; E3: 5 lần) | 07 | `onboard\simtools\out\` | E2, E3 | sau 5 |
| 7 | Đối chiếu bước 6, tự tính lại từ csv | 08 | chỉ đọc | Bảng số | sau 6 |
| 8 | Cập nhật tài liệu theo kết quả (A), (B); thêm quy tắc S-16 vào thiết kế | 05 | ba file tài liệu, `.office\design-search.md` | Bước 9 | sau 7 |
| 9 | Rà cuối, bảng E1–E6 | 08 | chỉ đọc | Báo cáo cuối | sau 8 |

## Ước lượng
Khoảng 10–14 lượt gọi vai. SITL khoảng 19 lần × 2,5–4,5 phút ≈ 50–85 phút máy (trong lúc đó không game, không huấn luyện). Tổng khoảng nửa ngày.

## Rủi ro
- Mô hình dự đoán "mục tiêu giữ vận tốc nhớ" chưa được kiểm ở ca bổ nhào; phương án lùi: giữ nguyên hướng ngắm cuối (`last_aim`), đã có bằng chứng từ ca tắt tìm lại (8,0 s).
- E2 đạt không chứng minh việc quét có ích: tới nay chưa ca nào cho thấy bật tốt hơn tắt (mục tiêu luôn tự hiện lại). Ca chứng minh (mục tiêu hiện lại ở chỗ khác dự đoán) để giai đoạn sau.
- Tốc độ servo thật khác mô hình: thông số quét sẽ phải xem lại khi có phần cứng.

## Việc khó hoàn tác
Không có. Commit và push do trưởng phòng làm sau khi chủ dự án chấp nhận kết quả.

## Không đụng
`vision\`, `pi\`, `lab\`, `gcs\`, `cad\`; phần nhận diện; cơ chế "giả định mục tiêu hãm" (giữ tắt); `search.enabled` mặc định vẫn TẮT; `guidance.py` (không sửa trong kế hoạch này).

## Để sau (ngoài kế hoạch)
Sửa (B); chạy bù C8 (leo 10 m thêm 2 seed, 20 m 1 seed); trần chênh cao khi bám ở xa; ca chứng minh quét có ích.
