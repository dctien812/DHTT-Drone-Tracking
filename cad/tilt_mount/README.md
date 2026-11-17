# Khop gat mot truc MG90S + Pi Camera Module 3 Wide (ban dau, chua in thu)

Ma CadQuery tham so; moi tham so o dau `tilt_mount.py`. Don vi mm.

## Chay (WSL Ubuntu-24.04, venv ~/venv-cad: cadquery, trimesh, numpy, pytest, matplotlib)
- `wsl -d Ubuntu-24.04 -- bash /mnt/d/Personal/Drone-Tracking/cad/tilt_mount/run.sh`  (STEP, STL, PNG vao `out\`)
- `wsl -d Ubuntu-24.04 -- bash /mnt/d/Personal/Drone-Tracking/cad/tilt_mount/test.sh`  (pytest)
- `setup.sh` tao venv va cai thu vien.

## Chi tiet in (`out\*_print.stl` da xoay dung huong in)
| File | Vat lieu | Mat dat ban | Support |
|---|---|---|---|
| base (de chu U: san + 2 vach) | PETG/PLA | san | khong; cua so servo bridge ~23 mm |
| bracket (gia kep camera) | PETG/PLA | mat sau tam (nam phang) | khong; lo hub O7,45 nam ngang, bridge nho |
| spacer (ong lot chot, O8) | PETG/PLA | dung dung | khong |
Lop 0,2, dau phun 0,4, 4 chu vi, infill >= 25 %.

## Vit va phu kien
- 4 x M3x10 (+ dai/long den) bat de xuong tam go: lo O3,3.
- 2 x vit tai servo (kem servo, hoac M2x6) bat tai servo vao vach 1 (lo ren O1,7).
- 4 x M2x8 bat bo camera vao tru (lo ren O1,7).
- 2 x vit M2x6 (kem horn) bat canh tay horn vao ma 1 qua lo O2,3 tu phia ngoai ma.
- 1 x vit giu horn (kem servo) vao truc ra, vặn qua lo hub O7,45 o ma 1.
- 1 x M3x14 lam chot ben ma 2 (xuyen vach 2, spacer, ren vao ma 2 lo O2,6).
- Tuy chon (chua lam): vong bi 623.

## Lap
1. Bat servo vao vach 1: than servo nam ngoai (x<0), tai ap mat ngoai vach, 2 vit.
2. Gan horn mot canh len ma 1 bang 2 vit M2x6 (canh tay chi ve phia sau, -Y), chua vit hub.
3. Bat bo camera len 4 tru bang 4 vit M2x8 (dau noi o canh duoi, cap di xuong qua cua so san).
4. Tha cum gia kep tu tren xuong giua hai vach, o vi tri cach vach servo ~5 mm; day ve phia servo cho horn an vao truc ra; vặn vit hub qua lo O7,45.
5. Xau M3x14 qua vach 2 va spacer, ren vao ma 2; xiet toi khi dau vit cham vach roi noi nhe (de quay tu do).
6. Bat de xuong tam go bang 4 vit M3.

## Nguon kich thuoc
Tat ca kich thuoc linh kien la so pho bien, CHUA DOI CHIEU NGUON (khong co mang trong phien nay).
Nen doi chieu: datasheets.raspberrypi.com (Camera Module 3 mechanical drawing) va ban ve MG90S cua nha san xuat.

## Chinh sau lan in dau
`CLR` (khe ho chung), `SV_*` (than/tai/truc servo), `HORN_*` (ban kinh lo, chieu cao hub), `HOLE_DX/DZ`,
`BOARD_*`, `LENS_*`, `POST_H` (chieu cao tru), `FAR_GAP`/`PIN_PLAY` (ho doc truc), `AX_H`.

## Han che da biet
- Gan giua cua so servo va lo vit tai chi ~1,5 mm (< 1,6) do hinh hoc servo; co kiem trong pytest.
- Non nhin 120 do kiem voi vach, servo, gia kep; de (san) KHONG tinh (khi nhin xuong -60 do thi tat nhien thay de).
- Hinh PNG ve bang matplotlib (thu tu ve gan dung), chi de xem nhanh; xem STEP trong Fusion de chinh xac.