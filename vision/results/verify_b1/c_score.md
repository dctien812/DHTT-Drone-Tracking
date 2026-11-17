# Cham nhan tay vs ft_v8n (ca khung 640x512, 1 khung/lan, khong tracker)

Nhan do chinh toi gan bang mat tren anh nen; sai so vai px, muc tieu 5-30 px. "chac"=sure 1.

| tap | conf | n khung | recall (khung drone co >=1 det khop) | CI95 Wilson | precision det (det khop/tong det tren khung drone+none) | CI95 | khung drone co det khong khop |
|---|---|---|---|---|---|---|---|
| tat ca | 0.25 | 99 drone (+1 none) | 88/99 = 88.9% | 81.2-93.7% | 89/92 = 96.7% | 90.8-98.9% | 1 |
| tat ca | 0.5 | 99 drone (+1 none) | 81/99 = 81.8% | 73.1-88.2% | 81/81 = 100.0% | 95.5-100.0% | 0 |
| chac (sure=1) | 0.25 | 65 drone (+0 none) | 64/65 = 98.5% | 91.8-99.7% | 64/65 = 98.5% | 91.8-99.7% | 0 |
| chac (sure=1) | 0.5 | 65 drone (+0 none) | 63/65 = 96.9% | 89.5-99.2% | 63/63 = 100.0% | 94.3-100.0% | 0 |

| may bay | conf | khung may bay bi goi drone | CI95 |
|---|---|---|---|
| 20 khung | 0.25 | 20/20 = 100.0% | 83.9-100.0% |
| 20 khung | 0.5 | 19/20 = 95.0% | 76.4-99.1% |

So khung khong chac (sure=0): 35/120 (drone: 35)

## Chi tiet khung drone bi bo sot hoac det sai (conf 0.25)
| video | khung | chac | nhan (x1,y1,x2,y2) | det conf>=0.25 |
|---|---|---|---|---|
| V_DRONE_005 | 254 | 0 | [('250', '438', '264', '447')] | [] |
| V_DRONE_033 | 138 | 0 | [('494', '311', '510', '319')] | [] |
| V_DRONE_039 | 193 | 0 | [('367', '257', '376', '265')] | [] |
| V_DRONE_046 | 285 | 1 | [('396', '279', '408', '290')] | [] |
| V_DRONE_069 | 169 | 0 | [('236', '156', '243', '163')] | [] |
| V_DRONE_069 | 266 | 0 | [('357', '242', '367', '252')] | [] |
| V_DRONE_111 | 193 | 0 | [('259', '433', '267', '441')] | [(413, 213, 441, 237, np.float32(0.27))] |
| V_DRONE_112 | 220 | 0 | [('257', '347', '265', '355')] | [] |
| V_DRONE_112 | 290 | 0 | [('237', '346', '245', '354')] | [] |
| V_DRONE_114 | 104 | 0 | [('225', '314', '233', '322')] | [] |
| V_DRONE_114 | 149 | 0 | [('224', '312', '232', '320')] | [] |
