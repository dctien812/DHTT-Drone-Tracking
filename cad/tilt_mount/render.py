"""Ve hinh xem nhanh (PNG) cua cum lap o 0 va +50 do, bang matplotlib (khong can man hinh)."""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import tilt_mount as T

COL = {"base": (0.6, 0.6, 0.68), "bracket": (1.0, 0.55, 0.1), "spacer": (0.9, 0.9, 0.2),
       "servo": (0.25, 0.35, 0.85), "horn": (0.95, 0.95, 0.95), "camera": (0.1, 0.65, 0.2),
       "lens": (0.08, 0.08, 0.08), "cable": (0.85, 0.2, 0.2)}
MOVING = ("bracket", "horn", "camera", "lens", "cable")


def mesh(shape):
    v, t = shape.val().tessellate(0.05, 0.2)
    v = np.array([(p.x, p.y, p.z) for p in v])
    return v, np.array(t)


def draw(ang, view, fname, cut_wall2):
    P, D = T.parts(), T.dummies()
    fig = plt.figure(figsize=(8, 6))
    ax = fig.add_subplot(111, projection="3d", proj_type="persp")
    light = np.array([0.4, -0.5, 0.8]); light /= np.linalg.norm(light)
    allv = []
    for k, wp in {**P, **D}.items():
        shp = T.rot_x(wp, ang) if k in MOVING else wp
        v, t = mesh(shp)
        tri = v[t]
        if cut_wall2 and k in ("base", "spacer"):
            keep = tri[:, :, 0].min(axis=1) < T.X_W2 - 0.1 if k == "base" else np.zeros(len(tri), bool)
            tri = tri[keep]
        n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
        sh = 0.45 + 0.55 * np.abs(n @ light)
        c = np.array(COL[k])[None, :] * sh[:, None]
        pc = Poly3DCollection(tri, facecolors=c, edgecolors="none")
        ax.add_collection3d(pc)
        allv.append(v)
    allv = np.vstack(allv)
    mn, mx = allv.min(0), allv.max(0)
    ax.set_xlim(mn[0], mx[0]); ax.set_ylim(mn[1], mx[1]); ax.set_zlim(mn[2], mx[2])
    ax.set_box_aspect(mx - mn)
    ax.view_init(elev=view[0], azim=view[1])
    ax.set_xlabel("X (truc quay)"); ax.set_ylabel("Y (huong nhin)"); ax.set_zlabel("Z")
    ax.set_title(f"goc gat {ang:+.0f} do")
    fig.savefig(os.path.join(T.OUT, fname), dpi=110)
    plt.close(fig)


if __name__ == "__main__":
    for ang in (0.0, 50.0):
        tag = f"{int(ang):+d}".replace("+", "p").replace("-", "m")
        draw(ang, (0, 90), f"view_front_{tag}.png", False)    # nhin tu +Y (chinh dien, thay lens)
        draw(ang, (0, 0), f"view_side_{tag}.png", True)       # nhin tu +X, bo vach xa (thay goc gat)
        draw(ang, (25, -50), f"view_persp_{tag}.png", False)  # phoi canh
    print("ok")
