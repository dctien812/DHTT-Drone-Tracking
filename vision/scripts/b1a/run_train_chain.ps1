# Chay lan luot 3 luot huan luyen, moi luot mot tien trinh Python, log rieng. Chay tach roi bang Start-Process.
$py = "D:\Personal\Drone-Tracking\vision\.venv-gpu\Scripts\python.exe"
$sc = "D:\Personal\Drone-Tracking\vision\scripts\b1a\run_train.py"
$out = "D:\Personal\Drone-Tracking\vision\results\b1a\train"
New-Item -ItemType Directory -Force $out | Out-Null
foreach ($f in @("EE", "DD", "final")) {
    & $py $sc $f *> "$out\log_$f.txt"
}
& $py $sc collect *> "$out\log_collect.txt"
Set-Content "$out\CHAIN_DONE" (Get-Date -Format s)
