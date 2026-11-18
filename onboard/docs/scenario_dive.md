# Kich ban nghiem thu CAM XUONG (mo phong)

Thay cu phanh gap (~8 m/s^2) cua muc tieu: drone that hiem khi phanh. Muc tieu bay thang 10 m/s, **dot ngot** doi huong
cam xuong, bay bang o do cao thap hon, cuoi chuyen **giam toc nhe** nhu chuan bi ha canh.

## Chay
Mot lan thu (khoang 4-5 phut that, KHONG chay khi may dang huan luyen model):

    STRAIGHT=1 PROFILE=accept_gimbal_r25 DIVE_DEG=15 bash onboard/simtools/run_closed_loop.sh 10
    STRAIGHT=1 PROFILE=accept_gimbal_r25 DIVE_DEG=25 bash onboard/simtools/run_closed_loop.sh 10

Nghiem thu (ma tran mac dinh = 3 seed x dive15, 3 seed x dive25, blackout, disengage):

    bash onboard/simtools/run_acceptance.sh
    MATRIX="1:none:dive15 1:none:dive25" bash onboard/simtools/run_acceptance.sh     # chay mot phan

Bien: `DIVE_DEG` (> 0 bat ca cam; yeu cau `SCENARIO=none`, tu dat `STRAIGHT=1`), `DIVE_DROP` (m ha xuong, 40),
`ALT` (do cao hanh trinh, 70 khi cam), `TARGET_DECEL` (giam toc cuoi, 1.5 m/s^2).

## Dien bien (target_dive.py + sim_helper.py)
1. Muc tieu cat canh len 70 m, chaser len cung do cao, vao vi tri, hoi tu nhu cu.
2. Sau go: bay thang huong Bac 10 m/s. Cua so cham 120 s nhu cu (t_ws .. t_ws+120).
3. t_ws + 125 s: helper ghi file `dive`; muc tieu doi vector van toc NGAY (3D van 10 m/s): ngang = 10*cos(g), xuong = 10*sin(g).
   - dốc vừa g = 15 do: xuong 2.59 m/s, ngang 9.66 m/s, ha 40 m mat ~15.4 s.
   - dốc gắt g = 25 do: xuong 4.23 m/s, ngang 9.06 m/s, ha 40 m mat ~9.5 s.
4. Con cach do cao dich (30 m) chung vd^2/(2*2) m thi vuot len bay bang (luat P cua target.py), ngang tro lai 10 m/s.
5. Helper giu (drop/vd + 15 s) sau lenh cam roi ghi `stop`: muc tieu giam toc ngang 1.5 m/s^2 toi 0 (khong phanh gap), giu do cao.

## Gioi han da biet (tu ma ArduPilot 4.7, doi chieu `~/ardupilot`)
- SITL muc tieu nap `models/freestyle.param`: `WP_SPD_DN 5.0`, `WP_ACC_Z 3.0`, `WP_SPD_UP 5.0` (`sim/run_sitl.sh`). Toc do xuong
  lenh bi cat o 5 m/s => voi 10 m/s goc toi da 30 do. `target_dive.py` va `run_closed_loop.sh` tu choi vd > 5 m/s.
  (Chua kiem bang chay SITL: can xem `tgt_vd` trong truth.csv dat dung gia tri lenh.)
- Chaser: `guidance.descend_max_mps = 4`, `min_alt_m = 10`: ca 25 do (xuong 4.23 > 4) chu y bat chaser khong theo kip theo phuong dung.
- Do cao 30 m cu khong du de cam 40 m: do cao hanh trinh 70 m, ha ve 30 m (chaser con cach san 10 m xa).

## Tieu chi cham them (analyze_closed_loop.py; cac tieu chi bay deu cu giu nguyen)
| Tieu chi | Nguong | Nguon |
|---|---|---|
| events.json du t_go, t_dive_cmd, t_stop_target, dive_deg, dive_drop_m; both_stopped = true | thieu/false -> FAIL | tranh PASS nham khi log thieu |
| muc tieu thuc su ha | >= 0.8 * DIVE_DROP | phat hien SITL cat toc do |
| toc do ha dinh cua muc tieu | >= 0.8 * speed * sin(goc) | SITL cat toc do xuong (WP_SPD_DN) |
| pha cam (lenh .. stop): d3 min | >= range_min (12.5 m, config) | config.py |
| trong va sau cam (lenh .. stop): d3 max | <= 40 m (`--dmax`) | de xuat truong phong |
| muc tieu ra khoi khung trong pha cam (lenh .. het ha + 5 s) | <= 2.0 s (`--out-max`) | de xuat, can xem lai sau so do dau tien |
| muc tieu ra khoi khung trong pha bay bang (het pha cam .. stop) | <= 2.0 s (`--out-max`); in them khoang lien tuc dai nhat va tong tu lenh cam toi het chuyen | nhu tren |
| do cao chaser (lenh cam .. het chuyen) | >= min_alt_m - 1 = 9 m (`--alt-floor`) VA >= (do cao dich cua muc tieu sau cam - 10 m, `--alt-margin`) | config.py; san tuong doi moi |
| giam toc cuoi (stop .. dung): d3 min / d3 max / ra khoi khung | >= 12.5 m / <= 40 m / <= 2.0 s | nhu tren |
Ca khong cam (target.py, target_softbrake.py): pha phanh cuoi chi IN cac so, khong cham, tru khi them `--score-final`.
Dong truth.csv thieu/hong gia tri so bi bo (in canh bao), khong con lam sai min/max.
In them (khong cham): d3 max doan bay deu truoc lenh cam (t_ws .. lenh cam) de doi chieu nguong 40 m. un_acceptance.sh tu choi che do khac '', soft, diveNN (NN nguyen duong): bao loi, thoat 2 truoc khi chay gi.
