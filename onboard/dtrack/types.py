"""Hop dong du lieu dung chung giua cac module cua phan mem bam (dtrack).

Quy uoc:
- He the gioi: NED (x Bac, y Dong, z Xuong), met, goc tai diem home cua EKF.
- He than: FRD (x mui theo quy uoc ArduCopter, y phai, z xuong).
- He camera: x phai anh, y xuong anh, z theo truc quang (huong nhin).
- Anh: goc toa do o goc tren-trai, don vi pixel cua khung day du (do phan giai goc).
- Thoi gian: giay (float), cung mot dong ho don dieu cho moi module.
- Goc: radian. Quaternion: (w, x, y, z), quay vector tu he than sang he the gioi.

File nay chi chua kieu du lieu, khong chua logic. Doi kieu o day la doi hop dong:
phai cap nhat moi module dung no.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

Vec3 = Tuple[float, float, float]
Quat = Tuple[float, float, float, float]
Mat3 = Tuple[Vec3, Vec3, Vec3]


@dataclass(frozen=True)
class CameraModel:
    """Camera lo kim. Mac dinh: IMX296 1456x1088, pixel 3.45 um."""
    width: int = 1456
    height: int = 1088
    fx: float = 2319.0          # px; lens 8 mm / 3.45 um
    fy: float = 2319.0
    cx: float = 728.0
    cy: float = 544.0
    # Ma tran quay vector tu he camera sang he than (cot = truc camera trong he than).
    # Mac dinh: camera nhin theo mui (z_cam = x_than), x_cam = y_than, y_cam = z_than.
    R_body_cam: Mat3 = ((0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))


@dataclass(frozen=True)
class Detection:
    """Mot ket qua phat hien trong khung day du."""
    t_capture: float            # thoi diem phoi sang
    cx: float                   # tam bbox, px
    cy: float
    w: float                    # kich thuoc bbox, px
    h: float
    conf: float                 # 0..1


@dataclass(frozen=True)
class OwnState:
    """Trang thai cua drone bam, lay tu FC."""
    t: float
    pos_ned: Vec3               # m
    vel_ned: Vec3               # m/s
    q_world_body: Quat
    armed: bool = False
    mode: str = ""


class TrackStatus(Enum):
    SEARCH = "search"           # chua co muc tieu
    TRACK = "track"             # dang co do moi
    COAST = "coast"             # mat do, dang du doan
    LOST = "lost"               # mat qua lau


@dataclass(frozen=True)
class TrackState:
    """Dau ra cua khoi nhan biet (tracker + uoc luong khoang cach)."""
    t: float
    status: TrackStatus
    los_ned: Optional[Vec3] = None        # vector don vi tu drone bam toi muc tieu
    los_rate_ned: Optional[Vec3] = None   # rad/s, toc do quay duong ngam
    range_m: Optional[float] = None       # khoang cach uoc luong
    range_sigma_m: Optional[float] = None  # do bat dinh 1-sigma
    range_rate_mps: Optional[float] = None  # duong = dang xa ra
    # False khi khoang cach khong dang tin (bbox cham mep anh, chua hoi tu, dau vao hong).
    # Khoi dan duong KHONG duoc tien lai gan muc tieu khi range_valid = False.
    range_valid: bool = False
    # Tam du doan cho khung ke (de crop). Co the nam NGOAI khung: noi dung phai tu kep.
    predicted_px: Optional[Tuple[float, float]] = None
    age_s: float = 0.0                    # tinh tu t_capture cua lan do cuoi (da gom do tre)


@dataclass(frozen=True)
class GuidanceCommand:
    """Lenh gui cho FC o che do GUIDED (van toc NED + huong mui)."""
    t: float
    vel_ned: Vec3               # m/s
    yaw_rad: Optional[float] = None
    valid: bool = True          # False = supervisor phai giu vi tri / thoat
    reason: str = ""
