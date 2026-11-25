"""Event vs result nominals: which Kazakh form renders Russian 'выброс' / 'сброс'?

Russian deverbal nouns (выброс, сброс) are ambiguous between an event reading ('the act of
emitting') and a result reading ('what is emitted'). Kazakh distinguishes them morphologically:
result noun -нды/-нді (шығарынды, төгінді) vs action noun -у / passive -ылу (шығару, шығарылу; төгу, төгілу).

For every aligned paragraph with exactly one occurrence of the Russian lemma and only one of the two
Kazakh forms, we record features of the Russian occurrence (number, goal PP 'в/на', genitive argument,
greenhouse-gas domain) and fit a logistic regression for P(Kazakh action noun).
Usage: nominal_analysis.py corpus.json rows.json
"""
import difflib
import json
import re
import sys
from collections import Counter

import numpy as np
import pymorphy3
import statsmodels.api as sm
from scipy.stats import fisher_exact

corpus = json.load(open(sys.argv[1], encoding="utf-8"))
morph = pymorphy3.MorphAnalyzer()
LAB = re.compile(r"^(\d+(?:-\d+)?[.)])\s")
W = re.compile(r"[А-Яа-яЁё]+(?:-[А-Яа-яЁё]+)*")
K = re.compile(r"[А-Яа-яЁёӘәҒғҚқҢңӨөҰұҮүҺһІі]+")
FAM = {"выброс": (re.compile(r"^шығарынды"), re.compile(r"^шығар(ыл|у)")),
       "сброс": (re.compile(r"^төгінді"), re.compile(r"^төг(іл|у)"))}


def lab(p):
    m = LAB.match(p)
    return m.group(1) if m else "-"


rows = []
for a in corpus:
    rp = [p for p in a["ru_text"].split("\n") if p.strip()]
    kp = [p for p in a["kk_text"].split("\n") if p.strip()]
    sm_ = difflib.SequenceMatcher(a=[lab(p) for p in rp], b=[lab(p) for p in kp], autojunk=False)
    for op, a1, a2, b1, b2 in sm_.get_opcodes():
        if not (op == "equal" or a2 - a1 == b2 - b1):
            continue
        for i, j in zip(range(a1, a2), range(b1, b2)):
            toks = W.findall(rp[i])
            for lem, (res_re, ev_re) in FAM.items():
                idx = [t for t, w in enumerate(toks) if morph.parse(w.lower())[0].normal_form == lem]
                if len(idx) != 1:
                    continue
                kw = [w.lower() for w in K.findall(kp[j])]
                res = sum(1 for w in kw if res_re.match(w))
                ev = sum(1 for w in kw if ev_re.match(w) and not res_re.match(w))
                if (res > 0) == (ev > 0):
                    continue                      # neither or both forms: no clean pairing
                t = idx[0]
                p = morph.parse(toks[t].lower())[0]
                nxt = morph.parse(toks[t + 1].lower())[0] if t + 1 < len(toks) else None
                ctx = " ".join(toks[max(0, t - 3):t + 4])
                art = int(a["id"].split("-")[0])
                rows.append({
                    "article": a["id"], "lemma": lem, "kk_form": "action" if ev else "result",
                    "plural": "plur" in p.tag,
                    "goal_pp": any(x.lower() in ("в", "на") for x in toks[t + 1:t + 6]),
                    "genitive_arg": bool(nxt and "gent" in nxt.tag and nxt.tag.POS in ("NOUN", "ADJF", "PRTF")),
                    "ghg_domain": 280 <= art <= 304 or "парников" in ctx.lower(),
                    "register_name": "регистр" in ctx.lower() or "переноса" in ctx.lower(),
                    "context": ctx})
json.dump(rows, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("pairs:", len(rows), Counter((r["lemma"], r["kk_form"]) for r in rows))

vy = [r for r in rows if r["lemma"] == "выброс" and not r["register_name"]]
pol = [r for r in vy if not r["ghg_domain"]]
print(f"\nвыброс, pollutants only (n={len(pol)}):")
for f in ("plural", "goal_pp"):
    tab = [[sum(1 for r in pol if r[f] == v and r["kk_form"] == k) for k in ("action", "result")] for v in (True, False)]
    odds, pval = fisher_exact(tab)
    print(f"  {f}: [[action, result] if True, [..] if False] = {tab}; Fisher odds={odds:.2f}, p={pval:.4f}")
y = np.array([r["kk_form"] == "action" for r in vy], float)
X = np.array([[r["ghg_domain"], not r["plural"], r["goal_pp"], r["genitive_arg"]] for r in vy], float)
fit = sm.Logit(y, sm.add_constant(X)).fit(disp=0)
print(f"\nLogistic regression, P(action noun), выброс without register name (n={len(vy)}):")
print(fit.summary2(xname=["const", "GHG domain", "singular", "goal PP", "genitive arg"]).tables[1].round(3))
