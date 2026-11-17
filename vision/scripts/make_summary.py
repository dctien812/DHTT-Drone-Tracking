"""Gop cac CSV trong results/ thanh results/SUMMARY.md (bang). Phan ket luan viet tay o results/conclusions.md se duoc chen len dau."""
import csv, os
R = '/mnt/d/Personal/Drone-Tracking/vision/results'


def rd(n):
    p = f'{R}/{n}'
    return list(csv.DictReader(open(p))) if os.path.exists(p) else []


def md(head, rows):
    return '\n'.join(['| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head)] + ['| ' + ' | '.join(map(str, r)) + ' |' for r in rows]) + '\n'


S = rd('summary_metrics.csv'); RB = rd('recall_by_width.csv'); WE = rd('width_error.csv'); DS = rd('dataset_stats.csv')
tags = list(dict.fromkeys(r['tag'] for r in S))
out = []
if os.path.exists(f'{R}/conclusions.md'):
    out.append(open(f'{R}/conclusions.md', encoding='utf-8').read() + '\n')
out.append('# Bang so lieu (tu dong sinh boi scripts/make_summary.py)\n')
out.append('## Tap cham (DUT Anti-UAV, split test; be rong muc tieu theo px)\n')
out.append(md(['split', 'co so px', 'so box', '<10', '10-20', '20-40', '>40', 'p10', 'p50', 'p90', 'kich thuoc anh pho bien'],
              [[r['split'], r['basis'], r['n_box'], r['<10'], r['10-20'], r['20-40'], r['>40'], r['p10'], r['p50'], r['p90'], r['img_sizes_top']] for r in DS]))
for conf in ('0.25', '0.1'):
    out.append(f'## Chi so tong (nguong tin cay {conf}; anh/GT test; CPU)\n')
    rows = [[r['tag'], r['mode'], r['imgsz'], r['n_img'], r['n_gt'], r['precision'], r['recall'], r['mAP50'], r['fp_per_100img'],
             f"{float(r['ms_pre']) + float(r['ms_inf']) + float(r['ms_post']):.1f}"]
            for r in S if r['conf'] == conf and not r['mode'].startswith('sweep')]
    out.append(md(['model', 'che do', 'imgsz', 'anh', 'GT', 'P', 'R', 'mAP50', 'FP/100 anh', 'ms/anh (pre+inf+post)'], rows))
out.append('## Recall theo nhom be rong (nguong 0.25). Co so "infer" = px sau khi dua ve imgsz; "native" = px goc\n')
for basis in ('infer', 'native'):
    rows = []
    for r in RB:
        if r['conf'] == '0.25' and r['width_basis'] == basis and not r['mode'].startswith('sweep'):
            rows.append([r['tag'], r['mode'], r['imgsz'], r['width_bin_px'], r['n_gt'], r['recall']])
    out.append(f'### co so {basis}\n')
    out.append(md(['model', 'che do', 'imgsz', 'nhom px', 'n GT', 'recall'], rows))
out.append('## Sai so be rong khung bao (phat hien dung, IoU>=0.5; nguong 0.25; px goc)\n')
out.append(md(['model', 'che do', 'imgsz', 'nhom px goc', 'n', 'trung vi |loi| px', 'p90 |loi| px', 'trung vi |loi| %', 'p90 |loi| %', 'lech co dau %'],
              [[r['tag'], r['mode'], r['imgsz'], r['width_bin_native_px'], r['n'], r['med_abs_px'], r['p90_abs_px'], r['med_abs_pct'], r['p90_abs_pct'], r['median_signed_pct']]
               for r in WE if r['conf'] == '0.25' and not r['mode'].startswith('sweep')]))
sw = [r for r in S if r['mode'].startswith('sweep') and r['conf'] == '0.25']
if sw:
    out.append('## Quet kich thuoc tong hop (thu nho anh de muc tieu rong tw px, dat tren khung 640x640 xam, nguong 0.25)\n')
    out.append('Recall (P / FP tren 100 anh) theo be rong muc tieu tw (px, o khung 640 goc truoc khi phong len imgsz).\n')
    tws = sorted({float(r['mode'][5:]) for r in sw})
    rows = []; mins = []
    for tag in tags:
        for sz in ('640', '1280'):
            cells = []; first90 = None
            for tw in tws:
                m = [r for r in sw if r['tag'] == tag and r['imgsz'] == sz and float(r['mode'][5:]) == tw]
                if m:
                    cells.append(f"{float(m[0]['recall']):.2f} ({m[0]['precision']}/{m[0]['fp_per_100img']})")
                    if first90 is None and float(m[0]['recall']) >= 0.9:
                        first90 = tw
                else:
                    cells.append('')
            if any(cells):
                rows.append([tag, sz] + cells); mins.append([tag, sz, '' if first90 is None else f'{first90:g}'])
    out.append(md(['model', 'imgsz'] + [f'{t:g}px' for t in tws], rows))
    # recall chi tinh muc tieu chinh (dong dau cua moi anh), bo cac GT phu bi thu nho theo
    rows = []; mins = []
    for tag in tags:
        for sz in ('640', '1280'):
            cells = []; first90 = None
            for tw in tws:
                fn = f'{R}/raw/{tag}_sweep{tw:g}_{sz}_lim900.csv'
                if not os.path.exists(fn):
                    cells.append(''); continue
                seen = set(); hit = n = 0
                for r in csv.DictReader(open(fn)):
                    if r['stem'] in seen:
                        continue
                    seen.add(r['stem']); n += 1; hit += float(r['conf_matched']) >= 0.25
                rec = hit / max(n, 1); cells.append(f'{rec:.2f} (n={n})')
                if first90 is None and rec >= 0.9:
                    first90 = tw
            if any(cells):
                rows.append([tag, sz] + cells); mins.append([tag, sz, '' if first90 is None else f'{first90:g}'])
    out.append('Recall chi cua muc tieu chinh (nguong 0.25):\n')
    out.append(md(['model', 'imgsz'] + [f'{t:g}px' for t in tws], rows))
    out.append('Be rong nho nhat co recall >= 0.90 (trong cac muc da quet; trong = khong dat o muc nao):\n')
    out.append(md(['model', 'imgsz', 'tw nho nhat (px)'], mins))
    out.append('## Sai so be rong theo tw (quet; px goc = px khung 640)\n')
    out.append(md(['model', 'imgsz', 'tw', 'n', 'trung vi |loi| px', 'p90 |loi| px', 'trung vi |loi| %', 'p90 |loi| %', 'lech co dau %'],
                  [[r['tag'], r['imgsz'], r['mode'][5:], r['n'], r['med_abs_px'], r['p90_abs_px'], r['med_abs_pct'], r['p90_abs_pct'], r['median_signed_pct']]
                   for r in WE if r['mode'].startswith('sweep') and r['conf'] == '0.25' and r['width_bin_native_px'] == 'all']))
open(f'{R}/SUMMARY.md', 'w', encoding='utf-8').write('\n'.join(out))
print('ok', len(out))
