"""Step 4. Write the results into an Excel workbook for expert (legal) review."""
import json
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

results = json.load(open(sys.argv[1], encoding="utf-8"))
out = sys.argv[2]
# expert labels from an annotated copy of an earlier report (optional): carried over by
# (term, article, Russian paragraph)
labels = {}
if len(sys.argv) > 4:
    from openpyxl import load_workbook
    _ws = load_workbook(sys.argv[4], data_only=True)["Случаи для экспертизы"]
    for _r in _ws.iter_rows(min_row=2, values_only=True):
        if _r[0]:
            labels[(_r[1], str(_r[3]), (_r[9] or "")[:600])] = (_r[6], _r[7], _r[8])
results = [r for r in results if r["ru_occurrences"]]

F = "Arial"
H = Font(name=F, bold=True, color="FFFFFF")
HFILL = PatternFill("solid", fgColor="C0504D")
IN = PatternFill("solid", fgColor="FFF2CC")
B = Font(name=F, bold=True)
N = Font(name=F)
WRAP = Alignment(wrap_text=True, vertical="top")


def header(ws, row, names, widths):
    for i, (n, w) in enumerate(zip(names, widths), 1):
        c = ws.cell(row=row, column=i, value=n)
        c.font, c.fill, c.alignment = H, HFILL, Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[get_column_letter(i)].width = w


wb = Workbook()

# ---------------- 1. About ----------------
ws = wb.active
ws.title = "О проекте"
ws.column_dimensions["A"].width = 110
lines = [
    ("Терминологическая (не)последовательность в казахской и русской версиях Экологического кодекса РК", B),
    ("Пилотное корпусное исследование. Кодекс РК от 2 января 2021 года № 400-VI ЗРК, редакция с изменениями по 2026 г.", N),
    ("", N),
    ("Метод", B),
    ("1. Корпус: русский и казахский тексты кодекса (426 статей), выровненные по статьям и пунктам; сноски и примечания ИЗПИ удалены.", N),
    ("2. Термины: определения вида «Под X понимается…» / «X деп … түсініледі» извлечены автоматически и проверены вручную.", N),
    ("3. Для каждого вхождения русского термина проверено, использован ли в соответствующем казахском пункте термин из определения "
     "(с учётом падежей, множественного числа и вставленных определений).", N),
    ("4. Случаи, где казахский термин из определения не найден, вынесены на лист «Случаи для экспертизы».", N),
    ("", N),
    ("Листы", B),
    ("«Термины» — сводка по 146 терминам: сколько раз встречается русский термин и сколько раз в казахском тексте использован термин из определения.", N),
    ("«Случаи для экспертизы» — все расхождения с русским и казахским текстом пункта. Жёлтые столбцы заполняет эксперт.", N),
    ("«Основные находки» — предварительные выводы для статьи.", N),
    ("", N),
    ("Как заполнять «Случаи для экспертизы» (жёлтые столбцы)", B),
    ("Тип расхождения — выбрать из списка: терминологический вариант / грамматическая вариация / перефразирование / ошибка автоматики.", N),
    ("Правовое значение — да / нет / неясно: может ли расхождение повлиять на толкование нормы.", N),
    ("Пример: «Қалдықтарды игеру ұлттық орталығы» вместо «қалдықтарды басқару» → терминологический вариант; правовое значение: неясно; "
     "комментарий: название органа расходится с определением в ст. 319.", N),
    ("", N),
    ("Статусы автоматической проверки", B),
    ("exact — термин из определения найден (с любыми окончаниями); dispersed — найден, но между словами вставлены другие слова; "
     "coordinated — термин разделён перечислением («қалдықтарды жинаудың, …, кәдеге жаратудың»); restructured — казахский пункт "
     "начинается с перечня, термин стоит в основной части после него. Всё это считается согласованным употреблением.", N),
    ("alignment — казахский сегмент пустой или обрезан: вывод невозможен, в процент не входит.", N),
    ("absent — термин из определения в казахском пункте не найден (кандидат в расхождение).", N),
    ("Разметка эксперта из предыдущей версии таблицы перенесена в жёлтые столбцы автоматически.", N),
]
for i, (t, f) in enumerate(lines, 1):
    c = ws.cell(row=i, column=1, value=t)
    c.font, c.alignment = f, Alignment(wrap_text=True, vertical="top")

# ---------------- 2. Terms ----------------
ws = wb.create_sheet("Термины")
ws["A1"], ws["A1"].font = "Всего вхождений русских терминов", B
ws["A2"], ws["A2"].font = "Из них казахский термин из определения", B
ws["A3"], ws["A3"].font = "Доля согласованных употреблений (без сбоев выравнивания)", B
first, last = 6, 6 + len(results) - 1
ws["B1"] = f"=SUM(E{first}:E{last})"
ws["B2"] = f"=SUM(F{first}:F{last})+SUM(G{first}:G{last})"
ws["B3"] = f"=IF(B1-SUM(H{first}:H{last})=0,0,B2/(B1-SUM(H{first}:H{last})))"
ws["B3"].number_format = "0.0%"
for c in ("B1", "B2", "B3"):
    ws[c].font = B
cols = ["Статья (определение)", "Русский термин", "Казахский термин (из определения)", "Тип",
        "Вхождений (RU)", "Совпадает (KK)", "С разрывом / перечислением", "Сбой выравнивания",
        "Не найден (KK)", "Согласованность", "Возможные варианты в KK", "Статьи с расхождениями"]
header(ws, 5, cols, [12, 34, 38, 14, 11, 11, 11, 11, 11, 13, 40, 40])
results.sort(key=lambda r: (-(r["kk_absent"]), r["ru"]))
for i, r in enumerate(results, first):
    vals = [r["article"], r["ru"], r["kk"], r["type"], r["ru_occurrences"], r["kk_canonical"],
            r["kk_dispersed"], r["kk_alignment"], r["kk_absent"], f"=IF(E{i}-H{i}=0,0,(F{i}+G{i})/(E{i}-H{i}))",
            ", ".join(f'{c["word"]} ({c["in_misses"]})' for c in r["candidate_words"][:4]),
            ", ".join(r["miss_articles"])]
    for j, v in enumerate(vals, 1):
        c = ws.cell(row=i, column=j, value=v)
        c.font, c.alignment = N, WRAP
    ws.cell(row=i, column=10).number_format = "0.0%"
ws.freeze_panes = "C6"
ws.auto_filter.ref = f"A5:L{last}"

# ---------------- 3. Cases ----------------
ws = wb.create_sheet("Случаи для экспертизы")
cols = ["№", "Русский термин", "Казахский термин (из определения)", "Статья", "Статус",
        "Подсказка (авто)", "Тип расхождения", "Правовое значение", "Комментарий",
        "Русский текст пункта", "Казахский текст пункта"]
header(ws, 1, cols, [6, 28, 30, 9, 10, 28, 22, 14, 34, 70, 70])
n = 1
for r in results:
    cands = [c["word"] for c in r["candidate_words"]]
    for e in r["review"]:
        hint = ", ".join(c for c in cands if c in e["kk"].lower()) if e["status"] == "absent" \
            else "казахский сегмент пустой или обрезан"
        lab = labels.get((r["ru"], e["article"], e["ru"][:600]), (None, None, None))
        vals = [n, r["ru"], r["kk"], e["article"], e["status"], hint, *lab, e["ru"], e["kk"]]
        for j, v in enumerate(vals, 1):
            c = ws.cell(row=n + 1, column=j, value=v)
            c.font, c.alignment = N, WRAP
        for j in (7, 8, 9):
            ws.cell(row=n + 1, column=j).fill = IN
        n += 1
dv1 = DataValidation(type="list", allow_blank=True, formula1='"терминологический вариант,грамматическая вариация,'
                     'перефразирование,ошибка автоматики"')
dv2 = DataValidation(type="list", allow_blank=True, formula1='"да,нет,неясно"')
ws.add_data_validation(dv1)
ws.add_data_validation(dv2)
dv1.add(f"G2:G{n}")
dv2.add(f"H2:H{n}")
ws.freeze_panes = "C2"
ws.auto_filter.ref = f"A1:K{n}"

# ---------------- 4. Findings ----------------
ws = wb.create_sheet("Основные находки")
cols = ["№", "Термин (RU)", "Определение в KK", "Другие варианты в KK", "Где", "Расхождений / вхождений", "Комментарий"]
header(ws, 1, cols, [5, 26, 28, 34, 26, 14, 60])
findings = json.load(open(sys.argv[3], encoding="utf-8"))
for i, f in enumerate(findings, 2):
    for j, v in enumerate([i - 1] + f, 1):
        c = ws.cell(row=i, column=j, value=v)
        c.font, c.alignment = N, WRAP
# ---------------- 5. Evaluation against the expert annotation ----------------
if labels:
    from collections import Counter
    now = {(r["ru"], e["article"], e["ru"][:600]): e["status"] for r in results for e in r["review"]}
    conf = Counter()
    for (term, art, ru), (typ, _, _) in labels.items():
        conf[(typ == "ошибка автоматики", now.get((term, art, ru), "снят автоматически"))] += 1
    ws = wb.create_sheet("Оценка метода")
    header(ws, 1, ["Разметка эксперта", "Статус в этой версии", "Случаев"], [32, 28, 12])
    for i, ((fa, st), v) in enumerate(sorted(conf.items()), 2):
        for j, val in enumerate(["ложная тревога" if fa else "реальное расхождение", st, v], 1):
            ws.cell(row=i, column=j, value=val).font = N
    k = len(conf) + 3
    ws.cell(row=k, column=1, value="Важно: метод доработан на тех же 209 случаях, которыми он здесь проверяется; "
            "для статьи нужна проверка на другом кодексе или на отложенной выборке.").font = B
wb.save(out)
print("saved", out, "cases:", n - 1)
