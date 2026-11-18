import sys, time, csv, os, glob, argparse, subprocess, re
import cv2, numpy as np
from ultralytics import YOLO
def vc(*a):
    try: return subprocess.check_output(["vcgencmd", *a], text=True).strip()
    except Exception: return "err"
def rd(p):
    try: return open(p).read().strip()
    except Exception: return ""
ap = argparse.ArgumentParser()
ap.add_argument("--model"); ap.add_argument("--imgsz", type=int); ap.add_argument("--secs", type=int, default=1800)
ap.add_argument("--out", default=os.path.expanduser("~/dtrack/results/soak.csv"))
a = ap.parse_args()
m = YOLO(os.path.expanduser(a.model), task="detect")
vids = sorted(glob.glob(os.path.expanduser("~/dtrack/videos/*.mp4")))
f = open(a.out, "w", newline=""); w = csv.writer(f)
w.writerow(["t_s","temp_c","freq_mhz","throttled","ext5v","win_fps","win_e2e_med_ms","win_e2e_p95_ms","win_e2e_max_ms","cpu_load1"])
t0 = time.time(); tw = t0; lat = []; n = 0; vi = 0
while time.time() - t0 < a.secs:
    cap = cv2.VideoCapture(vids[vi % len(vids)]); vi += 1
    try: m.predictor.trackers[0].reset()
    except Exception: pass
    while time.time() - t0 < a.secs:
        s = time.perf_counter(); ok, fr = cap.read()
        if not ok: break
        m.track(fr, persist=True, tracker="bytetrack.yaml", imgsz=a.imgsz, conf=0.25, verbose=False, device="cpu")
        lat.append((time.perf_counter()-s)*1000); n += 1
        if time.time() - tw >= 30:
            now = time.time(); mm = re.search(r"EXT5V_V volt\(\d+\)=([\d.]+)V", vc("pmic_read_adc"))
            w.writerow([round(now-t0), vc("measure_temp").split("=")[1].replace("'C",""), int(rd("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq") or 0)//1000,
                vc("get_throttled").split("=")[1], mm.group(1) if mm else "", round(n/(now-tw),2), round(float(np.median(lat)),1),
                round(float(np.percentile(lat,95)),1), round(max(lat),1), rd("/proc/loadavg").split()[0]]); f.flush()
            tw = now; lat = []; n = 0
    cap.release()
f.close(); print("SOAK_DONE")