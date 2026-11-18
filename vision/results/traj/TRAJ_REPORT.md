# Thu loc theo quy dao (may bay vs drone) - ngoai tuyen, 2026-11-18

Lenh chay lai toan bo (~50 s, 1 luong, khong chay model): `wsl -d Ubuntu-24.04 -- bash /mnt/d/Personal/Drone-Tracking/vision/scripts/run_traj_filter_try.sh`
(in bang day du ra man hinh; log mau: `run_full.log`; so lieu: `results.csv`).

## Ket luan
**Chua dang dua vao lab.** Co tin hieu, nhung chi 4 video / 8 vet may bay; dac trung "thang/deu" nhu gia thuyet **khong** phan biet duoc.
Thu duoc la "muc tieu gan nhu dung yen so voi nen sau khi tru chuyen dong camera" - dung la trang thai drone luc lo lung, tuc loai nham dung luc can bam.

## Du lieu
ByteTrack chay lai tren `runs/b1_det/ft_full/*.npz` (conf 0,25): 625 vet; may bay 8 vet (1266 khung), drone 617 vet (32888 khung; 115 video, gom `VIDEO.MOV` = drone cam tay, da xem 3 khung). Vet du N khung: N=15: 7 may bay/268 drone; N=30: 7/216; N=60: 6/147. Du lieu theo khung co san nen khong chay lai nhan dien.

## Bang chinh (bo-ra-mot: 4 fold, moi fold giu 1 video may bay + 1/4 video drone; nguong + chieu chon tren phan con lai theo Youden co trong so theo do dai vet)
Moc khong loc: may bay bi loai 0% (100% con goi la drone), drone bi loai nham 0%. "khung" = chi tinh khung SAU thoi diem quyet dinh.

| bu camera | quan sat | dac trung | vet may bay loai | vet drone loai nham | khung may bay loai | khung drone loai nham |
|---|---|---|---|---|---|---|
| khong | 1 s | tot nhat (straight) | 3/7 | 59/216 | 31% | 21% |
| co | 0,5 s | turn | 7/7 | 59/268 | 91% | 22% |
| co | 1 s | speed_w | 6/7 | 30/216 | 60% | 10% |
| co | 2 s | turn | 6/6 | 22/147 | 67% | 7% |
| co | 2 s | speed_w | 5/6 | 19/147 | 47% | 5% |

(`turn` = doi huong trung binh, gan nhu chi la co "dung yen" vi dung yen duoc gan pi; `speed_w` = toc do tren anh / be rong hop.) Chi tiet theo video may bay: cot `air_001..004` trong `results.csv`; video 004 (camera dung yen) khong bi loai theo speed_w.

## Dac trung nao co tac dung
- Khong bu camera: yeu va khong on dinh (AUC 0,5-0,7, chieu nguong doi giua cac fold).
- Co bu camera: toc do tren be rong hop thap (speed_w, AUC dao 0,07-0,10) va "dung yen" (turn). `straight`, `lin_res`, `acc_w`, `speed_cv`, ti le rong/cao, doi co hop: khong co tac dung ro.- Che do ngan sach 10% drone nham (`fpr10`) gan nhu khong loai duoc may bay (xem csv).

## Camera
Camera chuyen dong **tuong quan voi lop**: 3/4 video may bay co dich nen trung vi 1,3-2,2 px/khung, drone trung vi 0,15 (3/115 video > 1 px). Neu khong bu, dac trung dinh voi chuyen dong camera. Bu bang phaseCorrelate (nua do phan giai, tinh tien thuan, ~50 s cho 38k khung), sai so cuoi nho hon chuyen dong cua may bay xa (~0,2-0,5 px/khung) nen ket qua co the la do nhieu bu. Chua do do chinh xac cua phep bu.

## Gioi han / chua kiem chung
- 4 video, 6-7 vet may bay: do tin cay thap; khong co khoang tin cay. Nguong "chon tren 3 video, cham tren 1" co the do nhieu va khong on.
- Chua tinh ti le video drone bi mat vet chinh; chua thu ket hop nhieu dac trung; chi conf 0,25.
- Vet drone ngan/ phan manh (357/625 vet khong du 15 khung) khong duoc danh gia; nhan "drone" cho moi vet trong video drone (co vet la bao dong gia).
- May bay chi ~21-68 px, do trong cac video nay, khong dai dien may bay gan.

## File
`vision\scripts\traj_filter_try.py`, `vision\scripts\run_traj_filter_try.sh`, `vision\results\traj\` (TRAJ_REPORT.md, results.csv, features_{raw,comp}_c0.25.csv, tracks_c0.25.csv, camshift.csv, camshift_summary.csv, run_full.log).
