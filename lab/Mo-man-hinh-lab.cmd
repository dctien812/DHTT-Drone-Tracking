@echo off
rem Mo man hinh lab: bam dup file nay. Dong cua so nay (hoac Ctrl+C) de tat.
rem Trang chi mo duoc tu chinh may nay: http://localhost:8080/
rem Muon dung video khac: keo tha file video vao file .cmd nay khong duoc (duong dan Windows);
rem thay vao do sua bien VIDEO ben duoi thanh duong dan kieu /mnt/d/...
title Man hinh lab - dong cua so nay de tat
set VIDEO=
echo Dang khoi dong man hinh lab (mat khoang 10 giay de nap model)...
start "" /min cmd /c "timeout /t 10 /nobreak >nul & start http://localhost:8080/"
wsl -d Ubuntu-24.04 -- bash /mnt/d/Personal/Drone-Tracking/lab/run_demo.sh %VIDEO%
echo.
echo Man hinh lab da dung.
pause
