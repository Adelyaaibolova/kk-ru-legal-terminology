"""Step 2. Extract legal definitions and pair each Russian term with its Kazakh term.

RU pattern: "Под <TERM> [в настоящем Кодексе] понимается/понимаются ..."  and  "<TERM> означает ..."
KK pattern: "<TERM> деп ... түсініледі"                                   and  "<TERM> ... білдіреді"

Paragraphs of each article are aligned by their numbering (1., 2), ...), then the
definition sentences inside an aligned paragraph pair are paired in order.
Output: terms.json
"""
import difflib
import json
import re
import sys

import pymorphy3

morph = pymorphy3.MorphAnalyzer()
corpus = json.load(open(sys.argv[1], encoding="utf-8"))
out = sys.argv[2]

LABEL = re.compile(r"^(\d+(?:-\d+)?[.)])\s")
SENT = re.compile(r"(?<=[.;:])\s+(?=(?:\d+(?:-\d+)?\)\s)?[А-ЯЁӘҒҚҢӨҰҮҺІA-Z])")
RU_DEF = re.compile(
    r"(?:^|\s)[Пп]од\s+(.+?)\s+(?:(?:в|для целей)\s+настоящ\w+\s+\w+\s+|в\s+целях\s+настоящ\w+\s+\w+\s+)?"
    r"понима(?:ется|ются)\b")
RU_DEF2 = re.compile(r"^(?:\d+(?:-\d+)?[.)]\s+)?([А-ЯЁ][^.;:]{2,80}?)\s+означает\b")
KK_PRE = re.compile(r"^(?:\d+(?:-\d+)?[.)]\s+)?(?:Осы\s+(?:Кодексте|параграфта|тарауда|бөлімде|бапта|"
                    r"\w+\s+мақсаттары\s+үшін)\s+)?")
KK_DEF = re.compile(r"^(.{3,120}?)\s+деп\s+.*\bтүсініл(?:еді|еді\.)")
KK_DEF2 = re.compile(r"^(.{3,120}?)\s+[^.;]*\bбілдіреді\b")


def paragraphs(text):
    return [p for p in text.split("\n") if p.strip()]


def label(p):
    m = LABEL.match(p)
    return m.group(1) if m else "-"


def to_nominative(phrase):
    """Под загрязнением окружающей среды -> загрязнение окружающей среды.
    The leading instrumental group (adjectives + head noun) is put into the nominative,
    adjectives agreeing with the head noun; dependents (genitive etc.) stay as they are."""
    words = phrase.split()
    group = []
    for idx, w in enumerate(words):
        core = w.strip('(),«»"')
        parses = [x for x in morph.parse(core) if "ablt" in x.tag]
        if not parses:
            break
        noun = next((x for x in parses if x.tag.POS == "NOUN"), None)
        adj = next((x for x in parses if x.tag.POS in ("ADJF", "PRTF")), None)
        if noun and not (adj and idx + 1 < len(words) and not group and False):
            group.append((idx, core, noun))
            break                                   # head noun reached
        if adj:
            group.append((idx, core, adj))
            continue
        break
    if not group or group[-1][2].tag.POS != "NOUN":
        return phrase
    head = group[-1][2]
    number = "plur" if "plur" in head.tag else "sing"
    gender = head.tag.gender
    res = list(words)
    for idx, core, p in group:
        feats = {"nomn", number}
        if p.tag.POS != "NOUN" and number == "sing" and gender:
            feats.add(gender)
        form = p.inflect(feats)
        if form and form.word[:3] == core.lower()[:3]:   # guard against suppletive forms
            word = form.word
            if core[0].isupper():
                word = word[0].upper() + word[1:]
            res[idx] = words[idx].replace(core, word)
    return " ".join(res)


def ru_defs(par):
    found = []
    for s in SENT.split(par):
        m = RU_DEF.search(s) or RU_DEF2.search(s)
        if m:
            term = m.group(1).strip(" ,")
            found.append({"raw": term, "term": to_nominative(term) if m.re is RU_DEF else term,
                          "sentence": s})
    return found


def kk_defs(par, ru_terms):
    """Return one Kazakh term per Russian definition in the paragraph.
    Strategy A: '<TERM> деп ... түсініледі' (term first).
    Strategy B: '... <TERM> деп түсініледі' (term last; length taken from the RU term) - flagged.
    Strategy C: '<TERM> деп:' / '<TERM>:' introducing a list - flagged."""
    found = []
    sents = SENT.split(par)
    for s in sents:
        s2 = KK_PRE.sub("", s)
        if re.search(r"деп\s+түсініл", s2):                       # B: inverted order
            before = re.split(r"\s+деп\s+түсініл", s2)[0].split()
            n = len(ru_terms[len(found)].split()) if len(found) < len(ru_terms) else 2
            found.append({"term": " ".join(before[-n:]), "sentence": s, "method": "B (inverted, check)"})
        elif "түсініл" in s2 or "білдіреді" in s2:
            m = KK_DEF.search(s2) or KK_DEF2.search(s2)
            if m:
                found.append({"term": m.group(1).strip(" ,"), "sentence": s, "method": "A"})
        elif s2.rstrip().endswith(":") and len(found) < len(ru_terms):
            m = re.match(r"^(.{3,120}?)(?:\s+деп)?\s*:$", s2.strip())
            if m:
                found.append({"term": m.group(1), "sentence": s, "method": "C (list, check)"})
    return found


terms, unmatched = [], []
for art in corpus:
    rp, kp = paragraphs(art["ru_text"]), paragraphs(art["kk_text"])
    sm = difflib.SequenceMatcher(a=[label(p) for p in rp], b=[label(p) for p in kp], autojunk=False)
    pairs = []
    for op, a1, a2, b1, b2 in sm.get_opcodes():
        if op == "equal" or (a2 - a1 == b2 - b1):
            pairs += list(zip(range(a1, a2), range(b1, b2)))
    for i, j in pairs:
        r = [x for x in ru_defs(rp[i]) if "термин" not in x["raw"]]
        if not r:
            continue
        k = kk_defs(kp[j], [x["term"] for x in r])
        if len(r) == len(k):
            for x, y in zip(r, k):
                terms.append({"article": art["id"], "para": label(rp[i]),
                              "ru_term": x["term"], "kk_term": y["term"],
                              "method": y["method"],
                              "ru_sentence": x["sentence"], "kk_sentence": y["sentence"]})
        else:
            unmatched.append({"article": art["id"], "para": label(rp[i]),
                              "ru": [x["term"] for x in r], "kk": [y["term"] for y in k]})

json.dump({"terms": terms, "unmatched": unmatched}, open(out, "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"paired definitions: {len(terms)}; RU definitions without a clean KK pair: {len(unmatched)}")
