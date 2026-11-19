"""In bang [goc | fin1 | fin2] tu RES/final/summary_*.csv. Dung: realvideo_final_table.py cach nguong [cfg...]"""
import csv
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from realvideo_common import *

method, thr = sys.argv[1], sys.argv[2]
cfgs = sys.argv[3:] or ["base", "fin1", "fin2"]
data = {}
for c in cfgs:
    p = "%s/final/summary_%s.csv" % (RES, c)
    if os.path.exists(p):
        for r in csv.DictReader(open(p)):
            if r["cach"] == method and r["nguong"] == thr:
                data.setdefault((r["chi_so"], r["nhom"]), {})[c] = r["gia_tri"]
for (m, g), v in data.items():
    print(m, g, " | ".join("%s=%s" % (c, v.get(c, "-")) for c in cfgs))
