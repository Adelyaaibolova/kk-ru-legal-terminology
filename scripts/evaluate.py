"""Step 5. Compare the automatic verdicts with the expert annotation of the review workbook.

Usage: evaluate.py results.json annotated_report.xlsx
Expert labels: 'ошибка автоматики' = false alarm; every other label = a real discrepancy.
"""
import json
import sys
from collections import Counter

from openpyxl import load_workbook

res = json.load(open(sys.argv[1], encoding="utf-8"))
ws = load_workbook(sys.argv[2], data_only=True)["Случаи для экспертизы"]
gold = [[c.value for c in r] for r in ws.iter_rows(min_row=2) if r[0].value]
new = {}
for x in res:
    for e in x["review"]:
        new[(x["ru"], e["article"], e["ru"][:600])] = e["status"]
conf, missed = Counter(), []
for g in gold:
    st = new.get((g[1], g[3], (g[9] or "")[:600]), "resolved")
    real = g[6] != "ошибка автоматики"
    conf[("real" if real else "false alarm", st)] += 1
    if real and st == "resolved":
        missed.append((g[0], g[1], g[3], g[6]))
for k, v in sorted(conf.items()):
    print(f"{v:4d}  expert: {k[0]:12s} -> now: {k[1]}")
fa = sum(v for k, v in conf.items() if k[0] == "false alarm")
fa_left = conf[("false alarm", "absent")]
real = sum(v for k, v in conf.items() if k[0] == "real")
kept = real - len(missed)
print(f"false alarms removed or set aside: {fa - fa_left}/{fa}; real discrepancies still flagged: {kept}/{real}")
for m in missed:
    print("  lost:", m)
