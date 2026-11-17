#!/usr/bin/env python3
"""Arm + takeoff in GUIDED via pymavlink. usage: fly.py [alt_m] [hold_s]"""
import sys, time
from pymavlink import mavutil
alt = float(sys.argv[1]) if len(sys.argv) > 1 else 10
hold = float(sys.argv[2]) if len(sys.argv) > 2 else 20
m = mavutil.mavlink_connection("tcp:127.0.0.1:5760")
t0 = time.time()
m.wait_heartbeat(timeout=60)
print(f"heartbeat sys={m.target_system} after {time.time()-t0:.1f}s", flush=True)
m.mav.request_data_stream_send(m.target_system, m.target_component, mavutil.mavlink.MAV_DATA_STREAM_ALL, 10, 1)
armed = False
def set_guided():
    m.mav.command_long_send(m.target_system, m.target_component, 176, 0, 1, 4, 0, 0, 0, 0, 0)
    for _ in range(10):
        hb = m.recv_match(type="HEARTBEAT", blocking=True, timeout=2)
        if hb and hb.custom_mode == 4:
            return True
    return False
def is_armed():
    hb = m.recv_match(type="HEARTBEAT", blocking=True, timeout=3)
    return bool(hb and hb.base_mode & 128), (hb.custom_mode if hb else None)
t0 = time.time(); seen = set()
while time.time() - t0 < 150 and not armed:
    g = set_guided()
    m.mav.command_long_send(m.target_system, m.target_component, 400, 0, 1, 0, 0, 0, 0, 0, 0)
    time.sleep(2)
    while True:
        st = m.recv_match(type=["STATUSTEXT", "COMMAND_ACK"], blocking=False)
        if not st: break
        s = st.text if st.get_type() == "STATUSTEXT" else f"ACK cmd={st.command} res={st.result}"
        if s not in seen:
            seen.add(s); print(f"  [{time.time()-t0:5.1f}s] {s}", flush=True)
    armed, mode = is_armed()
    if armed and mode != 4:
        armed = False  # armed but not GUIDED: set again
print(f"armed={armed} guided={g} after {time.time()-t0:.1f}s", flush=True)
if not armed:
    sys.exit(2)
m.mav.command_long_send(m.target_system, m.target_component, 22, 0, 0, 0, 0, 0, 0, 0, alt)
ack = m.recv_match(type="COMMAND_ACK", blocking=True, timeout=5)
print("takeoff ack:", ack, flush=True)
hb = m.recv_match(type="HEARTBEAT", blocking=True, timeout=3)
print("armed flag:", bool(hb.base_mode & 128), "mode", hb.custom_mode, flush=True)
for _ in range(50):
    st = m.recv_match(type="STATUSTEXT", blocking=False)
    if not st: break
    print("STATUSTEXT:", st.text, flush=True)
t0 = time.time(); maxalt = 0; reached = None
while time.time() - t0 < hold:
    msg = m.recv_match(type="LOCAL_POSITION_NED", blocking=True, timeout=2)
    if msg:
        a = -msg.z; maxalt = max(maxalt, a)
        if reached is None and a >= alt * 0.95:
            reached = time.time() - t0
print(f"max_alt={maxalt:.2f}m target={alt} reached95%_after={reached}", flush=True)