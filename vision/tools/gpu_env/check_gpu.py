"""Phep thu nho tren card: mang tich chap, 20 buoc tien-lui, anh ngau nhien 480x480 batch 16."""
import time
import torch
import torch.nn as nn


def run(device, steps=20):
    torch.manual_seed(0)
    net = nn.Sequential(
        nn.Conv2d(3, 32, 3, stride=2, padding=1), nn.BatchNorm2d(32), nn.SiLU(),
        nn.Conv2d(32, 64, 3, stride=2, padding=1), nn.BatchNorm2d(64), nn.SiLU(),
        nn.Conv2d(64, 128, 3, stride=2, padding=1), nn.BatchNorm2d(128), nn.SiLU(),
        nn.AdaptiveAvgPool2d(1), nn.Flatten(), nn.Linear(128, 10),
    ).to(device)
    opt = torch.optim.SGD(net.parameters(), lr=0.01)
    x = torch.randn(16, 3, 480, 480, device=device)
    y = torch.randint(0, 10, (16,), device=device)
    times, loss = [], None
    for _ in range(steps):
        t = time.perf_counter()
        opt.zero_grad()
        loss = nn.functional.cross_entropy(net(x), y)
        loss.backward()
        opt.step()
        if device == "cuda":
            torch.cuda.synchronize()
        times.append(time.perf_counter() - t)
    ok = bool(torch.isfinite(loss).item()) and all(torch.isfinite(p).all().item() for p in net.parameters())
    return times, float(loss.item()), ok


if __name__ == "__main__":
    print("torch", torch.__version__, "hip", torch.version.hip, "cuda_available", torch.cuda.is_available())
    modes = []
    if torch.cuda.is_available():
        print("device:", torch.cuda.get_device_name(0))
        modes += [("cuda (MIOpen bat)", "cuda", True), ("cuda (MIOpen tat)", "cuda", False)]
    modes.append(("cpu", "cpu", True))
    for label, d, miopen in modes:
        torch.backends.cudnn.enabled = miopen
        try:
            if d == "cuda":
                run(d, 3)  # khoi dong (nap kernel), khong tinh
            times, loss, ok = run(d)
        except RuntimeError as e:
            print(f"{label}: LOI {str(e)[:80]}")
            continue
        med = sorted(times)[len(times) // 2]
        print(f"{label}: trung vi {med*1000:.1f} ms/buoc, trung binh {sum(times)/len(times)*1000:.1f} ms, buoc dau {times[0]*1000:.1f} ms, loss {loss:.4f}, huu han={ok}")

