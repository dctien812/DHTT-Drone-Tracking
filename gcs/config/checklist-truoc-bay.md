# Checklist GCS truoc / trong / sau buoi bay

(De xuat, chua duoc bay thu. Nguoi dung sua cho hop thuc te.)

## Truoc khi ra san (o nha)
- [ ] Laptop day pin, mang theo sac + day USB du phong
- [ ] Chay `Test-Gcs.ps1` (Desktop): khong co FAIL
- [ ] Dong ho he thong dung (WARN neu lech) de log/tlog co gio dung
- [ ] Ban do ngoai tuyen da prefetch cho khu vuc bay (gmapcache)
- [ ] Da kiem tham so failsafe/hang rao trong `dtrack-failsafe.param` va nap neu da duyet
- [ ] Bat MAVLink signing QUA CAP USB (khong qua WiFi/UDP) truoc buoi bay. ArduPilot 4.7.2 co ma ho tro (`libraries/GCS_MAVLink/GCS_Signing.cpp`); cach bat trong Mission Planner CHUA kiem, va CHUA kiem ELRS Backpack co chuyen goi da ky hay khong
- [ ] Xac nhan `ARMING_SKIPCHK = 0` tren FC (tham so co trong `libraries/AP_Arming/AP_Arming.cpp` cua 4.7.2; 0 = khong bo kiem tra nao truoc khi arm)
- [ ] Da doi mat khau WiFi Backpack khoi mac dinh; dang dung tai khoan Windows thuong (khong phai admin); Tailscale/ZeroTier TAT
- [ ] (Lan cai dau) Da xem NGUOI KY cua tung goi do Get-GcsPackages.ps1 in ra va doi chieu bang nguon ngoai USB; da dien expectedPublisher trong manifest.json (neu chua: Install se hoi xac nhan tung goi - dung bam Yes khi chua doi chieu)
- [ ] Bang tong ket Install: khong con muc 'con phai lam tay' bi bo sot (vd cai /passive qua han, Public Desktop cho tai khoan thuong ghi, goi chay voi -AllowUnsigned)
- [ ] Test-Gcs khong bao FAIL ACL (cay C:\GCS: chi Administrators/SYSTEM ghi, khong junction); shortcut tren Public Desktop tro dung MissionPlanner.exe / Test-Gcs.ps1 trong C:\GCS

## Tai san bay, truoc khi arm
- [ ] Cam sac laptop hoac pin day; tat che do tiet kiem pin cua may
- [ ] Noi WiFi "ExpressLRS TX Backpack"; MP chon UDP, cong 14550, bam Connect
- [ ] Thay heartbeat, GPS lock, so ve tinh/HDOP dat yeu cau
- [ ] Home dung vi tri; hang rao (FENCE) va RTL_ALT_M dung voi san bay
- [ ] Thu failsafe RC tren mat dat (thao day, khong co canh quat/khong arm) truoc buoi bay dau
- [ ] Mo dung phien MP, bat ghi tlog

## Trong khi bay
- [ ] Theo doi pin, GPS, mat lien lac; nguoi dieu khien giu tay tren cong tac che do
- [ ] Neu Install-Gcs dung vi "C:\GCS da ton tai nhung KHONG dat kiem tin cay": doi ten hoac xoa C:\GCS bang tai khoan admin roi chay lai (khong con co -AdoptExistingRoot; script khong tu doi ten/reset)
- [ ] Neu mat telemetry: khong tu tin vao GCS, dung RC

## Sau khi bay
- [ ] Disarm, cho log ghi xong, dong MP
- [ ] Chep `Documents\Mission Planner\logs` (tlog) va log tren SD/FC ve luu tru
- [ ] Ghi lai bat thuong (failsafe nao da kich, canh bao nao)
- [ ] Neu da chinh MP: luu lai config.xml mau vao `gcs\config\MissionPlanner\`
