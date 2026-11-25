"""Cohen's kappa between the first annotator (key.json) and a second annotator (filled sample.xlsx).

Usage: agreement_kappa.py key.json filled_sample.xlsx
"""
import json
import sys
from collections import Counter

from openpyxl import load_workbook

key = json.load(open(sys.argv[1], encoding="utf-8"))
ws = load_workbook(sys.argv[2], data_only=True)["Разметка"]
second = {r[0]: (r[4], r[5]) for r in ws.iter_rows(min_row=2, values_only=True) if r[0]}


def kappa(pairs):
    n = len(pairs)
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / n ** 2
    return po, (po - pe) / (1 - pe) if pe < 1 else 1.0


for name, idx, fkey in [("type", 0, "type"), ("legal significance", 1, "legal")]:
    pairs = [(key[c][fkey], second[c][idx]) for c in key if c in second and second[c][idx]]
    if not pairs:
        print(name, ": no labels yet")
        continue
    po, k = kappa(pairs)
    print(f"{name}: n={len(pairs)}, observed agreement={po:.2f}, Cohen's kappa={k:.2f}")
    binary = [(a == "ошибка автоматики", b == "ошибка автоматики") for a, b in pairs] if idx == 0 else None
    if binary:
        po, k = kappa(binary)
        print(f"  real vs false alarm: observed={po:.2f}, kappa={k:.2f}")
