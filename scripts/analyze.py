"""Step 3. Measure how consistently each defined Russian term is rendered in the Kazakh text.

For every verified term pair (definition article -> RU term, KK term):
  1. find every paragraph of the Russian text where the RU term occurs (lemma match, pymorphy3);
  2. look at the aligned Kazakh paragraph (same article, paragraphs aligned by numbering);
  3. check whether the canonical KK term occurs there (stem match, any inflection, with or
     without the genitive -ның: "қоршаған ортаның сапасы" = "қоршаған орта сапасы");
  4. if not, look in the whole numbered point (Kazakh points are often restructured), flag
     empty/truncated Kazakh segments as alignment problems, and rank candidate variants.
Output: results.json
"""
import difflib
import json
import re
import sys
from collections import Counter, defaultdict

import pymorphy3

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from curation import ADD, FIX  # noqa: E402

corpus = json.load(open(sys.argv[1], encoding="utf-8"))
auto = json.load(open(sys.argv[2], encoding="utf-8"))["terms"]
out = sys.argv[3]
morph = pymorphy3.MorphAnalyzer()

# ---------- term list (automatic + manual verification) ----------
pairs, used_fix = [], set()
for t in auto:
    k = (t["article"], t["ru_term"])
    if k in FIX:
        used_fix.add(k)
        if FIX[k] is None:
            continue
        ru, kk = FIX[k]
    else:
        ru, kk = t["ru_term"], t["kk_term"]
    pairs.append({"article": t["article"], "ru": ru, "kk": kk})
pairs += [{"article": a, "ru": r, "kk": k} for a, r, k in ADD]
pairs = [p for p in pairs if not p["ru"].lower().startswith("котор")]
missing = set(FIX) - used_fix
if missing:
    print("WARNING: curation keys not found:", missing)

# split off "(далее – X)" short forms into their own pairs
expanded = []
for p in pairs:
    mr = re.search(r"\(далее\s*[–-]\s*([^)]+)\)", p["ru"])
    mk = re.search(r"\(бұдан әрі\s*[–-]\s*([^)]+)\)", p["kk"], re.I)
    full_ru = re.sub(r"\s*\(далее[^)]*\)", "", p["ru"]).strip()
    full_kk = re.sub(r"\s*\(бұдан әрі[^)]*\)", "", p["kk"], flags=re.I).strip()
    expanded.append({**p, "ru": full_ru, "kk": full_kk, "type": "full term"})
    if mr and mk:
        expanded.append({**p, "ru": mr.group(1).strip(), "kk": mk.group(1).strip(), "type": "short form (далее)"})
# de-duplicate identical pairs defined twice (e.g. arts. 325 and 366)
seen, terms = {}, []
for p in expanded:
    key = (p["ru"].lower(), p["kk"].lower())
    if key in seen:
        seen[key]["article"] += ", " + p["article"]
        continue
    seen[key] = p
    terms.append(p)

# ---------- Russian side: lemmas ----------
WORD = re.compile(r"[А-Яа-яЁё]+(?:-[А-Яа-яЁё]+)*")
_lem = {}


def lemma(w):
    """All possible normal forms of a word (pymorphy3 is ambiguous: газы -> газ / газы)."""
    w = w.lower()
    if w not in _lem:
        _lem[w] = frozenset(p.normal_form.replace("ё", "е") for p in morph.parse(w))
    return _lem[w]


def ru_key(term):
    term = re.sub(r"\([^)]*\)", " ", term)                      # "(экосистема)" etc.
    return tuple(lemma(w) for w in WORD.findall(term))


def ru_spans(key, toks):
    n = len(key)
    return [(i, i + n) for i in range(len(toks) - n + 1)
            if all(key[j] & toks[i + j] for j in range(n))]


# ---------- Kazakh side: light suffix stripping ----------
KK_WORD = re.compile(r"[А-Яа-яЁёӘәҒғҚқҢңӨөҰұҮүҺһІі]+(?:-[А-Яа-яЁёӘәҒғҚқҢңӨөҰұҮүҺһІі]+)*")
SUFFIXES = sorted("""
лар лер дар дер тар тер
ның нің дың дің тың тің
ға ге қа ке на не
ны ні ды ді ты ті
да де та те нда нде
дан ден тан тен нан нен
мен бен пен
дағы дегі тағы тегі ндағы ндегі
сы сі ы і н
ымыз іміз ңыз ңіз ым ім ң
ың ің ын ін ына іне сын сін ар ер сыз сіз
""".split(), key=len, reverse=True)
SUFSET = set(SUFFIXES)
_dec = {}


def decomposable(rest):
    """Can `rest` be written as a chain of inflectional suffixes?"""
    if rest == "":
        return True
    if rest not in _dec:
        _dec[rest] = any(rest.startswith(x) and decomposable(rest[len(x):]) for x in SUFFIXES)
    return _dec[rest]


def bases(w):
    """All ways to strip suffixes from a term word (BFS), plus қ/ғ, к/г alternation."""
    w = w.lower()
    out, todo = {w}, [w]
    while todo:
        cur = todo.pop()
        for suf in SUFFIXES:
            if cur.endswith(suf) and len(cur) - len(suf) >= 2 and cur[:-len(suf)] not in out:
                out.add(cur[:-len(suf)])
                todo.append(cur[:-len(suf)])
    alt = {"қ": "ғ", "к": "г", "ғ": "қ", "г": "к", "п": "б"}
    for b in list(out):
        if b[-1] in alt:
            out.add(b[:-1] + alt[b[-1]])
    return frozenset(out)


_wm = {}


def word_match(base_set, word):
    key = (base_set, word)
    if key not in _wm:
        word = word.lower()
        _wm[key] = any(word.startswith(b) and decomposable(word[len(b):]) for b in base_set)
    return _wm[key]
_stem = {}


def stem(w):
    w = w.lower()
    if w in _stem:
        return _stem[w]
    s, changed = w, True
    while changed:
        changed = False
        for suf in SUFFIXES:
            if s.endswith(suf) and len(s) - len(suf) >= 2:
                s, changed = s[:-len(suf)], True
                break
    if s[-1:] in "ғг":                     # consonant alternation: жұртшылығы ~ жұртшылық
        s = s[:-1] + {"ғ": "қ", "г": "к"}[s[-1]]
    _stem[w] = s
    return s


def kk_key(term):
    term = re.sub(r"\([^)]*\)", " ", term)
    return tuple(bases(w) for w in KK_WORD.findall(term))


def kk_tokens(text):
    return [(m.group(0), stem(m.group(0))) for m in KK_WORD.finditer(text)]


def kk_find(key, toks, slack=2):
    """True if the stems of the term occur in order within a window of len(term)+slack words
    (allows inserted modifiers: 'қалдықтарды энергетикалық кәдеге жарату')."""
    words = [w for w, _ in toks]
    for i, w in enumerate(words):
        if not word_match(key[0], w):
            continue
        j, pos = 1, i
        while j < len(key):
            nxt = next((q for q in range(pos + 1, min(len(words), i + len(key) + slack))
                        if word_match(key[j], words[q])), None)
            if nxt is None:
                break
            pos, j = nxt, j + 1
        if j == len(key):
            return True
    return False


def kk_coordinated(key, text):
    """Term split by a list of coordinated nouns, e.g. 'қалдықтарды жинаудың, тасудың, ...,
    кәдеге жаратудың': head (and for 3+ word terms the word before it) in place, the other
    words earlier in the same list, with a comma or a conjunction in between."""
    ms = list(KK_WORD.finditer(text))
    words = [m.group(0) for m in ms]
    tail = 2 if len(key) >= 3 else 1
    for h, w in enumerate(words):
        if not word_match(key[-1], w):
            continue
        if tail == 2 and not (h > 0 and word_match(key[-2], words[h - 1])):
            continue
        first = h - tail + 1
        ok, earliest = True, first
        for b in key[:-tail]:
            pos = [q for q in range(max(0, first - 25), first) if word_match(b, words[q])]
            if not pos:
                ok = False
                break
            earliest = min(earliest, pos[-1])
        if not ok:
            continue
        between = text[ms[earliest].end():ms[first].start()]
        if re.search(r",|\bжәне\b|\bнемесе\b|\bмен\b|\bбен\b|\bпен\b", between):
            return True
    return False


# ---------- paragraph alignment ----------
LABEL = re.compile(r"^(\d+(?:-\d+)?[.)])\s")


def lab(p):
    m = LABEL.match(p)
    return m.group(1) if m else "-"


def points(paras):
    """For each paragraph, its text plus the rest of the numbered point ("N." + subitems "N)")
    it belongs to. Kazakh points are often restructured: the list comes first and the
    main clause with the term after it."""
    starts = [i for i, p in enumerate(paras) if re.match(r"^\d+(?:-\d+)?\. ", p)] or [0]
    out = []
    for i in range(len(paras)):
        a = max([s for s in starts if s <= i], default=0)
        b = min([s for s in starts if s > i], default=len(paras))
        out.append(" ".join(paras[i:b]))     # this paragraph and the rest of its point
    return out


aligned = []          # (article, ru_par, kk_par, kk_point)
for art in corpus:
    rp = [p for p in art["ru_text"].split("\n") if p.strip()]
    kp = [p for p in art["kk_text"].split("\n") if p.strip()]
    kpt = points(kp)
    sm = difflib.SequenceMatcher(a=[lab(p) for p in rp], b=[lab(p) for p in kp], autojunk=False)
    for op, a1, a2, b1, b2 in sm.get_opcodes():
        if op == "equal" or a2 - a1 == b2 - b1:
            for i, j in zip(range(a1, a2), range(b1, b2)):
                aligned.append((art["id"], rp[i], kp[j], kpt[j]))
        else:  # unequal block: compare against the whole Kazakh block
            block = " ".join(kp[b1:b2])
            for i in range(a1, a2):
                aligned.append((art["id"], rp[i], block, block))
kk_tok_cache = {}

# ---------- run ----------
keys = [(t, ru_key(t["ru"]), kk_key(t["kk"])) for t in terms]
# longer defined terms that start with a shorter one: "выброс" -> "выбросы парниковых газов"
longer = {id(t): [(L, kl[len(rk):]) for L, kl, _ in keys if len(kl) > len(rk) and kl[:len(rk)] == rk]
          for t, rk, _ in keys}
CONJ = (frozenset({"и"}), frozenset({"или"}))
par_stats = Counter()          # in how many KK paragraphs each stem occurs (for variant ranking)
surface = defaultdict(Counter)
records = {id(t): [] for t in terms}


def coordinated_spans(t, rk, rtoks, spans):
    """'выбросов и поглощений парниковых газов': the short term is coordinated with another
    noun and shares the rest of a longer defined term -> an occurrence of the longer term."""
    extra = []
    for s0, e0 in spans:
        for L, rest in longer[id(t)]:
            if not any(rtoks[k] & c for k in range(e0, min(e0 + 2, len(rtoks))) for c in CONJ):
                continue
            for q in range(e0 + 1, min(e0 + 6, len(rtoks) - len(rest) + 1)):
                if all(rest[x] & rtoks[q + x] for x in range(len(rest))):
                    extra.append((L, (s0, q + len(rest))))
                    break
    return extra


for art, rpar, kpar, kpoint in aligned:
    rtoks = [lemma(w) for w in WORD.findall(rpar)]
    toks = kk_tok_cache.setdefault(id(kpar), kk_tokens(kpar))
    ptoks = kk_tok_cache.setdefault(id(kpoint), kk_tokens(kpoint))
    for w, st in toks:
        surface[st][w.lower()] += 1
    for st in {st for _, st in toks}:
        par_stats[st] += 1
    spans = {id(t): ru_spans(rk, rtoks) for t, rk, _ in keys}
    for t, rk, _ in keys:
        for L, sp in coordinated_spans(t, rk, rtoks, spans[id(t)]):
            spans[id(L)].append(sp)
    allspans = [sp for v in spans.values() for sp in v]
    for t, rk, kkk in keys:
        # ignore matches nested inside a longer defined term ("утилизация отходов" inside
        # "энергетическая утилизация отходов"), they are counted for the longer term
        own = [sp for sp in spans[id(t)]
               if not any(o != sp and o[0] <= sp[0] and sp[1] <= o[1] for o in allspans)]
        if own:
            if kk_find(kkk, toks):
                status = "exact"
            elif kk_find(kkk, toks, slack=12):
                status = "dispersed"         # words of the term separated by inserted phrases
            elif len(kkk) > 1 and kk_coordinated(kkk, kpar):
                status = "coordinated"       # all words present but split by a list of coordinated nouns
            elif kpar.rstrip().endswith(":") and not rpar.rstrip().endswith(":") \
                    and kk_find(kkk, ptoks, slack=12):
                status = "restructured"      # Kazakh point puts the list first, main clause after it
            elif len(kpar) < 0.4 * len(rpar):
                status = "alignment"         # Kazakh segment empty/truncated: no verdict
            else:
                status = "absent"
            records[id(t)].append((art, rpar, kpar, toks, status))
n_par = len(aligned)

results = []
for t, rk, kkk in keys:
    rec = records[id(t)]
    occ = len(rec)
    stc = Counter(r[4] for r in rec)
    hits, dispersed = stc["exact"], stc["dispersed"] + stc["coordinated"] + stc["restructured"]
    unaligned = [r for r in rec if r[4] == "alignment"]
    misses = [r for r in rec if r[4] == "absent"]
    # candidate variants: stems over-represented in the Kazakh paragraphs where the term is missing
    cand = Counter()
    for _, _, _, toks, _ in misses:
        for st in {st for _, st in toks}:
            cand[st] += 1
    ranked = []
    if misses:
        for st, c in cand.items():
            lift = (c / len(misses)) - par_stats[st] / n_par
            if c >= 2 and len(st) > 3 and lift > 0.3 and not any(word_match(b, st) for b in kkk):
                ranked.append((round(lift, 2), surface[st].most_common(1)[0][0], c))
        ranked.sort(reverse=True)
    examples = [{"article": a, "ru": rp[:700], "kk": kp[:700]} for a, rp, kp, _, _ in misses[:4]]
    results.append({**t, "ru_occurrences": occ, "kk_canonical": hits, "kk_dispersed": dispersed,
                    "statuses": dict(stc), "kk_alignment": len(unaligned), "kk_absent": len(misses),
                    "review": [{"article": a, "status": s_, "ru": rp, "kk": kp} for a, rp, kp, _, s_ in misses + unaligned],
                    "consistency": round((hits + dispersed) / (occ - len(unaligned)), 3) if occ > len(unaligned) else None,
                    "miss_articles": sorted({a for a, *_ in misses}, key=lambda x: [int(v) for v in x.split("-")]),
                    "candidate_words": [{"word": w, "in_misses": c, "lift": l} for l, w, c in ranked[:5]],
                    "examples": examples})

json.dump(results, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
valid = [r for r in results if r["ru_occurrences"]]
print(f"terms: {len(results)}, with occurrences: {len(valid)}")
print(f"RU occurrences: {sum(r['ru_occurrences'] for r in valid)}, "
      f"KK canonical: {sum(r['kk_canonical'] for r in valid)}, dispersed: {sum(r['kk_dispersed'] for r in valid)}, "
      f"alignment: {sum(r['kk_alignment'] for r in valid)}, absent: {sum(r['kk_absent'] for r in valid)}")
tot = Counter()
for r in valid:
    tot.update(r["statuses"])
print(dict(tot))
