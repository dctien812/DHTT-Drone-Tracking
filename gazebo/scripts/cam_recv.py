#!/usr/bin/env python3
"""Receive H.264/RTP on UDP 5600 via GStreamer appsink -> numpy. usage: cam_recv.py <secs> <outdir> <tag>"""
import sys, time, os
import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst
import numpy as np, cv2
secs = float(sys.argv[1]); outdir = sys.argv[2]; tag = sys.argv[3]
Gst.init(None)
p = Gst.parse_launch(
 'udpsrc port=5600 caps="application/x-rtp, media=(string)video, clock-rate=(int)90000, encoding-name=(string)H264" '
 '! rtph264depay ! avdec_h264 ! videoconvert ! video/x-raw,format=BGR ! appsink name=s emit-signals=true sync=false max-buffers=2 drop=true')
s = p.get_by_name("s")
frames = []; shape = [None]; saved = [0]
t_start = time.time()
def on_sample(sink):
    smp = sink.emit("pull-sample"); buf = smp.get_buffer()
    c = smp.get_caps().get_structure(0)
    w, h = c.get_value("width"), c.get_value("height"); shape[0] = (w, h)
    ok, mi = buf.map(Gst.MapFlags.READ)
    img = np.frombuffer(mi.data, np.uint8).reshape(h, w, 3).copy(); buf.unmap(mi)
    now = time.time(); frames.append(now)
    if saved[0] < 3 and now - t_start > 3 + saved[0] * 4:
        cv2.imwrite(os.path.join(outdir, f"{tag}_{saved[0]}.png"), cv2.resize(img, (w // 2, h // 2)),
                    [cv2.IMWRITE_PNG_COMPRESSION, 9])
        saved[0] += 1
    return Gst.FlowReturn.OK
s.connect("new-sample", on_sample)
p.set_state(Gst.State.PLAYING)
time.sleep(secs)
p.set_state(Gst.State.NULL)
n = len(frames)
if n > 1:
    span = frames[-1] - frames[0]
    print(f"CAM {tag}: resolution={shape[0]} frames={n} first_frame_after={frames[0]-t_start:.1f}s fps={(n-1)/span:.2f} (span {span:.1f}s) png_saved={saved[0]}")
else:
    print(f"CAM {tag}: frames={n} (no stream)")