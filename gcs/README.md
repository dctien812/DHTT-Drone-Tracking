# Bộ cài trạm mặt đất (GCS) di động — Mission Planner

Mục tiêu: biến một laptop Windows 10/11 x64 sạch thành GCS cho drone ArduCopter 4.7 (FC Matek H743-WING V3, Raspberry Pi 5 đồng hành). Mọi script chạy trên Windows PowerShell 5.1.

**Trạng thái:** bản viết ngày 2026-11-16, mới được kiểm cú pháp và chạy `-WhatIf` trên máy cá nhân. **Chưa chạy thật trên laptop GCS nào.** Xem mục 6.

Cấu trúc:

```
gcs\
  manifest.json          danh sách gói
  GcsLogic.ps1           hàm dùng chung (kiểm đường dẫn/ACL/chữ ký...), được chép sang C:\GCS\tools cùng Test/Uninstall
  Get-GcsPackages.ps1    tải gói (máy có Internet)
  Install-Gcs.ps1        cài (laptop GCS, admin)
  Test-Gcs.ps1           kiểm sau cài (không cần admin)
  Uninstall-Gcs.ps1      hoàn tác
  tests\Test-GcsLogic.ps1  kiểm các hàm thuần logic, không cần admin, không đụng hệ thống
  config\                dtrack-failsafe.param, checklist-truoc-bay.md
  drivers\               (tự tạo, tự chép file .inf + .cat vào nếu cần)
  packages\              (do Get-GcsPackages.ps1 tạo)
```

## 1. Chuẩn bị USB trên máy có mạng

```powershell
cd <thư mục gcs>
powershell -ExecutionPolicy Bypass -File .\Get-GcsPackages.ps1 -CheckOnly   # chỉ kiểm URL còn sống
powershell -ExecutionPolicy Bypass -File .\Get-GcsPackages.ps1               # tải vào packages\ (~700 MB nếu lấy đủ; riêng MAVProxy ~370 MB)
```

- Kết quả: `packages\*` và `packages\checksums.json` (SHA256, kích thước, ngày tải, và với từng `.msi/.exe`: trạng thái Authenticode, subject, thumbprint người ký; `.zip` ghi `signed:false`). Lỗi gói tùy chọn không làm hỏng cả lượt; lỗi gói bắt buộc thì script thoát mã 1. Script in rõ gói nào KHÔNG có chữ ký hợp lệ.
- **SHA256 và chữ ký số (đọc kỹ):** SHA256 nằm cùng USB với gói nên chỉ chống file hỏng, KHÔNG chống bị thay file (ai thay được gói cũng thay được `checksums.json`). Điểm tin cậy là chữ ký số: máy có mạng nên chạy `Get-GcsPackages.ps1` và đọc trạng thái chữ ký/người ký của từng gói TRƯỚC khi chép vào USB. Khi cài, `Install-Gcs.ps1` chép gói vào `C:\GCS\packages\` (chỉ admin ghi) rồi kiểm trên **bản chép**: SHA256 khớp VÀ chữ ký `Valid` VÀ thumbprint/subject khớp bản ghi lúc tải; mọi bước sau (chạy, thử lại 1618, giải nén) dùng bản chép đã kiểm, nên đổi file trên USB giữa chừng không có tác dụng. SHA256 sai thì luôn dừng. **Chưa kiểm trạng thái chữ ký thật của từng gói** (chưa tải gói nào để xem); nếu MSI Mission Planner thực tế không có chữ ký hợp lệ thì Install sẽ dừng. Máy đích không có Internet: chưa kiểm Status có còn `Valid` khi không kiểm tra thu hồi chứng chỉ được.
- **Điểm tin cậy ngoài USB: `expectedPublisher`.** Mỗi gói trong `manifest.json` có trường `expectedPublisher` (mảng mẫu wildcard `-like`, không phân biệt hoa thường, so với subject người ký, ví dụ `"*O=Tên Nhà Phát Hành*"`). **Mặc định để rỗng và tôi không tự bịa tên nhà phát hành.** Cách điền: chạy `Get-GcsPackages.ps1` trên máy có mạng, đọc dòng `NGƯỜI KÝ: subject=[...] thumbprint=[...]` in cho từng gói, đối chiếu với trang chính thức của nhà phát hành bằng đường khác (không dùng nguồn trên USB), rồi điền mẫu vào manifest. Khi đó người ký không khớp → Install dừng (không bỏ qua được bằng `-AllowUnsigned`). Khi còn rỗng → Install in subject + thumbprint người ký và **hỏi xác nhận từng gói** (`ShouldContinue`; chạy không tương tác thì từ chối). Gói `.zip` không có chữ ký nên luôn hỏi xác nhận.
- **`-AllowUnsigned <id>[,<id>...]`** (ví dụ `-AllowUnsigned missionplanner-msi,mavproxy`) chỉ áp cho đúng các gói đó: cho chạy dù thiếu checksum/chữ ký không hợp lệ và bỏ qua câu hỏi xác nhận; in cảnh báo lớn, ghi log, ghi vào "còn phải làm tay". Không có dạng áp cho tất cả. Id không có trong manifest thì script dừng.
- QGroundControl trong manifest là **bản daily, không dùng để bay**. Gói winget `verified:false` (Zadig, ZeroTier) chỉ cài khi có `-AllowUnverified`.
- Thêm `-RequiredOnly` nếu chỉ muốn MSI. Gói winget (Tailscale, Zadig, ZeroTier) không tải về, chỉ cài trên laptop khi có Internet.
- Tùy chọn: đặt file mẫu vào `config\MissionPlanner\config.xml` và bản đồ vào `config\gmapcache\`; chép file `.inf` driver vào `drivers\`.
- Chép cả thư mục `gcs\` sang USB.

## 2. Cài trên laptop

Mở PowerShell **Run as administrator** (script không tự nâng quyền). Nếu các file script bị đánh dấu tải từ mạng: `Get-ChildItem -Path . -Filter *.ps1 | Unblock-File` (chỉ áp cho các file `.ps1` của bộ cài; KHÔNG chạy `Unblock-File` đệ quy lên `packages\` — các gói cài phải được kiểm bằng checksum và chữ ký, không phải bỏ dấu chặn).

```powershell
cd <USB>\gcs
powershell -ExecutionPolicy Bypass -File .\Install-Gcs.ps1 -WhatIf     # xem trước, không đổi gì, không cần admin
powershell -ExecutionPolicy Bypass -File .\Install-Gcs.ps1              # cài thật
powershell -ExecutionPolicy Bypass -File .\Install-Gcs.ps1 -Include MAVProxy,QGC,Tailscale
powershell -ExecutionPolicy Bypass -File .\Install-Gcs.ps1 -UseZip      # giải ZIP vào C:\GCS\MissionPlanner thay vì MSI
```

Script làm theo thứ tự: tạo và **khóa ACL `C:\GCS`** (bỏ thừa kế; Administrators và SYSTEM toàn quyền, Users chỉ đọc/chạy, đặt theo SID nên đúng cả trên Windows tiếng Trung; **không thư mục nào cho Users ghi**, kể cả `logs`, vì `Test-Gcs.ps1` không ghi log). Thư mục gốc chưa có thì tạo **nguyên tử**: một lệnh `[System.IO.Directory]::CreateDirectory(path, DirectorySecurity)` tạo thư mục kèm chủ sở hữu Administrators và ACL (bỏ thừa kế, Administrators + SYSTEM toàn quyền, Users đọc/chạy; thư mục con thừa kế) ngay lúc tạo, không có khe giữa "tạo" và "đặt ACL"; sau đó kiểm lại chủ sở hữu, ACL, reparse và xác nhận còn rỗng (phòng có ai tạo trước). Thư mục cha phải có sẵn (nên đặt gốc trực tiếp dưới gốc ổ đĩa, như mặc định `C:\GCS`). Thư mục gốc **đã có** thì chỉ tiếp tục khi nó đạt kiểm tin cậy đầy đủ (chủ sở hữu, ACL từng thư mục và file, không có reparse point ở bất kỳ đâu, kể cả thư mục cha) tức là do chính bộ cài này tạo lần trước; không đạt thì script **dừng** và in hướng dẫn làm tay: *đổi tên hoặc xóa thư mục đó bằng tài khoản admin rồi chạy lại*. Script không tự đổi tên, không reset ACL (không còn cờ `-AdoptExistingRoot`: `icacls /reset /T` đi vào junction và reset ACL thư mục đích), không đọc gì từ một gốc không đạt. Ngay trước mỗi lần chạy thứ gì bằng quyền admin lấy từ trong gốc (msiexec kể cả lần thử lại, bộ cài `.exe`, `Expand-Archive`, `Test-Gcs.ps1`) script kiểm lại cả cây và băm lại SHA256 + chữ ký của chính bản chép (không còn bộ nhớ đệm kết quả kiểm); không đạt thì dừng. Hiện trạng cũ trong `state.json` được lọc (GUID đúng mẫu, tên thiết lập powercfg nằm trong danh sách, giá trị số nguyên không âm, trường tường lửa đúng định dạng) trước khi đưa vào lệnh; có giá trị không hợp lệ thì bỏ cả state cũ và chụp lại hiện trạng. Tiếp theo: kiểm tra (Windows x64, .NET ≥ 4.7.2, dung lượng ≥ 3 GB, chép gói bắt buộc vào `C:\GCS\packages\` rồi SHA256 + chữ ký trên bản chép) → lưu hiện trạng `C:\GCS\backup\<ngày giờ>\state.json` → cài MP (MSI im lặng tối đa `-SilentTimeoutMinutes` phút, mặc định 20; quá hạn thì chỉ kết thúc tiến trình `msiexec` client do script tạo, KHÔNG dừng dịch vụ Windows Installer; chờ có hạn tới khi không còn lượt cài nào đang chạy rồi mới chạy `/passive`; mã 1618 thì chờ và thử lại vài lần; cài `/passive` và bộ cài `.exe` tương tác chờ tối đa `-InteractiveTimeoutMinutes`, mặc định 60: hết hạn thì **không** kết thúc tiến trình đang chạy, chỉ báo rõ và ghi vào "còn phải làm tay") → gói tùy chọn → driver (chỉ liệt kê; cài khi có `-InstallDrivers` và `.cat` có chữ ký hợp lệ) → chép config → thiết lập máy (không ngủ/không tắt màn hình/đóng nắp không ngủ cả khi cắm điện và chạy pin; tường lửa inbound UDP 14550–14551 chỉ profile Private, chỉ `-RemoteAddress LocalSubnet`, gắn theo `MissionPlanner.exe` (và quy tắc riêng cho `QGroundControl.exe` nếu có `-Include QGC`), tên `GCS-DroneTracking-...`; quy tắc trùng tên có sẵn thì cấu hình cũ được lưu vào state và Uninstall khôi phục) → shortcut trên Public Desktop → chạy `Test-Gcs.ps1` → bảng tổng kết. Chạy lại được nhiều lần; lần sau dùng lại hiện trạng GỐC trong state cũ (trừ khi Uninstall đã đổi tên nó thành `state.restored.json`). Log: `C:\GCS\logs\install-<ngày giờ>.log`.

Cờ: `-AllowUnsigned <id,...>` (theo từng gói, xem mục 1; SHA256 sai hoặc publisher không khớp thì vẫn dừng), `-AllowUnverified` (cho gói `verified:false`), `-InstallDrivers`, `-SilentTimeoutMinutes`, `-InteractiveTimeoutMinutes`, `-Force`, `-UseZip`. `-GcsRoot` (mặc định `C:\GCS`) phải là đường dẫn tuyệt đối trên ổ cố định, không phải gốc ổ, không nằm trong `C:\Windows`, `C:\Users`, `C:\Program Files*`, `C:\ProgramData`; mọi lệnh hệ thống (icacls, msiexec, powercfg, pnputil, robocopy, taskkill, powershell) gọi bằng đường dẫn đầy đủ `%SystemRoot%\System32\...`.

Tin cậy file công cụ: file trong `C:\GCS\tools` được xóa file đích rồi chép lại (để thừa hưởng ACL thư mục, không giữ chủ sở hữu/DACL cũ) và kiểm chủ sở hữu + ACL từng file. `Install-Gcs.ps1` (bước i), `Uninstall-Gcs.ps1` và `Test-Gcs.ps1` chạy bằng quyền admin từ `C:\GCS\tools` chỉ nạp `GcsLogic.ps1` khi file và thư mục chứa nó do Administrators/SYSTEM sở hữu và không ai khác ghi được; không đạt thì dừng (Install tự chuyển sang bản trên USB; Uninstall/Test-Gcs bảo bạn chạy bản trên USB). ACL được kiểm theo **danh sách cho phép**: chỉ Administrators, SYSTEM, TrustedInstaller được quyền ghi (bất kỳ SID khác có quyền ghi đều bị từ chối, không chỉ Users/Everyone).

Ghi chú khác: Mission Planner do bộ cài này cài được đánh dấu bằng file `C:\GCS\.installed-by-gcs.json` (chỉ tin khi chủ sở hữu/ACL đúng và mã MSI khớp bản đang cài), nên sau Uninstall rồi Install lại, MP đó vẫn được nhận là "của mình" (`-RemoveApps` gỡ được). Quy tắc tường lửa cùng tên có sẵn bị ép về Inbound/Allow/UDP 14550–14551 (cấu hình cũ gồm giao thức, cổng, hướng, hành động được lưu để Uninstall khôi phục). Shortcut nằm trên Public Desktop: nếu thư mục đó cho tài khoản ngoài Administrators/SYSTEM quyền ghi thì bảng tổng kết ghi chú (script không tự đổi ACL Desktop).

Không làm: tắt Defender/UAC/Windows Update, mở cổng profile Public (đừng thêm profile Public vào quy tắc), đặt Active Hours (làm tay, mục 3.5).

Lưu ý: `config.xml` mẫu của Mission Planner được chép vào `Documents` của tài khoản chạy bộ cài (admin), không phải của tài khoản thường dùng để bay. Nếu bay bằng tài khoản khác, chép `config.xml` vào `Documents\Mission Planner\` của tài khoản đó.

Kiểm lại bất cứ lúc nào: `Test-Gcs.ps1 -ListenSeconds 15` (nghe UDP 14550; đóng MP trước vì MP giữ cổng). Phép nghe này mở socket bằng `powershell.exe` nên quy tắc tường lửa gắn theo `MissionPlanner.exe` sẽ không cho gói đi qua: không nhận gói chỉ là WARN, không phải FAIL. `Test-Gcs.ps1` FAIL nếu bất kỳ thư mục hay file nào trong `C:\GCS` (gồm `tools`, `config`, `packages`, `MissionPlanner`) cho tài khoản ngoài Administrators/SYSTEM/TrustedInstaller quyền ghi, có chủ sở hữu sai hoặc là reparse point, hoặc nếu có quy tắc inbound cho `MissionPlanner.exe` bật ở profile Public (ví dụ Windows tự tạo khi bấm Allow trên mạng công cộng).

## 3. Các bước BẮT BUỘC làm tay, theo thứ tự

1. **Nạp firmware lần đầu qua DFU.** Tải STM32CubeProgrammer từ st.com (phải đăng nhập, nên không đóng gói được). Giữ nút BOOT khi cắm USB, nạp file `*_with_bl.hex` của Matek H743-WING (từ firmware.ardupilot.org, thư mục MatekH743). Về sau cập nhật qua Mission Planner (Initial Setup > Install Firmware).
2. **ELRS:** flash/bind TX và receiver theo tài liệu ExpressLRS; trên TX bật Backpack Telemetry = WiFi (chế độ MAVLink). Laptop nối WiFi "ExpressLRS TX Backpack", MAVLink ra UDP 14550. Đặt mạng đó là **Private**.
3. **Prefetch bản đồ ngoại tuyến** (cần Internet): MP > Flight Plan > Prefetch, giữ Alt và kéo khung vùng bay. Kiểm bằng `Test-Gcs.ps1` (dòng gmapcache).
4. **Lưu config.xml mẫu** sau khi chỉnh MP lần đầu: chép `Documents\Mission Planner\config.xml` vào `gcs\config\MissionPlanner\config.xml` (và `C:\ProgramData\Mission Planner\gmapcache` vào `gcs\config\gmapcache\`) để lần sau Install chép lại. Script không tự tạo config.xml vì tên khóa chưa xác minh.
5. **Active Hours** Windows Update: Settings > Windows Update > Advanced options > Active hours (hoặc Pause updates ngày bay).
6. Duyệt từng giá trị trong `config\dtrack-failsafe.param` (ĐỀ XUẤT, CHƯA BAY THỬ) trước khi nạp; tự đặt ngưỡng pin (`BATT_LOW_VOLT`, `BATT_CRT_VOLT`...) theo pack thật. `FENCE_TYPE` đặt 3 (độ cao tối đa + vòng tròn); chỉ bật bit đa giác (7) sau khi đã nạp đa giác, vì chưa có đa giác thì pre-arm báo "Polygon fence(s) invalid" (`AC_Fence.cpp:432-437`).

### 3.6 Bảo mật khi dùng

- **MAVLink mặc định không có xác thực**: ai gửi được gói UDP tới cổng 14550 (hoặc vào cùng WiFi Backpack) đều có thể ra lệnh cho drone. Bật MAVLink signing qua cáp USB trước buổi bay (ArduPilot 4.7.2 có hỗ trợ: `libraries/GCS_MAVLink/GCS_Signing.cpp`; cách bật trong Mission Planner **chưa kiểm**; ELRS Backpack có chuyển tiếp gói đã ký hay không **chưa kiểm**).
- **Tailscale/ZeroTier làm lộ luồng điều khiển cho mọi máy trong mạng lớp phủ.** Khuyên không bật khi bay; nếu dùng thì giới hạn bằng ACL của dịch vụ. Quy tắc tường lửa của bộ cài chỉ mở trên profile Private và chỉ mạng cục bộ; **không thêm profile Public vào quy tắc**.
- **Đổi mật khẩu WiFi của ELRS Backpack** khỏi mặc định.
- **Dùng tài khoản Windows thường khi bay**, không dùng tài khoản admin. `config.xml` của Mission Planner thuộc tài khoản dùng để bay (xem lưu ý ở mục 2).
- Xác nhận `ARMING_SKIPCHK = 0` trên FC (tên tham số có trong `libraries/AP_Arming/AP_Arming.cpp` của Copter-4.7.2, dòng 195-201).
- `C:\GCS` bị khóa quyền ghi cho Users vì các script admin đọc và chạy file ở đó (xem mục 2). Gói được chép vào `C:\GCS\packages\` rồi mới kiểm và chạy bản chép, nên đổi file trên USB sau khi chép không có tác dụng. Còn tồn tại: ai thay được cả gói lẫn `checksums.json` trên USB **trước** lúc chép thì chỉ bị chặn bởi chữ ký/`expectedPublisher` (nếu bạn đã điền) hoặc câu hỏi xác nhận; chính các file `.ps1` trên USB là mã chạy bằng admin nên vẫn phải giữ USB tin cậy. Public Desktop có thể cho tài khoản thường ghi (shortcut bị đổi đích): xem bảng tổng kết của Install.

## 4. Nối MP vào SITL để tập

Máy chạy SITL (WSL2 hoặc máy khác) gửi MAVLink tới IP laptop, UDP 14550 (hoặc 14551). Ví dụ từ MAVProxy trong SITL: `--out=udp:<IP-laptop>:14550`. Trong MP chọn **UDP**, cổng 14550, Connect. Quy tắc tường lửa chỉ mở cho mạng Private; mạng cục bộ phải được Windows xếp loại Private. Từ WSL2 tới Windows host có thể cần địa chỉ IP vEthernet của WSL, chưa kiểm chứng ở đây.

## 5. Hoàn tác

```powershell
powershell -ExecutionPolicy Bypass -File C:\GCS\tools\Uninstall-Gcs.ps1 -WhatIf
powershell -ExecutionPolicy Bypass -File C:\GCS\tools\Uninstall-Gcs.ps1               # nguồn, tường lửa, shortcut
powershell -ExecutionPolicy Bypass -File C:\GCS\tools\Uninstall-Gcs.ps1 -RemoveApps   # thêm: gỡ MP nếu chính Install cài
```

Giữ nguyên `C:\GCS`, dữ liệu MP. Driver, MAVProxy/QGC/... và config bị ghi đè chỉ được liệt kê hướng dẫn gỡ/khôi phục tay (bản cũ nằm ở `C:\GCS\backup\<ngày giờ>\overwritten`).

Uninstall chỉ tin `state.json` nằm trong `C:\GCS\backup\` và do Administrators/SYSTEM sở hữu, Users không ghi được; mọi giá trị đọc từ state (đường dẫn, tên quy tắc, GUID, mã MSI) bị kiểm phạm vi trước khi dùng, và chỉ xóa shortcut `.lnk` nằm trực tiếp trong Desktop của người dùng hoặc Public Desktop. Khôi phục xong không lỗi thì `state.json` được đổi tên thành `state.restored.json` (để lần Install sau chụp lại hiện trạng mới làm bản "gốc"). Muốn gỡ MP sau đó: `Uninstall-Gcs.ps1 -StatePath C:\GCS\backup\<ngày giờ>\state.restored.json -RemoveApps`; với `state.restored*.json` Uninstall **không** khôi phục nguồn/tường lửa lần hai (chỉ xử lý gỡ ứng dụng), để không ghi đè thay đổi của bạn sau lần khôi phục đầu.

## 6. Đã xác minh / chưa xác minh

| Thành phần | Trạng thái |
|---|---|
| URL MP MSI, MP ZIP (firmware.ardupilot.org) | Đã xác minh khi tra 2026-11-16; `-CheckOnly` kiểm lại (kết quả ở báo cáo) |
| `https://firmware.ardupilot.org/Tools/MAVProxy/MAVProxySetup-latest.exe` | HEAD trả 200, ~368,5 MB (2026-11-16, `-CheckOnly`); manifest dùng https; cờ im lặng chưa biết, cài tương tác |
| Trạng thái chữ ký số thật của từng gói (MP MSI, MAVProxy, QGC) | **Chưa kiểm** (chưa tải gói nào về để xem); Install dừng gói nếu chữ ký không hợp lệ, trừ khi `-AllowUnsigned` |
| ACL `C:\GCS` (`CreateDirectory` + `DirectorySecurity`) | **Chưa chạy thật trên máy đích** (tạo nguyên tử bằng tài khoản Administrators thật, đặt chủ sở hữu Administrators lúc tạo, chưa chạy lần nào; `icacls /setowner` vẫn dùng cho thư mục con/file). Đã thử trong `%TEMP%` bằng tài khoản thường: ACL và chủ sở hữu có ngay sau khi tạo (SID tham số hóa). Hàm kiểm (`Test-GcsTreeAcl`, `Test-GcsFileTrusted`, junction, ACE ghi của Users trên file con) đã thử trên cây thật trong `%TEMP%` của máy dev bằng tài khoản thường (`tests\Test-GcsLogic.ps1`); chưa thử với chủ sở hữu `Administrators` thật |
| QGC daily (cloudfront) | Đã xác minh có trong tài liệu QGC; là bản DAILY, không ổn định |
| winget `Tailscale.Tailscale` | Đã xác minh |
| winget `akeo.ie.Zadig`, `ZeroTier.ZeroTierOne` | CHƯA xác minh |
| `msiexec /qn` cho MP | CHƯA ai thử; có báo cáo treo vì hộp thoại driver; logic timeout + `/passive` chưa chạy thật |
| Chờ mutex `Global\_MSIExecute`, thử lại khi 1618, kết thúc msiexec client khi quá hạn (không còn dừng `msiserver`) | CHƯA kiểm chứng trên cài đặt thật. Logic giữ/chờ mutex đã kiểm bằng mutex thật tên `Local\...` giữ từ luồng khác (`Test-GcsMsiBusy`/`Wait-GcsMsiIdle` nhận tên mutex); tên `Global\_MSIExecute` thật và hành vi của Windows Installer chưa kiểm |
| Khôi phục quy tắc tường lửa có sẵn, `/setactive` có điều kiện, giá trị powercfg có áp dụng ngay khi scheme đã active hay không | CHƯA kiểm chứng trên máy đích |
| Tên khóa config.xml của MP | CHƯA xác minh, không tự tạo |
| Vị trí dữ liệu MP (`Documents\Mission Planner`, `C:\ProgramData\Mission Planner\gmapcache`) | Theo người dùng cung cấp, chưa kiểm trên máy có MP |
| Tên tham số trong `dtrack-failsafe.param` | Đã đối chiếu mã nguồn tag Copter-4.7.2; giá trị CHƯA bay thử |
| Driver CP210x/CH340/FTDI | Chưa có URL xác minh; chỉ cài `.inf` bạn tự chép vào `drivers\` |
| powercfg, tường lửa, shortcut, Test-Gcs | Mới kiểm cú pháp và `-WhatIf` trên máy khác; chưa chạy thật trên laptop sạch |
| Active Hours | Không tự đặt (không dùng khóa registry chưa chắc) |

### Chưa kiểm trên máy đích (liệt kê trung thực)

Tất cả những thứ dưới đây chỉ mới được đọc mã, kiểm cú pháp, chạy `-WhatIf` và chạy `tests\Test-GcsLogic.ps1` trên máy khác; **chưa có lần cài thật nào**:

- Toàn bộ `Install-Gcs.ps1` chạy thật bằng admin: tạo nguyên tử `C:\GCS` (`CreateDirectory` với chủ sở hữu Administrators: có thành công trong token admin đã nâng quyền hay không), nhánh "gốc đã có nhưng không đạt → dừng", kiểm lại cây ngay trước msiexec/bộ cài/`Expand-Archive`/`Test-Gcs.ps1`, chép gói vào `C:\GCS\packages`, xóa-rồi-chép file `tools`, kiểm chủ sở hữu thật (`Administrators` hay SID tài khoản tạo tùy chính sách "Default owner" của máy).
- `ShouldContinue` (hỏi xác nhận từng gói) trong phiên admin thật; hành vi khi chạy không tương tác.
- Chữ ký Authenticode thật của MSI Mission Planner, MAVProxy, QGC (chưa tải gói nào); vì vậy `expectedPublisher` đang để trống.
- `msiexec /qn` và `/passive` cho Mission Planner, hết hạn `-InteractiveTimeoutMinutes` (không kết thúc tiến trình).
- `powercfg /setactive` luôn gọi; giá trị có áp dụng ngay hay không; Modern Standby.
- Quy tắc tường lửa: ép quy tắc cùng tên về UDP 14550–14551 và khôi phục cấu hình cũ (protocol/localPort/direction/action) bằng `Set-NetFirewallRule`.
- File đánh dấu `.installed-by-gcs.json` qua chu trình Uninstall → Install → `-RemoveApps`.
- Chặn nạp `GcsLogic.ps1` khi ACL sai (đường `Test-BootstrapTrusted` trong Uninstall/Test-Gcs) trên cây `C:\GCS` thật.
- Thời gian kiểm ACL từng file trong `MissionPlanner` (hàng nghìn file sau khi giải nén ZIP).

## 7. Yêu cầu laptop đề xuất (ĐỀ XUẤT, không phải yêu cầu chính thức)

Windows 10 22H2 hoặc 11 x64; .NET Framework ≥ 4.7.2 (Windows 11 có sẵn); RAM ≥ 8 GB; ≥ 10 GB trống (bản đồ ngoại tuyến tốn thêm); WiFi 2,4 GHz; 1 cổng USB-A hoặc USB-C; pin dùng được ≥ 3 giờ; màn hình đọc được ngoài trời; không dùng ARM64.
