"""Step 1. Build an article-aligned Russian–Kazakh corpus of the Environmental Code of the RK.

Input:  the combined markdown file (Russian version, then "# Қазақша нұсқа").
Output: corpus.json — list of {"id", "ru_title", "ru_text", "kk_title", "kk_text"}.

Cleaning: PDF page markers and page numbers, editorial footnotes
("Сноска." / "Ескерту."), IZPI notes, chapter/section headings.
"""
import json
import re
import sys

src, out = sys.argv[1], sys.argv[2]
text = open(src, encoding="utf-8").read()
ru_raw, kk_raw = text.split("# Қазақша нұсқа", 1)

PAGE = re.compile(r"^\s*(<!-- Страница PDF \d+ -->|\d+ / \d+)\s*$")
NOTE_START = re.compile(r"^\s*(Сноска\.|Ескерту\.|Примечание ИЗПИ|ЗҚАИ-ның ескертпесі)")
NOTE_END = re.compile(r"(\)\.|Заңымен\.|Заңдарымен\.|қараңыз\.|см\. ст\. \d+|!)\s*$")
HEADING = re.compile(
    r"^\s*(ОБЩАЯ ЧАСТЬ|ОСОБЕННАЯ ЧАСТЬ|ЖАЛПЫ БӨЛІМ|ЕРЕКШЕ БӨЛІМ|РАЗДЕЛ \d+|Глава \d+|Параграф \d+"
    r"|\d+-бөлім|\d+-тарау|\d+-параграф)\b")
ART = {
    "ru": re.compile(r"^Статья (\d+(?:-\d+)?)\.\s*(.*)$"),
    "kk": re.compile(r"^(\d+(?:-\d+)?)-бап\.\s*(.*)$"),
}


def clean_lines(raw):
    lines, in_note = [], False
    for line in raw.splitlines():
        if PAGE.match(line):
            continue
        if in_note:
            if NOTE_END.search(line) or not line.strip():
                in_note = False
            continue
        if NOTE_START.match(line):
            in_note = not NOTE_END.search(line)
            continue
        lines.append(line.rstrip())
    return lines


def split_articles(lines, lang):
    arts, cur, heading_mode = {}, None, False
    for line in lines:
        m = ART[lang].match(line.strip())
        if m:
            cur = {"title": m.group(2), "body": [], "in_title": True}
            arts[m.group(1)] = cur
            continue
        if cur is None:
            continue
        if HEADING.match(line):
            heading_mode = True  # heading may wrap onto next line(s)
            continue
        if heading_mode and line.strip() and not line.startswith(" "):
            continue
        heading_mode = False
        st = line.strip()
        if cur["in_title"] and st and (not line.startswith(" ") or st[0].islower()):
            cur["title"] += " " + line.strip()
            continue
        if not st:
            continue
        cur["in_title"] = False
        cur["body"].append(line)
    for a in arts.values():
        paras = []
        for line in a.pop("body"):
            s = line.strip()
            if not s:
                continue
            if not paras or re.match(r"^\d+(?:-\d+)?[.)] ", s):
                paras.append(s)                                  # new numbered item
            elif paras[-1].endswith("-"):
                paras[-1] += s                                   # hyphen at line break
            else:
                paras[-1] += " " + s                             # unwrap PDF line
        a["text"] = "\n".join(paras)
        a.pop("in_title")
    return arts


ru = split_articles(clean_lines(ru_raw), "ru")
kk = split_articles(clean_lines(kk_raw), "kk")

def key(n):
    a, _, b = n.partition("-")
    return (int(a), int(b or 0))

ids = sorted(set(ru) | set(kk), key=key)
corpus = [{"id": i,
           "ru_title": ru.get(i, {}).get("title", ""), "ru_text": ru.get(i, {}).get("text", ""),
           "kk_title": kk.get(i, {}).get("title", ""), "kk_text": kk.get(i, {}).get("text", "")}
          for i in ids]
json.dump(corpus, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"RU articles: {len(ru)}, KK articles: {len(kk)}, aligned: {len(set(ru) & set(kk))}")
print("only RU:", sorted(set(ru) - set(kk), key=key), "only KK:", sorted(set(kk) - set(ru), key=key))
