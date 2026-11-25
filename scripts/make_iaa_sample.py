"""Draw a blind, stratified sample of the expert-annotated cases for a second annotator.

Usage: make_iaa_sample.py annotated_report.xlsx sample.xlsx key.json [n=60] [seed=2026]
The sample hides the first annotator's labels; key.json keeps them for agreement_kappa.py.
"""
import json
import random
import sys
from collections import defaultdict

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

src, out, keyf = sys.argv[1:4]
n = int(sys.argv[4]) if len(sys.argv) > 4 else 60
rnd = random.Random(int(sys.argv[5]) if len(sys.argv) > 5 else 2026)
ws = load_workbook(src, data_only=True)["Случаи для экспертизы"]
rows = [[c.value for c in r] for r in ws.iter_rows(min_row=2) if r[0].value]
by = defaultdict(list)
for r in rows:
    by[r[6]].append(r)
# proportional allocation with at least 5 cases per class
alloc = {k: max(5, round(n * len(v) / len(rows))) for k, v in by.items()}
while sum(alloc.values()) > n:
    alloc[max(alloc, key=alloc.get)] -= 1
sample = [r for k, v in by.items() for r in rnd.sample(v, min(alloc[k], len(v)))]
rnd.shuffle(sample)

F = "Arial"
wb = Workbook()
s = wb.active
s.title = "Разметка"
hdr = ["ID", "Русский термин", "Казахский термин (из определения)", "Статья", "Тип расхождения",
       "Правовое значение", "Комментарий", "Русский текст пункта", "Казахский текст пункта"]
widths = [8, 28, 30, 9, 24, 14, 34, 70, 70]
for i, (h, w) in enumerate(zip(hdr, widths), 1):
    c = s.cell(row=1, column=i, value=h)
    c.font = Font(name=F, bold=True, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor="C0504D")
    s.column_dimensions[c.column_letter].width = w
key = {}
for i, r in enumerate(sample, 2):
    cid = f"S{i - 1:03d}"
    key[cid] = {"orig_no": r[0], "type": r[6], "legal": r[7]}
    for j, v in enumerate([cid, r[1], r[2], r[3], None, None, None, r[9], r[10]], 1):
        c = s.cell(row=i, column=j, value=v)
        c.font, c.alignment = Font(name=F), Alignment(wrap_text=True, vertical="top")
    for j in (5, 6, 7):
        s.cell(row=i, column=j).fill = PatternFill("solid", fgColor="FFF2CC")
last = len(sample) + 1
dv1 = DataValidation(type="list", formula1='"терминологический вариант,грамматическая вариация,перефразирование,ошибка автоматики"')
dv2 = DataValidation(type="list", formula1='"да,нет,неясно"')
s.add_data_validation(dv1); s.add_data_validation(dv2)
dv1.add(f"E2:E{last}"); dv2.add(f"F2:F{last}")
s.freeze_panes = "B2"
g = wb.create_sheet("Инструкция")
g.column_dimensions["A"].width = 110
for i, t in enumerate([
    "Для каждой строки: в русском пункте встречается определённый термин; автоматическая проверка не нашла в казахском пункте термин из определения.",
    "Тип расхождения: терминологический вариант — другое слово или термин; грамматическая вариация — тот же термин в другой форме "
    "(падеж, число, конструкция); перефразирование — смысл передан описательно или глагольно; ошибка автоматики — расхождения нет "
    "(термин на месте, другой смысл слова, сбой выравнивания).",
    "Правовое значение: может ли расхождение повлиять на толкование нормы — да / нет / неясно.",
    "Размечайте независимо, не глядя в первую разметку и не обсуждая случаи с первым экспертом.",
], 1):
    g.cell(row=i, column=1, value=t).font = Font(name=F)
    g.cell(row=i, column=1).alignment = Alignment(wrap_text=True)
wb.save(out)
json.dump(key, open(keyf, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("sample:", len(sample), {k: min(alloc[k], len(v)) for k, v in by.items()})
