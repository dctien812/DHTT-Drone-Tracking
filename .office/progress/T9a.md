# T9a progress (append-only)

## 2026-11-16 (buoc 1)
1. Xong:
   - Tao: onboard/dtrack/{config,guidance,supervisor,mavlink_io,logger,app}.py; onboard/simtools/{__init__,sim_truth_source,sim_helper,analyze_closed_loop}.py, run_closed_loop.sh; onboard/tests/{test_guidance,test_supervisor}.py
   - pytest -q (WSL venv): 174 passed (71 cu + 103 moi). Lenh: wsl -d Ubuntu-24.04 -- bash <scratchpad>/pt.sh  (cd onboard; ~/venv-ardupilot/bin/python -m pytest -q)
   - Da xac minh trong ~/ardupilot: type_mask vel+yaw=2503, vel-only=3527 (common.h:1545-1556; GCS_MAVLink_Copter.cpp:896-918,998+), GUID_TIMEOUT=3s (Parameters.cpp:875), SIM_STATE dung duoc de lay vi tri that (SITL.cpp:1605).
   - Khong con arducopter mo coi (ps kiem truoc khi chay).
2. Dang lam: chua chay SITL lan nao; chuan bi chay thu run_closed_loop.sh 10.
3. Ke tiep: chay thu 1 lan (smoke), sua loi; chay 10 m/s x3 seed (SEED=1..3); 20 m/s; kich ban blackout (SCENARIO=blackout); disengage (SCENARIO=disengage); viet README.md + them pymavlink vao requirements.txt; bao cao cuoi.
4. Lenh chay: wsl -d Ubuntu-24.04 -- bash -lc 'cd /mnt/d/Personal/Drone-Tracking/onboard/simtools && SEED=1 bash run_closed_loop.sh 10'   (ket qua o onboard/simtools/out/<ts>_<speed>ms_s<seed>_<scenario>/result.txt)
5. Luu y: cong SITL target 5760(target.py) 5762(SimTruthSource) 5763(helper); chaser 5770(app) 5772(helper) 5773(SimTruthSource). Phu thuoc sim/: run_sitl.sh, target.py, chaselib (khong dung trong helper), chase.parm. Khong goi sim/run_chase.sh (co pkill).

## 2026-11-17 buoc 2
1. Chay SITL 2 lan (10 m/s seed1): lan 1 tilt cam 15 do -> muc tieu ngoai khung luc hover (doi default 8 do). Lan 2: chaser mat lenh do BUG guidance: gia toc luu cho jerk gom ca buoc cat an toan -> tu khuech dai (lenh troi toi -30 m/s). Da sua (a_out = a_des). Ha tang vong kin (helper/app/analyze) chay duoc.
2. Dang lam: chay lai 10 m/s seed1.
3. Ke tiep: nhu truoc (3 seed, 20 m/s, blackout, disengage, README, requirements).

## 2026-11-17 buoc 3
- Chan doan 3 lan chay: (a) tilt cam 15 -> muc tieu ngoai khung luc hover; (b) bug jerk khuech dai; (c) chaser bi nghieng +-20..45 do khi gia toc/phanh => muc tieu ra khoi khung hinh (+-13 do doc) -> COAST -> khoang cach ngoai suy sai -> lui manh. Da doi: a_max 2, a_back 3, jerk 4, back_speed 5, kp 0.4, tilt 10, giu yaw khi phanh, khong cat tuc thi thanh phan tien lai gan (chi cat theo van toc hien tai). pytest 174 passed. Dang chay lai 10 m/s seed1.

## 2026-11-17 buoc 4
- Vong kin chay duoc toi cua so do: chaser bam 15 m on dinh ~45 s o 10 m/s roi mat muc tieu khi muc tieu doi huong (pitch chaser +-25..30 do vuot FOV doc camera). Doi: camera 6 mm (fx 1739, ~45x35 do), tilt 12, a_max 2/a_decel 1/a_back 3, kp 0.3, dong bang khoang cach khi COAST, helper cho chaser settled 15 m truoc khi cho muc tieu bay. Dang chay lai 10 m/s seed1.

## 2026-11-17 buoc 5
- Lan chay 10 m/s seed1 voi tilt15/close2/kp_vert0.5: TRACK 81%, sai so TB 31.9 m, min 7.8 m (FAIL): bam 14.5 m on dinh khi chay thang nhung mat muc tieu o cac lan doi huong cua muc tieu. Them yaw lead 0.5 s. Dang chay lai.

## buoc 6: nguyen nhan mat muc tieu o cac lan re: gioi han a_max=2 doc huong < gia toc huong tam khi muc tieu re (2.6 m/s^2) nen chaser tut lai 80 m. Them a_lat=4 (vuong goc huong bay), jerk 6. Chay lai 10 m/s seed1.

## buoc 7: 10 m/s seed1 (out/20261116_213253_10ms_s1_none): sai so TB 1.34 m, RMS 1.79, max 5.52, min d3 10.31 m, TRACK 100%, range_valid=False 0; chi FAIL o 'khoang trong truth <= 0.2 s' (0.223 s tai t_rel 75.9 s, pha ket noi app, khong phai trong cua so; app loop_dt max 35 ms). Dang chay run_all.sh (10/seed2, 10/seed3, 20/seed1, blackout, disengage) -> onboard/simtools/out/_run_all.log (cho dong ALLDONE). Sau do: README.md, requirements.txt, bao cao.
