#!/usr/bin/env python3
"""Bang TINH kha thi theo toc do (KHONG mo phong): khoang cach giu an toan, kich thuoc muc tieu trong anh, FOV.
Tai lap: python simtools/feasibility_table.py [--out docs/feasibility_speed.md]   (chay tu onboard/)

d = v*tau + v^2/(2*a_chaser) - v^2/(2*a_target) + 2*sigma_r(d) + margin,  sigma_r(r) = r^2 * sigma_px / (f * S)
(sigma_r tinh tai chinh r = d nen d la nghiem cua 2*k*d^2 - d + A = 0, k = sigma_px/(f*S), A = ve con lai; lay nghiem nho;
 vo nghiem khi 8*k*A > 1: sigma_r tang nhanh hon d, khong khoang cach nao du).
"""
import argparse
import math
import os

TAU_S = 0.35            # tre thuan cua FC trong SITL: 0.31-0.40 s (out/20261117_054730_fcstep)
A_CHASER = 4.1          # m/s^2, gia toc phanh TB cua chaser trong SITL (2.1-4.2): SO CUA SITL, KHONG PHAI MAY THAT
MARGIN_M = 8.0
TARGET_M = 0.30         # m, kich thuoc muc tieu
PIX_UM = 3.45
W_PX, H_PX = 1456, 1088
THRESH_PX = 20.0        # nguong nhan dien on dinh (buoc nhan dien V1)
SPEEDS = [10, 20, 30, 50, 70, 90, 111]
LENSES_MM = [6, 8, 12, 16, 25]
TARGET_BRAKES = [("a_t=4", 4.0), ("a_t=8", 8.0), ("dung tuc thi", None)]
# So do B4 (khop gat, SITL, bo phat hien tong hop sigma_size = 1 px): (khoang cach giu m, RMS sai so uoc luong m), fx = 1739 px
B4_RMS = [(15.0, 0.20), (25.0, 0.39), (40.0, 1.15)]     # R40 ghi 1.1-1.2 -> lay 1.15
B4_FX = 1739.0


def f_px(lens_mm):
    return lens_mm / (PIX_UM * 1e-3)


def sigma_px_b4():
    """sigma_px hieu dung = RMS * f * S / r^2, trung binh 3 diem B4 (da qua bo loc)."""
    vals = [rms * B4_FX * TARGET_M / (r * r) for r, rms in B4_RMS]
    return sum(vals) / len(vals), vals


def a_term(v, a_t):
    return v * TAU_S + v * v / (2 * A_CHASER) - (0.0 if a_t is None else v * v / (2 * a_t)) + MARGIN_M


def d_safe(v, a_t, sigma_px, f):
    """Khoang cach giu an toan (m) hoac None neu vo nghiem."""
    A = a_term(v, a_t)
    k = sigma_px / (f * TARGET_M)
    disc = 1.0 - 8.0 * k * A
    if disc < 0:
        return None
    return A if k == 0 else (1.0 - math.sqrt(disc)) / (4.0 * k)


def sigma_r(d, sigma_px, f):
    return d * d * sigma_px / (f * TARGET_M)


def width_px(d, f):
    return f * TARGET_M / d


def fov_deg(lens_mm):
    return (2 * math.degrees(math.atan(W_PX * PIX_UM * 1e-3 / (2 * lens_mm))),
            2 * math.degrees(math.atan(H_PX * PIX_UM * 1e-3 / (2 * lens_mm))))


def reach_m(lens_mm):
    """Khoang cach xa nhat con >= THRESH_PX."""
    return f_px(lens_mm) * TARGET_M / THRESH_PX


def vmax_for_lens(lens_mm, a_t, sigma_px):
    """Toc do cao nhat (m/s, chia doi) ma d_safe <= reach cua lens (d tang theo v)."""
    f, lim = f_px(lens_mm), reach_m(lens_mm)
    lo, hi = 0.0, 300.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        d = d_safe(mid, a_t, sigma_px, f)
        if d is not None and d <= lim:
            lo = mid
        else:
            hi = mid
    return lo


def fmt(x, nd=1):
    return "vo nghiem" if x is None else ("%.*f" % (nd, x))


def build():
    sp, sp_list = sigma_px_b4()
    f6 = f_px(6)
    L = []
    L.append("# Bang kha thi theo toc do (CHI TINH, khong mo phong)\n")
    L.append("Tao bang `python simtools/feasibility_table.py` (tu `onboard/`). Cong thuc va gia dinh:\n")
    L.append("- `d = v*tau + v^2/(2*a_chaser) - v^2/(2*a_target) + 2*sigma_r(d) + 8 m`; cot \"dung tuc thi\" bo so hang tru. "
             "`sigma_r(r) = r^2*sigma_px/(f*S)` tinh tai chinh `r = d` (giai phuong trinh bac hai, lay nghiem nho; \"vo nghiem\" = sigma_r tang nhanh hon d).")
    L.append("- `tau = %.2f s` (tre thuan FC, SITL do 0.31-0.40 s), `a_chaser = %.1f m/s^2` (gia toc phanh TB cua chaser trong SITL do 2.1-4.2, "
             "`out/20261117_054730_fcstep`). **Day la so cua SITL (quad freestyle 0.8 kg), KHONG phai may that**; chi do o toc do <= 10 m/s, "
             "ngoai suy toi 111 m/s la gia dinh chua kiem." % (TAU_S, A_CHASER))
    L.append("- `sigma_px` hieu dung = **%.2f px**: lay tu so do B4 (khop gat, SITL): RMS sai so uoc luong khoang cach sau bo loc "
             "%s m tai r = %s m, quy ra `sigma_px = RMS*f*S/r^2` voi f = %.0f px, S = %.2f m -> %s, lay trung binh. "
             "Bo phat hien cua B4 la TONG HOP (nhieu kich thuoc 1 px moi canh); bo nhan dien that chua do trong vong kin. "
             "Tham khao V1 (nhan dien tren anh, `vision/`): sai so be rong khung bao nhom 20-40 px trung vi 5.5%%, phan vi 90 = 19%% "
             "(lon hon nhieu so voi mo hinh tong hop), nen cot 'do nhay' ben duoi dung sigma_px = 1.0 px (khong loc) lam can tren." % (
                 sp, "/".join("%.2f" % r for _, r in B4_RMS), "/".join("%g" % r for r, _ in B4_RMS), B4_FX, TARGET_M,
                 "/".join("%.2f" % v for v in sp_list)))
    L.append("- Bang 1 tinh sigma_r theo lens 6 mm (f = %.0f px, lens da do B4); cac bang anh/bang 3 dung sigma_r theo dung f cua tung lens "
             "(lens dai -> sigma_r nho hon). Cam bien %dx%d, diem anh %.2f um (%.2f x %.2f mm); muc tieu %.2f m; nguong nhan dien %d px.\n" % (
                 f6, W_PX, H_PX, PIX_UM, W_PX * PIX_UM / 1000, H_PX * PIX_UM / 1000, TARGET_M, THRESH_PX))
    L.append("## Bang 1: khoang cach giu an toan (m), lens 6 mm\n")
    L.append("| v (m/s) | km/h | d, a_t=4 | d, a_t=8 | d, muc tieu dung tuc thi | sigma_r (a_t=8) | d, a_t=8 voi sigma_px=1.0 (can tren) |")
    L.append("|---|---|---|---|---|---|---|")
    D = {}   # (v, label, lens) -> d
    for v in SPEEDS:
        row = [str(v), "%.0f" % (v * 3.6)]
        for lab, a_t in TARGET_BRAKES:
            d = d_safe(v, a_t, sp, f6)
            row.append(fmt(d))
        d8 = d_safe(v, 8.0, sp, f6)
        row.append("-" if d8 is None else "%.2f" % sigma_r(d8, sp, f6))
        row.append(fmt(d_safe(v, 8.0, 1.0, f6)))
        L.append("| " + " | ".join(row) + " |")
    L.append("\n## Bang 2: FOV ngang x doc va tam xa nhat con >= %d px\n" % THRESH_PX)
    L.append("| lens (mm) | f (px) | FOV ngang x doc (do) | khoang cach xa nhat >= %d px (m) |" % THRESH_PX)
    L.append("|---|---|---|---|")
    for lm in LENSES_MM:
        h, w = fov_deg(lm)
        L.append("| %d | %.0f | %.1f x %.1f | %.1f |" % (lm, f_px(lm), h, w, reach_m(lm)))
    L.append("\n## Bang 3: be rong muc tieu %.2f m trong anh (px) tai khoang cach an toan; dau V = >= %d px, X = duoi nguong\n" % (TARGET_M, THRESH_PX))
    for lab, a_t in TARGET_BRAKES:
        L.append("### Muc tieu phanh: %s%s\n" % (lab, " m/s^2" if a_t else ""))
        L.append("| v (m/s) | km/h | " + " | ".join("lens %d mm (d m / px)" % lm for lm in LENSES_MM) + " |")
        L.append("|---|---|" + "---|" * len(LENSES_MM))
        for v in SPEEDS:
            cells = []
            for lm in LENSES_MM:
                f = f_px(lm)
                d = d_safe(v, a_t, sp, f)
                if d is None:
                    cells.append("vo nghiem")
                else:
                    px = width_px(d, f)
                    cells.append("%.1f / %.1f %s" % (d, px, "V" if px >= THRESH_PX else "X"))
            L.append("| %d | %.0f | %s |" % (v, v * 3.6, " | ".join(cells)))
        L.append("")
    L.append("## Bang 4: toc do cao nhat ma khoang cach an toan con trong tam >= %d px\n" % THRESH_PX)
    L.append("| lens (mm) | tam xa nhat (m) | " + " | ".join("%s: m/s (km/h)" % lab for lab, _ in TARGET_BRAKES) + " |")
    L.append("|---|---|" + "---|" * len(TARGET_BRAKES))
    for lm in LENSES_MM:
        cells = []
        for lab, a_t in TARGET_BRAKES:
            vm = vmax_for_lens(lm, a_t, sp)
            cells.append("%.1f (%.0f)" % (vm, vm * 3.6))
        L.append("| %d | %.1f | %s |" % (lm, reach_m(lm), " | ".join(cells)))
    L.append("\nGhi chu: ket qua la can tren ly thuyet theo mo hinh don gian (phanh deu, tre thuan co dinh, sigma_r dai dien cho sai so uoc luong khoang cach); "
             "khong xet nghieng than, FOV doc/ngang khi mat hinh, quang sai, rung camera, nhieu cua bo nhan dien that, gioi han v_max_mps = 30 cua cau hinh hien tai "
             "(`dtrack/config.py`), hay kha nang chaser tang toc duoi 111 m/s.")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "feasibility_speed.md"))
    a = ap.parse_args()
    text = build()
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(text)
    print("da ghi %s (%d dong)" % (a.out, text.count("\n")))


if __name__ == "__main__":
    main()
