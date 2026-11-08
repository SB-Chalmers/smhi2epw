# Paper in LaTeX

The gap-filling paper, typeset for the **Journal of Building Performance
Simulation** (Taylor & Francis, `interact`, APA author-date references) — the
target journal since 8 November 2026. The **Energy and Buildings** (Elsevier,
`elsarticle`) wrappers are kept.

| File | What it is |
| --- | --- |
| `main-enb.tex` | Energy and Buildings: front matter, graphical abstract, highlights, numbered references |
| `main-jbps.tex` | **Main version.** JBPS: T&F Interact class (`interact.cls` v1.05, included), APA references via `apacite` |
| `preamble.tex` | Packages and macros shared by both |
| `sections/` | Abstract, highlights, keywords, body, appendices, back matter |
| `refs.bib` | References (BibTeX) |
| `figures/` | Figure files, see `figures/README.md` |
| `tools/md_to_tex.py` | Turns the manuscript's Markdown export into `sections/` |
| `tools/refs_md_to_bib.py` | Turns its reference list into `refs.bib` (first pass, then checked by hand) |

Build with `make enb` (12 pt review preprint) or `latexmk -pdf main-enb-11pt.tex`
(11 pt, journal margins) or `main-enb-5p.tex` (two columns, 10 pt, closest to the printed journal). Build with `make enb` (or `latexmk -pdf main-enb.tex`). On Overleaf, upload this
folder and set `main-enb.tex` as the main document.

## Switching journal

Both wrappers read the same `sections/` and `refs.bib`, and all citations use
`\citep`/`\citet`, so only the wrapper changes. For JBPS, download the T&F
Interact APA template (link in `main-jbps.tex`), copy `interact.cls` here and
build `main-jbps.tex`. JBPS has no highlights or graphical abstract; those files
are simply not used.

## Hand-kept parts

Authors, affiliation and the funding statement are typed in `main-*.tex` and
`sections/backmatter.tex`, so regenerating the text never overwrites them.
