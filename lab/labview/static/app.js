"use strict";
const $ = (id) => document.getElementById(id);

async function post(url, body) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r.json();
}

function say(t) { $("msg").textContent = t; }

$("view").addEventListener("click", async (ev) => {
  const rc = ev.target.getBoundingClientRect();
  const x = (ev.clientX - rc.left) / rc.width;
  const y = (ev.clientY - rc.top) / rc.height;
  try {
    const j = await post("/api/lock", { x: Math.min(1, Math.max(0, x)), y: Math.min(1, Math.max(0, y)) });
    say(j.ok ? "Đã khóa ID " + j.track_id : "Không có khung nào tại điểm bấm");
  } catch (e) { say("Lỗi: " + e.message); }
});

$("btn-lock").addEventListener("click", async () => {
  try {
    const j = await post("/api/lock", { best: true });
    say(j.ok ? "Đã khóa ID " + j.track_id : "Chưa có vật thể nào để khóa");
  } catch (e) { say("Lỗi: " + e.message); }
});

$("btn-release").addEventListener("click", async () => {
  try {
    const j = await post("/api/release", {});
    say(j.released ? "Đã hủy khóa" : "Đang không khóa");
  } catch (e) { say("Lỗi: " + e.message); }
});

function render(s) {
  $("perf").textContent = s.running
    ? `${s.fps} fps · xử lý ${s.infer_ms} ms · trễ ${s.latency_ms} ms · CPU ${s.cpu_percent}% · ${s.source.width}x${s.source.height}`
    : (s.ended ? "Hết nguồn hình" : "Đang chờ khung hình...");
  const n = $("notice");
  n.hidden = !s.notice;
  n.textContent = s.notice ? "Đã tự bỏ khóa: mất mục tiêu" : "";
  const lb = $("lockbox"), L = s.lock;
  if (!L.active) {
    lb.className = "idle";
    lb.textContent = "Chưa khóa\nĐang thấy " + s.tracks.length + " vật thể";
  } else if (!L.visible) {
    lb.className = "lost";
    lb.textContent = `Đang khóa ID ${L.track_id}\nĐANG TÌM LẠI ${L.lost_for_s} s (hết hạn sẽ tự bỏ khóa)\nĐã gán lại: ${L.reacquired} lần`;
  } else {
    lb.className = "on";
    const dist = L.distance_m == null ? "n/a" : L.distance_m + " m";
    const st = L.state === "reacquired" ? "ĐÃ GÁN LẠI" : "BÁM";
    lb.textContent =
      `ĐANG KHÓA ID ${L.track_id}  (tin cậy ${L.conf})\n` +
      `Trạng thái: ${st} · đã gán lại ${L.reacquired} lần\n` +
      `Lệch ngang: ${L.yaw_deg > 0 ? "+" : ""}${L.yaw_deg}° (+ = phải)\n` +
      `Lệch dọc: ${L.pitch_deg > 0 ? "+" : ""}${L.pitch_deg}° (+ = lên)\n` +
      `Khoảng cách ước lượng: ${dist}\n` +
      `(giả định mục tiêu rộng ${L.assumed_width_m} m)\n` +
      `Đã khóa ${L.since_s} s`;
  }
  const ul = $("events");
  ul.textContent = "";
  for (const e of s.events.slice().reverse()) {
    const li = document.createElement("li");
    li.textContent = e.ts.slice(11, 23) + "  " + e.msg;
    ul.appendChild(li);
  }
}

async function poll() {
  try {
    const r = await fetch("/api/state");
    if (r.ok) render(await r.json());
  } catch (e) { /* mạng gián đoạn, thử lại */ }
  setTimeout(poll, 250);
}
poll();
