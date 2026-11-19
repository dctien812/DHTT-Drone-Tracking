@echo off
rem Mo man hinh lab chay tren Raspberry Pi (camera Pi that) qua duong ham SSH: bam dup file nay.
rem Dong cua so nay (hoac Ctrl+C) de tat ca labview tren Pi lan duong ham. Trang: http://localhost:8080/
rem Trang tren Pi chi nghe 127.0.0.1 cua Pi (khong --allow-network); PC vao qua ssh -L 8080:127.0.0.1:8080.
rem Duong dan ben Pi (venv, models) viet tuong doi voi ~/dtrack/lab sau lenh cd. Khoa -i ~/.ssh/... la ben WSL cua PC.
rem Ten dang nhap va dia chi Pi: lay tu bien moi truong PI_USER, PI_HOST hoac doc pi\pi.env (khong dua len git).
if not defined PI_USER if exist "%~dp0..\pi\pi.env" for /f "usebackq tokens=1,* delims==" %%a in (`findstr /b "PI_USER= PI_HOST=" "%~dp0..\pi\pi.env"`) do set "%%a=%%b"
if not defined PI_USER echo Loi: thieu PI_USER/PI_HOST. Tao pi\pi.env tu pi\pi.env.example hoac dat bien moi truong. & pause & exit /b 1
if not defined PI_HOST echo Loi: thieu PI_HOST (bien moi truong hoac pi\pi.env). & pause & exit /b 1
title Man hinh lab tren Pi - dong cua so nay de tat
echo Dang khoi dong labview tren Pi (mat khoang 15 giay), trinh duyet se tu mo...
start "" /min cmd /c "timeout /t 15 /nobreak >nul & start http://localhost:8080/"
wsl -d Ubuntu-24.04 -- ssh -t -i ~/.ssh/id_pi_lab -o IdentitiesOnly=yes -o BatchMode=yes -o ExitOnForwardFailure=yes -o ServerAliveInterval=15 -L 8080:127.0.0.1:8080 %PI_USER%@%PI_HOST% "cd dtrack/lab && exec ../venv/bin/python -m labview --source picamera2 --port 8080 --weights ../models/ft_v8n_480_ncnn_model --imgsz 480 --threads 3"
echo.
echo Man hinh lab tren Pi da dung.
pause
