# Chia du lieu V2 (theo nhom) va kiem ro ri

## dut: 10000 anh, 1645 nhom (nguong 0.9), nhom lon nhat [110, 110, 135, 172, 3333]
so anh: train=7771, val=729, test=1500, drop=0; so nhom: train=1059, val=140, test=446, drop=0
  ro ri (ti le anh test co anh train gan trung): n_test=1500, corr95=0.0000, corr90=0.0000, corr85=0.3573, dhash6=0.1107, maxcorr_median=0.8039

## detfly: 7635 anh, 66 nhom (nguong 0.95), nhom lon nhat [398, 465, 977, 1098, 2024]
so anh: train=5200, val=342, test=1501, drop=592; so nhom: train=16, val=7, test=19, drop=39
  Det-Fly train: thu muc 010: 1708, thu muc 020: 3492
  Det-Fly val: thu muc 010: 0, thu muc 020: 342
  Det-Fly test: thu muc 010: 544, thu muc 020: 957
  khung train gan nhat (cung thu muc) cua anh test: trung vi 134, nho nhat 11, so anh test cach <=5 khung: 0
  ro ri (ti le anh test co anh train gan trung): n_test=1501, corr95=0.0000, corr90=0.0027, corr85=0.1392, dhash6=0.0346, maxcorr_median=0.4184

## Doi chung: chia goc cua tac gia DUT (cung phep do): n_test=2200, corr95=0.6759, corr90=0.7295, corr85=0.7736, dhash6=0.6832, maxcorr_median=0.9995
