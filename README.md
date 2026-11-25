# Terminological (in)consistency in the Kazakh and Russian versions of the Environmental Code of the Republic of Kazakhstan

A corpus-based pilot study of how consistently the legal terms defined in the Environmental Code
(Code of the RK of 2 January 2021 No. 400-VI) are rendered in its Kazakh version.

## Pipeline

| Step | Script | Output |
|---|---|---|
| 1. Article-aligned RU–KK corpus (426 articles; footnotes and IZPI notes removed) | `scripts/build_corpus.py eco.md corpus.json` | `corpus.json` |
| 2. Extraction of legal definitions (*Под X понимается* / *X деп … түсініледі*) and RU–KK term pairing | `scripts/extract_terms.py corpus.json terms.json` | `terms.json` |
| 2b. Manual verification of the extracted pairs | `scripts/curation.py` | — |
| 3. Consistency check for every occurrence of each term | `scripts/analyze.py corpus.json terms.json results.json` | `results.json` |
| 4. Workbook for expert review (optionally carrying over an earlier annotated workbook) | `scripts/make_report.py results.json report.xlsx findings.json [annotated.xlsx]` | `report.xlsx` |
| 5. Evaluation against the expert annotation | `scripts/evaluate.py results.json annotated.xlsx` | console |
| 6a. Blind stratified sample for a second annotator | `scripts/make_iaa_sample.py annotated.xlsx sample.xlsx key.json [n] [seed]` | `sample.xlsx`, `key.json` (keep the key away from the annotator) |
| 6b. Inter-annotator agreement | `scripts/agreement_kappa.py key.json filled_sample.xlsx` | Cohen's kappa |
| 7. Adjudication sheet for the refined scheme (lexical / derivational / inflectional / paraphrase) | `scripts/make_adjudication.py report.xlsx key.json second.xlsx out.xlsx` | `out.xlsx` |
| 8. Event vs result nominals (*выброс*, *сброс*): logistic regression | `scripts/nominal_analysis.py corpus.json rows.json` | console, `rows.json` |

Input `eco.md`: the Russian and Kazakh texts of the Code (from adilet.zan.kz) in one Markdown file,
the Kazakh part starting with the heading `# Қазақша нұсқа`.

## Method in brief

- Russian side: lemma matching with pymorphy3 (all possible normal forms of a word).
- Kazakh side: a term word matches a text word if the text word = a base of the term word + a chain of
  inflectional suffixes (case, plural, possessive), with қ/ғ, к/г alternation. Modifiers may stand
  between the term's words (window of term length + 2).
- Paragraphs are aligned by their numbering inside each article.
- Occurrences of a term nested inside a longer defined term are counted for the longer term only.
- A short term coordinated with another noun and sharing the rest of a longer defined term
  (*выбросов и поглощений парниковых газов*) is counted as an occurrence of the longer term.
- Statuses: `exact`; `dispersed` (inserted words); `coordinated` (term split by a list of coordinated
  nouns: *қалдықтарды жинаудың, …, кәдеге жаратудың*); `restructured` (Kazakh point puts the list first and the
  main clause after it); `alignment` (empty/truncated Kazakh segment, excluded); `absent` (candidate
  inconsistency, sent to expert review).

## Pilot results

146 defined terms, 3,075 occurrences of the Russian terms. Excluding 26 alignment failures, the Kazakh text
uses the term from the definition in 95.3% of occurrences (automatic). After expert review and re-labelling,
122 real discrepancies remain (96.0% consistency): 85 derivational variants of the same root, 22 lexical
replacements, 8 inflectional/syntactic variants and 7 paraphrases. Legal significance concentrates in
lexical replacements (14 of 22 marked significant or unclear, vs 8 of 85 derivational variants).

Evaluation against the expert annotation of the first version (209 flagged cases, 86 false alarms):
the revised method removes or sets aside 65 of the 86 false alarms and still flags all 123 real
discrepancies. The revision was developed on these same cases, so a held-out check (another code) is needed.
Second annotator (blind, 60 cases): kappa 0.90 for real discrepancy vs false alarm, 0.46 for the type
of discrepancy; disagreements concern same-root (derivational) variants.

Most terminological variants are derivational (*шығарынды* / *шығарылу*). For *выброс*, the Kazakh action
noun is predicted by greenhouse-gas domain (OR 60), singular number (OR 6.5) and a goal phrase (OR 3.2):
Kazakh marks the event/result distinction that the Russian nominal leaves open.
The main inconsistencies are listed in `findings.json`.

## Data

| File | Content |
|---|---|
| `data/corpus.json` | 426 aligned articles (Russian / Kazakh), consolidated text with amendments up to the Law of 8 July 2026 No. 342-VIII |
| `data/terms.json` | automatically extracted definition pairs (before curation) |
| `data/results.json` | per-term counts, statuses and cases for review |
| `data/nominal_rows.json` | occurrences of *выброс* / *сброс* used in the event/result analysis |
| `data/annotations/review_expert1.xlsx` | flagged cases with the first (legal) expert's labels |
| `data/annotations/iaa_sample_expert2.xlsx`, `iaa_key.json` | blind sample of 60 cases labelled by the second expert, and the key |
| `data/annotations/adjudication.xlsx` | re-labelling of the 123 confirmed cases under the refined scheme |

The source texts are official publications of the Republic of Kazakhstan (adilet.zan.kz).

## Requirements

```
pip install -r requirements.txt
```
