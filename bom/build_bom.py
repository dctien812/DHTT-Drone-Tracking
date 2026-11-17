#!/usr/bin/env python3
"""Doc bom_data.json -> Drone-Tracking-BOM.xlsx (openpyxl). Chay: python build_bom.py

Them gia Taobao: trong bom_data.json, o dong linh kien (rows[]) them cac truong
  "price_cny": 2136.8                      (so, gia that doc tu trang san pham, CNY)
  "taobao_url": "https://item.taobao.com/item.htm?id=..."   (link bam duoc)
  "taobao_note": "..."                     (tuy chon, hien thanh ghi chu o o gia: shop, ngay, cau hinh)
Dong khong co cac truong nay thi hai cot P, Q de trong. Cot P/Q khong nam trong cong thuc tong.
Khong dien gia "tu" cua tin gop (chua dung cau hinh).
"""
import json
import os

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "bom_data.json")
OUT = os.path.join(HERE, "Drone-Tracking-BOM.xlsx")

OV = "Tổng quan"
OVQ = "'%s'" % OV
CELL_VND = OVQ + "!$B$5"
CELL_EUR = OVQ + "!$B$6"
CELL_GBP = OVQ + "!$B$7"
RATE_CELL = {"EUR": CELL_EUR, "GBP": CELL_GBP}

STATUSES = ["Đã có", "Mua ngay", "Chờ mô phỏng", "Tùy chọn", "Kiểm tra trước khi mua"]
STATUS_FILL = {
    "Đã có": "D9D9D9",
    "Mua ngay": "C6EFCE",
    "Chờ mô phỏng": "FFEB9C",
    "Tùy chọn": "BDD7EE",
    "Kiểm tra trước khi mua": "F8CBAD",
}
CONF = ["Đã mở trang", "Từ kết quả tìm kiếm"]

HEADERS = ["STT", "Nhóm", "Linh kiện", "Model", "Thông số chính", "SL",
           "Đơn giá thấp (USD)", "Đơn giá cao (USD)", "Thành tiền thấp (USD)",
           "Thành tiền cao (USD)", "Thành tiền cao (VND)", "Trạng thái",
           "Độ tin cậy", "Link", "Ghi chú", "Giá Taobao (CNY)", "Link Taobao"]
WIDTHS = [5, 14, 26, 30, 36, 5, 11, 11, 13, 13, 16, 16, 15, 42, 44, 14, 40]
NCOL = len(HEADERS)
LASTCOL = get_column_letter(NCOL)

HDR_FILL = PatternFill("solid", fgColor="1F4E78")
HDR_FONT = Font(bold=True, color="FFFFFF")
TOT_FILL = PatternFill("solid", fgColor="F2F2F2")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")
USD_FMT = "#,##0.00"
VND_FMT = "#,##0"


def q(name):
    return "'%s'" % name


def page_setup(ws, title_rows="1:1"):
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_title_rows = title_rows


def header_row(ws, row, headers):
    for c, h in enumerate(headers, 1):
        cell = ws.cell(row=row, column=c, value=h)
        cell.fill, cell.font, cell.border = HDR_FILL, HDR_FONT, BORDER
        cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")


def build_item_sheet(wb, sh):
    ws = wb.create_sheet(sh["name"])
    header_row(ws, 1, HEADERS)
    ws.row_dimensions[1].height = 32
    for i, w in enumerate(WIDTHS, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    rows = sh["rows"]
    for n, r in enumerate(rows, 1):
        x = n + 1
        cur = r.get("orig_currency")
        note = r.get("note", "")
        no_price = r["low"] is None and r["high"] is None and not cur
        if no_price and r["status"] != "Đã có" and "chưa tra" not in note.lower():
            note = (note + ". " if note else "") + "Chưa tra được giá"
        if cur:
            g = "=%s*%s" % (r["orig_low"], RATE_CELL[cur])
            h = "=%s*%s" % (r["orig_high"], RATE_CELL[cur])
        else:
            g, h = r["low"], r["high"]  # None -> o trong that
        vals = [n, r["group"], r["item"], r["model"], r["specs"], r["qty"], g, h,
                '=IF(OR(F%d="",G%d=""),"",F%d*G%d)' % (x, x, x, x),
                '=IF(OR(F%d="",H%d=""),"",F%d*H%d)' % (x, x, x, x),
                '=IF(J%d="","",J%d*%s)' % (x, x, CELL_VND),
                r["status"], r["conf"], r["link"] or None, note or None,
                r.get("price_cny"), r.get("taobao_url") or None]
        for c, v in enumerate(vals, 1):
            cell = ws.cell(row=x, column=c, value=v)
            cell.border, cell.alignment = BORDER, WRAP
            if c == 16:
                cell.number_format = "#,##0.0"
            elif c in (7, 8, 9, 10):
                cell.number_format = USD_FMT
            elif c == 11:
                cell.number_format = VND_FMT
            elif c == 6:
                cell.number_format = "0"
        if r["link"]:
            lc = ws.cell(row=x, column=14)
            lc.hyperlink = r["link"]
            lc.font = Font(color="0563C1", underline="single")
        if r.get("taobao_url"):
            tc = ws.cell(row=x, column=17)
            tc.hyperlink = r["taobao_url"]
            tc.font = Font(color="0563C1", underline="single")
        if r.get("taobao_note") and r.get("price_cny") is not None:
            ws.cell(row=x, column=16).comment = Comment(r["taobao_note"], "BOM")
    last = len(rows) + 1
    # dong tong
    t1, t2 = last + 1, last + 2
    for t, label in ((t1, "Tổng dòng 'Mua ngay'"), (t2, "Tổng mọi dòng (gồm Tùy chọn/ứng viên)")):
        for c in range(1, NCOL + 1):
            cell = ws.cell(row=t, column=c)
            cell.fill, cell.border, cell.font = TOT_FILL, BORDER, Font(bold=True)
        ws.cell(row=t, column=3, value=label)
        for col in "IJK":
            rng = "%s2:%s%d" % (col, col, last)
            f = ('=SUMIFS(%s,L2:L%d,"Mua ngay")' % (rng, last)) if t == t1 else "=SUM(%s)" % rng
            cell = ws["%s%d" % (col, t)]
            cell.value = f
            cell.number_format = VND_FMT if col == "K" else USD_FMT
    ws["O%d" % t1] = '="Dòng chưa có giá (trừ Đã có): "&COUNTIFS(L2:L%d,"<>Đã có",G2:G%d,"")' % (last, last)
    ws["O%d" % t1].alignment = WRAP
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = "A1:%s%d" % (LASTCOL, last)
    dv = DataValidation(type="list", formula1='"%s"' % ",".join(STATUSES), allow_blank=True)
    dv.add("L2:L%d" % last)
    ws.add_data_validation(dv)
    dv2 = DataValidation(type="list", formula1='"%s"' % ",".join(CONF), allow_blank=True,
                         showErrorMessage=False)
    dv2.add("M2:M%d" % last)
    ws.add_data_validation(dv2)
    for st, color in STATUS_FILL.items():
        ws.conditional_formatting.add(
            "A2:%s%d" % (LASTCOL, last),
            FormulaRule(formula=['$L2="%s"' % st], fill=PatternFill("solid", bgColor=color, fgColor=color)))
    page_setup(ws)
    return last


def build_risk_sheet(wb, risks):
    ws = wb.create_sheet("Rủi ro")
    header_row(ws, 1, ["STT", "Vấn đề", "Chi tiết", "Việc cần làm"])
    for i, w in enumerate([5, 34, 70, 55], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    for n, r in enumerate(risks, 1):
        for c, v in enumerate([n, r["issue"], r["detail"], r["action"]], 1):
            cell = ws.cell(row=n + 1, column=c, value=v)
            cell.border, cell.alignment = BORDER, WRAP
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = "A1:D%d" % (len(risks) + 1)
    page_setup(ws)


def build_overview(wb, data, lasts):
    ws = wb.active
    ws.title = OV
    meta = data["meta"]
    bold = Font(bold=True)
    ws["A1"] = "Danh sách linh kiện cần mua - Drone quad 8 inch bay bám"
    ws["A1"].font = Font(bold=True, size=16)
    ws["A2"] = "Ngày tra giá"
    ws["B2"] = meta["price_date"]
    ws["A2"].font = bold
    ws["A4"] = "Tỷ giá (ô vàng: tự nhập)"
    ws["A4"].font = bold
    rates = [
        (5, "USD → VND", meta["usd_vnd"], VND_FMT, "Giả định, hãy sửa theo tỷ giá thực."),
        (6, "EUR → USD", meta["eur_usd"], "0.0000", "Giả định, hãy sửa theo tỷ giá thực. Dùng cho dòng giá gốc EUR."),
        (7, "GBP → USD", meta["gbp_usd"], "0.0000", "Giả định, hãy sửa theo tỷ giá thực. Hiện chưa dòng nào dùng (giá £ của Sequre chỉ ghi trong Ghi chú)."),
    ]
    for r, lab, val, fmt, note in rates:
        ws.cell(row=r, column=1, value=lab).font = bold
        c = ws.cell(row=r, column=2, value=val)
        c.number_format = fmt
        c.fill = PatternFill("solid", fgColor="FFFF00")
        c.border = BORDER
        ws.cell(row=r, column=3, value=note)

    ws["A9"] = "Tổng tiền (USD, và VND theo tỷ giá ở trên). Đơn giá chưa gồm vận chuyển và thuế."
    ws["A9"].font = bold
    groups = [("Mua ngay", ["thấp USD", "cao USD", "thấp VND", "cao VND"]),
              ("Chờ mô phỏng", ["thấp USD", "cao USD", "cao VND"]),
              ("Tùy chọn", ["thấp USD", "cao USD", "cao VND"]),
              ("Kiểm tra trước khi mua", ["thấp USD", "cao USD", "cao VND"])]
    hdr = ["Sheet"]
    for g, cols in groups:
        hdr += ["%s - %s" % (g, c) for c in cols]
    hdr.append("Số dòng chưa có giá (trừ Đã có)")
    header_row(ws, 10, hdr)
    ws.row_dimensions[10].height = 60
    names = [s["name"] for s in data["sheets"]]
    first = 11
    for k, name in enumerate(names):
        r = first + k
        last = lasts[name]
        S = q(name)
        ws.cell(row=r, column=1, value=name)
        col = 2
        for g, cols in groups:
            for cname in cols:
                src = "I" if "thấp" in cname else "J"
                f = '=SUMIFS(%s!$%s$2:$%s$%d,%s!$L$2:$L$%d,"%s")' % (S, src, src, last, S, last, g)
                if "VND" in cname:
                    f = "=%s*%s" % (f[1:], CELL_VND)
                ws.cell(row=r, column=col, value=f).number_format = VND_FMT if "VND" in cname else USD_FMT
                col += 1
        ws.cell(row=r, column=col,
                value='=COUNTIFS(%s!$L$2:$L$%d,"<>Đã có",%s!$G$2:$G$%d,"")' % (S, last, S, last))
    tr = first + len(names)
    ws.cell(row=tr, column=1, value="Tổng cộng")
    for col in range(2, len(hdr) + 1):
        L = get_column_letter(col)
        c = ws.cell(row=tr, column=col, value="=SUM(%s%d:%s%d)" % (L, first, L, tr - 1))
        c.number_format = USD_FMT if "USD" in hdr[col - 1] else VND_FMT
    for r in range(first, tr + 1):
        for col in range(1, len(hdr) + 1):
            c = ws.cell(row=r, column=col)
            c.border = BORDER
            c.alignment = Alignment(wrap_text=True, vertical="top")
            if r == tr:
                c.font, c.fill = bold, TOT_FILL
    ws.cell(row=tr + 1, column=1,
            value="Lưu ý: 'Chờ mô phỏng' ở sheet Động lực cộng TẤT CẢ ứng viên (motor/ESC/pin), không phải một cấu hình hoàn chỉnh nên bị cộng thừa; "
                  "'Tùy chọn' ở GCS cộng cả ba máy Windows trong khi chỉ mua MỘT. Chỉ cột 'Mua ngay' là số cần chi ngay.")
    ws.merge_cells(start_row=tr + 1, start_column=1, end_row=tr + 1, end_column=10)
    ws.cell(row=tr + 1, column=1).alignment = WRAP
    ws.row_dimensions[tr + 1].height = 48

    r = tr + 3
    ws.cell(row=r, column=1, value="Chú giải trạng thái").font = bold
    legend = [("Đã có", "Đã sở hữu, không cần mua."),
              ("Mua ngay", "Chắc chắn cần cho dự án, có thể mua ngay (vẫn kiểm lại giá lúc đặt)."),
              ("Chờ mô phỏng", "Chưa mua cho tới khi có kết quả mô phỏng (động lực, cảm biến dòng)."),
              ("Tùy chọn", "Phương án dự phòng hoặc lựa chọn thay thế."),
              ("Kiểm tra trước khi mua", "Còn thiếu thông tin hoặc chưa chọn model; kiểm tra rồi mới quyết định.")]
    for k, (st, desc) in enumerate(legend, 1):
        a = ws.cell(row=r + k, column=1, value=st)
        a.fill = PatternFill("solid", fgColor=STATUS_FILL[st])
        a.border = BORDER
        ws.cell(row=r + k, column=2, value=desc)
    r = r + len(legend) + 2
    ws.cell(row=r, column=1, value="Chú giải độ tin cậy").font = bold
    ws.cell(row=r + 1, column=1, value="Đã mở trang")
    ws.cell(row=r + 1, column=2, value="Giá/thông số lấy từ trang sản phẩm hoặc tài liệu đã mở trực tiếp.")
    ws.cell(row=r + 2, column=1, value="Từ kết quả tìm kiếm")
    ws.cell(row=r + 2, column=2, value="Chỉ thấy trong kết quả tìm kiếm, chưa mở trang để xác nhận.")
    ws.cell(row=r + 3, column=1, value="—")
    ws.cell(row=r + 3, column=2, value="Chưa có nguồn (chưa tra hoặc đã có sẵn).")
    ws.cell(row=r + 4, column=1, value="Giá Taobao (CNY)")
    ws.cell(row=r + 4, column=2, value="Chỉ dòng đã đọc giá thật từ trang sản phẩm Taobao (đơn vị CNY, chưa quy đổi, không nằm trong các tổng USD/VND). Ô trống = chưa có giá Taobao. Chưa dùng tỷ giá CNY nào.")
    r = r + 5
    ws.cell(row=r, column=1, value="Lưu ý quan trọng (từ sheet Rủi ro, mục 1-5)").font = bold
    for k, rk in enumerate(data["risks"][:5], 1):
        cell = ws.cell(row=r + k, column=1, value="%d. %s: %s -> %s" % (k, rk["issue"], rk["detail"], rk["action"]))
        ws.merge_cells(start_row=r + k, start_column=1, end_row=r + k, end_column=10)
        cell.alignment = WRAP
        ws.row_dimensions[r + k].height = 34

    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 14
    for col in range(3, len(hdr) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 14
    ws.freeze_panes = "A4"
    page_setup(ws, "1:1")


def main():
    with open(DATA, encoding="utf-8") as f:
        data = json.load(f)
    wb = Workbook()
    lasts = {}
    # Tong quan can biet dong cuoi tung sheet -> tinh truoc, tao sau roi dua len dau
    for sh in data["sheets"]:
        lasts[sh["name"]] = len(sh["rows"]) + 1
    build_overview(wb, data, lasts)
    for sh in data["sheets"]:
        build_item_sheet(wb, sh)
    build_risk_sheet(wb, data["risks"])
    wb.save(OUT)
    print("Da ghi", OUT)


if __name__ == "__main__":
    main()
