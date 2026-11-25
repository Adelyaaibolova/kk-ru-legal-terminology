"""Adjudication sheet for the refined type scheme (lexical / derivational / inflectional-syntactic / paraphrase).

Usage: make_adjudication.py report_v2.xlsx key.json second_annotation.xlsx out.xlsx
For every real discrepancy, it shows both experts' labels (where a second label exists) and a
PROPOSED class: 'derivational' if a word of the defined term is missing but a Kazakh word in the
paragraph shares its root (first 3 letters), 'lexical' otherwise. The proposal is a
starting point only; the experts decide.
"""
import json
import re
import sys

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

rep, keyf, sec, out = sys.argv[1:5]
cases = [[c.value for c in r] for r in load_workbook(rep, data_only=True)["Случаи для экспертизы"].iter_rows(min_row=2)
         if r[0].value]
key = json.load(open(keyf, encoding="utf-8"))
s2 = {r[0]: r for r in load_workbook(sec, data_only=True)["Разметка"].iter_rows(min_row=2, values_only=True) if r[0]}
# map second-annotator labels to the report by (term, article, Russian paragraph)
second = {}
for sid, k in key.items():
    r = s2.get(sid)
    if r:
        second[(r[1], str(r[3]), (r[7] or "")[:600])] = (r[4], r[6])
KW = re.compile(r"[А-Яа-яЁёӘәҒғҚқҢңӨөҰұҮүҺһІі]+")
MAP = {"грамматическая вариация": "словоизменение / синтаксис", "перефразирование": "перефразирование"}


def propose(term_kk, kk_text, label1):
    if label1 in MAP:
        return MAP[label1]
    tw = [w.lower() for w in KW.findall(term_kk)]
    words = [w.lower() for w in KW.findall(kk_text or "")]
    for t in tw:
        if len(t) < 4 or any(w.startswith(t) for w in words):
            continue                      # this term word is present (possibly inflected)
        stem = t[:3]
        if any(w.startswith(stem) for w in words):
            return "словообразовательный вариант"   # same root, other derivation
    return "лексический вариант"


wb = Workbook()
ws = wb.active
ws.title = "Переразметка"
hdr = ["№", "Русский термин", "Казахский термин (из определения)", "Статья", "Метка эксперта 1", "Метка эксперта 2",
       "Комментарий эксперта 2", "Предложенный класс (авто)", "Итоговый класс (решают эксперты)", "Комментарий эксперта 1",
       "Русский текст пункта", "Казахский текст пункта"]
wid = [6, 26, 30, 8, 22, 22, 30, 26, 26, 30, 60, 60]
for i, (h, w) in enumerate(zip(hdr, wid), 1):
    c = ws.cell(row=1, column=i, value=h)
    c.font, c.fill = Font(name="Arial", bold=True, color="FFFFFF"), PatternFill("solid", fgColor="C0504D")
    c.alignment = Alignment(wrap_text=True)
    ws.column_dimensions[c.column_letter].width = w
n = 1
for r in cases:
    if not r[6] or r[6] == "ошибка автоматики":
        continue
    l2 = second.get((r[1], str(r[3]), (r[9] or "")[:600]), (None, None))
    vals = [n, r[1], r[2], r[3], r[6], l2[0], l2[1], propose(r[2], r[10], r[6]), None, r[8], r[9], r[10]]
    for j, v in enumerate(vals, 1):
        c = ws.cell(row=n + 1, column=j, value=v)
        c.font, c.alignment = Font(name="Arial"), Alignment(wrap_text=True, vertical="top")
    ws.cell(row=n + 1, column=9).fill = PatternFill("solid", fgColor="FFF2CC")
    n += 1
dv = DataValidation(type="list", formula1='"лексический вариант,словообразовательный вариант,словоизменение / синтаксис,перефразирование,не расхождение"')
ws.add_data_validation(dv)
dv.add(f"I2:I{n}")
ws.freeze_panes = "C2"
g = wb.create_sheet("Классы")
g.column_dimensions["A"].width = 110
for i, t in enumerate([
    "Лексический вариант — другой корень: қалдықтарды басқару → қалдықтарды игеру; бастапқы → алғашқы; қызметтер → жағдайлар.",
    "Словообразовательный вариант — тот же корень, другое образование: шығарынды (результат) → шығарылу / шығару (действие); "
    "төгінді → төгу / төгілу; жинақтау → жинақталу.",
    "Словоизменение / синтаксис — тот же термин в другой форме или конструкции: падеж вместо прилагательного, опущенное ету и т. п.",
    "Перефразирование — термин заменён описанием или глагольной конструкцией.",
    "Не расхождение — при переразметке выяснилось, что расхождения нет.",
], 1):
    g.cell(row=i, column=1, value=t).font = Font(name="Arial")
    g.cell(row=i, column=1).alignment = Alignment(wrap_text=True)
wb.save(out)
print("cases:", n - 1)
