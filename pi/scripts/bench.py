import sys, time, csv, json, os, glob, argparse, statistics, subprocess
import cv2, psutil, numpy as np
from ultralytics import YOLO

def vc(*a):
    try: return subprocess.check_output(["vcgencmd", *a], text=True).strip()
    except Exception as e: return "err"

def temp(): 
    t = vc("measure_temp"); return float(t.split("=")[1].replace("'C","")) if "=" in t else -1
def freq(): 
    try: return int(open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq").read())//1000
    except Exception: return -1

import threading, re
def rdint(ps):
    try: return int(open(ps[0]).read().strip())
    except Exception: return 0
class Mon(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True); self.stop=False; self.vmin=9.0; self.fmin=99999; self.tmax=0; self.flags=0; self.fan=0; self.fstate=0
    def run(self):
        while not self.stop:
            s = vc("pmic_read_adc")
            mm = re.search(r"EXT5V_V volt\(\d+\)=([\d.]+)V", s)
            if mm: self.vmin = min(self.vmin, float(mm.group(1)))
            self.fmin = min(self.fmin, freq()); self.tmax = max(self.tmax, temp())
            self.fan = max(self.fan, rdint(glob.glob("/sys/devices/platform/cooling_fan/hwmon/*/fan1_input")))
            self.fstate = max(self.fstate, rdint(["/sys/class/thermal/cooling_device0/cur_state"]))
            g = vc("get_throttled")
            try: self.flags |= int(g.split("=")[1], 16) & 0xF
            except Exception: pass
            time.sleep(1)

def load(model):
    return YOLO(model, task="detect")

def run_video(m, path, imgsz, maxf, save=None):
    cap = cv2.VideoCapture(path); inf=[]; e2e=[]; det=0; n=0
    try: m.predictor.trackers[0].reset()
    except Exception: pass
    while n < maxf:
        t0 = time.perf_counter(); ok, fr = cap.read()
        if not ok: break
        r = m.track(fr, persist=True, tracker="bytetrack.yaml", imgsz=imgsz, conf=0.25, verbose=False, device="cpu")[0]
        e2e.append((time.perf_counter()-t0)*1000); inf.append(r.speed["inference"])
        nd = 0 if r.boxes is None else len(r.boxes); det += nd>0; n += 1
        if save and n == save[0]:
            cv2.imwrite(save[1], r.plot())
    cap.release(); return inf, e2e, det, n

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model"); ap.add_argument("--fmt"); ap.add_argument("--imgsz", type=int)
    ap.add_argument("--videos", default="~/dtrack/videos"); ap.add_argument("--maxf", type=int, default=150)
    ap.add_argument("--out", default="~/dtrack/results/bench.csv"); ap.add_argument("--save", default="")
    a = ap.parse_args()
    vids = sorted(glob.glob(os.path.expanduser(a.videos)+"/*.mp4"))
    m = load(os.path.expanduser(a.model))
    # warm-up
    cap = cv2.VideoCapture(vids[0]); _, fr = cap.read()
    for _ in range(5): m.track(fr, persist=False, imgsz=a.imgsz, verbose=False, device="cpu")
    mon = Mon(); mon.start()
    p =psutil.Process(); p.cpu_percent(None); c0 = p.cpu_times(); w0 = time.perf_counter()
    I=[];E=[];D=0;N=0;rss=0; t_start=temp()
    for i, v in enumerate(vids):
        sv = (30, os.path.expanduser(a.save)) if (a.save and i == 0) else None
        inf, e2e, det, n = run_video(m, v, a.imgsz, a.maxf, sv)
        I+=inf; E+=e2e; D+=det; N+=n; rss=max(rss, p.memory_info().rss)
    mon.stop=True; wall = time.perf_counter()-w0; c1 = p.cpu_times()
    cpu = (c1.user-c0.user + c1.system-c0.system)/wall*100
    row = dict(fmt=a.fmt, imgsz=a.imgsz, threads=__import__("torch").get_num_threads(), frames=N,
        inf_med=round(statistics.median(I),1), inf_p95=round(float(np.percentile(I,95)),1),
        e2e_med=round(statistics.median(E),1), e2e_p95=round(float(np.percentile(E,95)),1),
        fps_e2e=round(N/wall,2), cpu_pct=round(cpu), rss_mb=round(rss/1e6), det_rate=round(D/N,4),
        temp_start=t_start, temp_max=mon.tmax, ext5v_min=mon.vmin, freq_min=mon.fmin, now_flags=hex(mon.flags), fan_rpm_max=mon.fan, fan_state_max=mon.fstate, throttled_sticky=vc("get_throttled").split("=")[1])
    out = os.path.expanduser(a.out); os.makedirs(os.path.dirname(out), exist_ok=True)
    new = not os.path.exists(out)
    with open(out, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row)); 
        if new: w.writeheader()
        w.writerow(row)
    print(json.dumps(row))
main()