# Checkpoint: cuối phiên 5 (2026-11-18, khoảng 22:15; TẠM DỪNG theo yêu cầu người dùng, mai làm tiếp)

Tên dự án: Drone Tracking (tên "Drone Interceptor" đã bỏ trong ngày). Giờ hạn mức đặt lại: không ghi nhận.
Phiên sau đọc: file này, rồi phần cuối `.office\ledger.md` từ mục "PHIÊN 5 bắt đầu". Thiết kế bước 3–6 và mọi quyết định bổ sung: `.office\design-gimbal-steps-3-6.md`.

## Quyết định của người dùng hôm nay (thay ý cũ trái với nó)
- Khoảng cách giữ chuẩn 15 m (hồ sơ `accept_plane_r15`: giữ 15, lùi 10, lùi khẩn 8 m; chấm: sàn 6 m, cận pha cắm và giảm tốc cuối 6 m). Phạm vi không đổi: chỉ bám và giữ khoảng cách an toàn.
- Dải khớp gật camera 10°–110° so với trục lực đẩy (thay 10–90°); góc lúc cất cánh vẫn 90°.
- Làm toàn bộ bước 3–7 ở phiên này (không để phiên khác sửa chung thư mục).
- Pi: chờ nguồn Pi 5 chính hãng (Pi đèn đỏ, sụt nguồn khi chạy camera + nhận diện 3 luồng).

## Đã xong (đều đã commit và push, HEAD lúc viết: `9241863` + sổ ghi)
- Bước 1b đo mốc hồ sơ máy bay giữ 25 m, camera cố định: dive15 s1 PASS 1,72 s, s2 FAIL 2,13 s, s3 PASS 0,77 s; dive25 s1 FAIL (mất hẳn); blackout:soft PASS; disengage:soft PASS (cột số đo trống).
- Hồ sơ giữ 15 m (`89857ad`), bước 2 hình học khớp `dtrack/gimbal.py` (`899ffbc`), bước 3 servo + cấu hình (`e16a57b`), bước 4 bộ điều khiển khớp (`f31bbbb`), bước 4b chuyển tiếp góc nâng (`7f3c55d`), bước 5 nối app + `gimbal.csv` (`cbd68cd`), bước 6 bộ chấm đọc góc khớp thật (`eb9f1dc`). Mỗi bước: test trước → mã → 08 rà duyệt. Cả bộ 694 passed trước khi đổi dải khớp.
- Bước 7 đợt A (thông đường) đạt 5/5 cổng; đợt B 6 lần lõi giữ 25 m: pha cắm ra khung 0 s ở cả 6 lần, kể cả cắm 25° (mốc camera cố định: mất hẳn); nhưng 6/6 FAIL ở "giảm tốc cuối: ra khung ≤ 2,0 s" (7,2–12,3 s).
- Nguyên nhân gốc (10 investigator, mức chắc chắn cao): giới hạn δ_max 90° khi drone bay chậm phía trên mục tiêu; tính lại với δ_max 110° thì 0 s ở 5/6 lần. Sự kiện δ vọt về 10° ở dive25 s2 là do một phát hiện giả lọt qua lớp kiểm bắt lại của tracker.
- Pi: camera `imx708_wide` nhận và chụp được; đã chép `labview`, cài flask, sửa `pyvenv.cfg` (có bản sao lưu) trong `~/dtrack`.

## Chưa xong
Đang dở:
- Bước 7 đợt C: 07 đang chạy 14 lần (đối chứng khớp đứng yên, servo chậm ×2, góc giữ −10/−15/+4, tắt ramp, giữ 20/15/12 m, 20 m/s), dùng δ_max 90° cũ. Chưa có kết quả.
- Đổi dải khớp 10–110°: test đã sửa (17 ca ĐỎ có chủ đích, 681 xanh; bộ test dự án đang đỏ), CHƯA commit; mã chưa sửa (chờ đợt C xong): `dtrack/gimbal.py:17`, `dtrack/config.py:118`, `config.py:211-212` (cho phép tới 120).
- Trang lab trên Pi với camera thật: dừng vì sụt nguồn; `lab/Mo-man-hinh-pi.cmd` chưa chạy thật.
Chưa bắt đầu:
- Chạy lại 6 lần lõi với δ_max 110°; chọn khoảng cách giữ mặc định từ số đo; báo cáo cuối giai đoạn 1.
- Điều tra vì sao drone leo cao khi mất hình (COAST/LOST).
- Giai đoạn 2 (tìm lại mục tiêu), gồm sửa lỗi phát hiện giả lọt qua tracker.
- Cập nhật `HANDOFF.md`, `README.md` gốc cho ngày 18.

## Chưa kiểm chứng
- Hồ sơ 15 m và các khoảng cách 20/12 m chưa có kết quả mô phỏng (đang ở đợt C).
- Dải 10–110° mới chỉ có phép tính lại từ log, chưa có lần mô phỏng nào.
- Trang lab trên Pi: chưa có số đo tốc độ khung, chưa kiểm đường hầm SSH; chưa biết lần sập nguồn có làm hỏng file trên thẻ không.
- Báo cáo phân tích lô mốc 5 lần của 07 (lượt đầu phiên) chưa nộp; mới có số thô.
- Đồng hồ `gimbal.csv` so với `truth.csv`: khớp ở đợt A; lệch hằng số < ~1 s bộ chấm không phát hiện được.

## Tồn đọng khác
- Bộ lọc an toàn của model đã dừng 10 lượt giao việc viết test bước 3, 4, 4b (Sonnet và Opus, nhãn `general_harms`); phần đó sau làm được khi giao lại và khi người dùng chuyển một phần sang phiên khác. Mã yêu cầu ghi trong sổ ghi.
- Panel "Văn phòng" (`mcp__office-panel__plan`) vẫn lỗi; đề xuất sửa ở `~\.claude\office\proposals\2026-11-18-08-panel-plan-loi-dinh-dang-ket-qua.md`, chưa áp dụng.
- Cổng 8080 trong WSL đang bị trang demo video cũ chiếm.
- Mật khẩu Pi người dùng đã gõ vào cuộc trò chuyện: không dùng, không lưu; nên đổi.
- Số lượt gọi vai của giai đoạn 1 đã vượt xa mốc 1,5 × ước lượng trong kế hoạch.
- Các mục Nhỏ của 08 ở từng bước: xem sổ ghi.

## Bước tiếp theo
1. Chờ đợt C xong, đọc kết quả, 08 đối chiếu.
2. 05 sửa 3 dòng mã cho dải 10–110°, 08 rà, commit cả test lẫn mã.
3. Chạy lại 6 lần lõi với 110°, thêm khoảng cách giữ tốt nhất từ đợt C; điều tra việc leo cao khi mất hình.
4. Báo cáo cuối giai đoạn 1, DỪNG chờ người dùng xem trước khi sang giai đoạn 2.
5. Khi Pi có nguồn mới: đọc log lần sập, chạy 2 luồng, đo 60 s, kiểm đường hầm.

---
# CẬP NHẬT LÚC TẠM DỪNG (đọc phần này trước; nó thắng phần trên nếu mâu thuẫn)

## Việc phải làm đầu tiên ở phiên sau
- XÓA `onboard\simtools\out\_STOP` trước khi chạy mô phỏng. Kiểm `pgrep -x arducopter` trống và `git status` sạch trong WSL `Ubuntu-24.04`.

## Thay đổi so với phần trên
- Đợt C XONG (14 lần, 2 PASS / 12 FAIL với δ_max 90°): đối chứng khớp đứng yên thất bại ở pha cắm như yêu cầu; servo chậm ×2 vẫn đạt pha cắm; giữ 15 m là mức gần đứng vững nhất (d3 nhỏ nhất 10,3–11,0 m, sàn 6 m; không dính lỗi trôi xa > 40 m); 12 m bắt đầu ra khung khi cắm 25°. Chi tiết trong sổ ghi.
- Dải khớp 10–110° XONG và đã commit `909ab41` (test trước → 05 sửa 3 dòng → 08 duyệt; cả bộ 698 passed). Bộ test dự án không còn đỏ.
- Đợt D (δ_max 110°) ĐANG DỞ, dừng bằng cờ `_STOP`: đã xong 3/14, cả ba PASS toàn bộ: giữ 25 m, dive15 seed 1, 2, 3 (`out/20261118_145823`, `150242`, `150701`): giảm tốc cuối ra khung 0,00 s (đợt B với 90°: 12,32 / 7,49 / 8,13 s); δ thực dùng tới 110,0°, chạm giới hạn 2 lần (119–142 mẫu); d3 giảm tốc cuối 20,8–26,1 m. Lần 4 (giữ 25 m, dive25 seed 1) đang chạy lúc đặt cờ: xem báo cáo của 07 ở cuối sổ ghi.
- CHƯA chạy của đợt D: `plane_r25_gimbal_e12` dive25 seed 2, 3 (và seed 1 nếu lần 4 không trọn); `plane_r15_gimbal_e12` dive15 seed 1, 2, 3, dive25 seed 1, 2, 3, `1:blackout:soft`, `1:disengage:soft`. Script: `onboard\simtools\out\run_gimbal_batch*.sh` (không vào git; cấu hình ở `onboard\simtools\configs\`).

## Bước tiếp theo (thay danh sách ở trên)
1. Xóa `_STOP`, chạy nốt đợt D (07), 08 đối chiếu số đo đợt A–D với tiêu chí nghiệm thu.
2. 10 điều tra vì sao drone leo cao khi mất hình (COAST/LOST).
3. Báo cáo cuối giai đoạn 1 (kèm đề nghị mặc định: giữ 15 m, nhìn xuống 12°, khớp 10–110°), DỪNG chờ người dùng trước khi sang giai đoạn 2.
4. Pi: khi có nguồn mới, đọc log lần sập, chạy trang lab 2 luồng, đo 60 s, kiểm đường hầm (tắt demo cũ ở cổng 8080 trước).
5. Cập nhật `HANDOFF.md`, `README.md` gốc.
