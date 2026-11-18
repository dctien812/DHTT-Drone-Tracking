@echo off
rem Mo man hinh lab chay tren Raspberry Pi (camera Pi that) qua duong ham SSH: bam dup file nay.
rem Dong cua so nay (hoac Ctrl+C) de tat ca labview tren Pi lan duong ham. Trang: http://localhost:8080/
rem Trang tren Pi chi nghe 127.0.0.1 cua Pi (khong --allow-network); PC vao qua ssh -L 8080:127.0.0.1:8080.
rem Duong dan ben Pi viet tuong doi voi thu muc nha (khong dung ~ hay $ de wsl khong bien doi).
title Man hinh lab tren Pi - dong cua so nay de tat
echo Dang khoi dong labview tren Pi (mat khoang 15 giay), trinh duyet se tu mo...
start "" /min cmd /c "timeout /t 15 /nobreak >nul & start http://localhost:8080/"
wsl -d Ubuntu-24.04 -- ssh -t -i /home/drone/.ssh/id_pi_lab -o IdentitiesOnly=yes -o BatchMode=yes -o ExitOnForwardFailure=yes -o ServerAliveInterval=15 -L 8080:127.0.0.1:8080 dctien812@192.168.1.91 "cd dtrack/lab && exec dtrack/venv/bin/python -m labview --source picamera2 --port 8080 --weights /home/dctien812/dtrack/models/ft_v8n_480_ncnn_model --imgsz 480 --threads 3"
echo.
echo Man hinh lab tren Pi da dung.
pause
