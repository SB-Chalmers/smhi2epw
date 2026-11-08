"""Convert the manuscript (Claude Docs Markdown export) into the LaTeX section files.

Usage:
    python tools/md_to_tex.py paper.md

Writes sections/abstract.tex, highlights.tex, keywords.tex, body.tex,
data_availability.tex, acknowledgements.tex,
ai_declaration.tex and appendix.tex next to this script's parent folder.
Front matter (authors, affiliation, funding) is kept by hand in the main files
and sections/backmatter.tex, so re-running this script never touches it.

What it does:
- turns author-year citations into \\citep / \\citet keys from refs.bib;
- turns "Figure N", "Table N", "Section x.y" and "Appendix X" into \\ref links;
- writes each figure as a figure float that loads figures/figNN (pdf or png);
- writes each Markdown table as a table float, column widths set from the text.
Anything it cannot match is listed on stderr for a hand check.
"""
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SECT = ROOT / "sections"
warn = lambda *a: print("WARN:", *a, file=sys.stderr)


# ---------------------------------------------------------------- citations
def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", s.lower())


def load_keys():
    keys = {}
    bib = (ROOT / "refs.bib").read_text(encoding="utf-8")
    for m in re.finditer(r"@\w+\{(\w+),", bib):
        k = m.group(1)
        km = re.match(r"([a-z]+)(\d{4}[a-z]?)$", k)
        keys[(km.group(1), km.group(2))] = k
    # short forms used in the text that differ from the first author
    keys[("ieapvps", "2023")] = "ieapvps2023"
    return keys


KEYS = None
NAME = r"(?:[A-ZÀ-Ý][\w'’À-ÿ\-]*|diyepw|van|de|Delle)(?:\s(?:[A-ZÀ-Ý][\w'’À-ÿ\-]*|PVPS))*"
AUTH = rf"{NAME}(?:\s(?:et al\.|and\s{NAME}))?"
YEAR = r"\d{4}[a-z]?"


def key_for(auth, year):
    first = re.split(r"\s+et al\.|\s+and\s", auth)[0].strip()
    k = KEYS.get((norm(first), year))
    if not k:
        warn("no bib key for", auth, year)
    return k


def cite_part(part):
    """'Hong et al., 2013' -> key; returns None if not a citation."""
    m = re.fullmatch(rf"\s*({AUTH}),\s*({YEAR}(?:,\s*{YEAR})*)\s*", part)
    if not m:
        return None
    auth = m.group(1)
    out = []
    for y in re.split(r",\s*", m.group(2)):
        k = key_for(auth, y)
        if not k:
            return None
        out.append(k)
    return out


def convert_citations(text):
    def partial(parts):
        """'(hot and dry; SMHI, 2018)' -> '(hot and dry; \\citealp{smhi2018})'"""
        out = []
        for p in parts:
            k = cite_part(p)
            out.append((" " if p.startswith(" ") else "") + f"\\citealp{{{','.join(k)}}}" if k else p)
        res = "(" + ";".join(out) + ")"
        if "\\cite" not in res and re.search(r"[A-Z]\w+.*\d{4}", res):
            warn("unmatched citation?", res)
        return res

    def paren(m):
        inner = m.group(1)
        parts = inner.split(";")
        keys, pre = [], ""
        for i, p in enumerate(parts):
            pm = re.match(r"\s*(e\.g\.,?|see|cf\.)\s+", p)
            if i == 0 and pm:
                pre = pm.group(1)
                p = p[pm.end():]
            k = cite_part(p)
            if k is None:
                return partial(parts)
            keys += k
        opt = f"[{pre}][]" if pre else ""
        return f"\\citep{opt}{{{','.join(keys)}}}"

    text = re.sub(r"\(([^()]*?\d{4}[a-z]?)\)", paren, text)

    # narrative: "Eguía Oller et al. (2017)", "Anjomshoaa and Salmanzadeh (2019)"
    def narr(m):
        k = key_for(m.group(1), m.group(2))
        return f"\\citet{{{k}}}" if k else m.group(0)

    text = re.sub(rf"({AUTH})\s\(({YEAR})\)", narr, text)
    # in table cells: "Hong et al., 2013" on its own, or "Titikpina et al. (2015)"
    return text


# ---------------------------------------------------------------- cross-refs
def convert_refs(text):
    def lab(kind, n):
        return f"{kind}:{n}"

    text = re.sub(r"\bFigures (\d+|[A-Z]\d+) and (\d+|[A-Z]\d+)",
                  lambda m: f"Figures\u00a0\\ref{{fig:{m.group(1)}}} and\u00a0\\ref{{fig:{m.group(2)}}}", text)
    text = re.sub(r"\bTables (\d+|[A-Z]\d+) and (\d+|[A-Z]\d+)",
                  lambda m: f"Tables\u00a0\\ref{{tab:{m.group(1)}}} and\u00a0\\ref{{tab:{m.group(2)}}}", text)
    text = re.sub(r"\bFigure (\d+|[A-Z]\d+)(?!\d)", lambda m: f"Figure\u00a0\\ref{{fig:{m.group(1)}}}", text)
    text = re.sub(r"\bTable (\d+|[A-Z]\d+)(?!\d)", lambda m: f"Table\u00a0\\ref{{tab:{m.group(1)}}}", text)
    text = re.sub(r"\bSections (\d+(?:\.\d+)?) and (\d+(?:\.\d+)?)",
                  lambda m: f"Sections\u00a0\\ref{{sec:{m.group(1)}}} and\u00a0\\ref{{sec:{m.group(2)}}}", text)
    text = re.sub(r"\bSection (\d+(?:\.\d+)?)", lambda m: f"Section\u00a0\\ref{{sec:{m.group(1)}}}", text)
    text = re.sub(r"\bAppendix ([A-C])\b", lambda m: f"\\ref{{app:{m.group(1)}}}", text)
    return text


# ---------------------------------------------------------------- pandoc
def pandoc(md):
    r = subprocess.run(["pandoc", "-f", "markdown+raw_tex-auto_identifiers",
                        "-t", "latex", "--wrap=none", "--shift-heading-level-by=-1"],
                       input=md, capture_output=True, text=True, check=True)
    out = r.stdout
    out = out.replace("\\tightlist\n", "")
    out = re.sub(r"\\def\\labelenumi\{[^\n]*\}\n", "", out)
    return out


def inline(md):
    return pandoc(md).strip()


def prep(md):
    """Citations and cross-references on Markdown text."""
    md = md.replace("&#91;", "[")
    # keep a number and its unit on one line
    md = re.sub(r"(\d) (°C|%|W/m|kWh/m|km|K\b|h\b|hPa|m/s|mm|GB)", "\\1\u00a0\\2", md)
    md = re.sub(r"(?<![<(\[])\b(https?://[^\s)<>]+?)([.,;]?)(?=[\s)]|$)", r"<\1>\2", md)
    md = re.sub(r"\((https?://[^\s)]+)\)", r"(<\1>)", md)
    return convert_refs(convert_citations(md))


# ---------------------------------------------------------------- blocks
def fig_file(n):
    return f"fig{int(n):02d}" if n.isdigit() else f"fig{n}"


# Small figures drawn at their print size; shown at natural size, not
# stretched to the text width (the flow chart in Appendix B).
NATURAL_SIZE = {"figB1"}


def figure_block(n, caption):
    cap = inline(prep(caption))
    f = fig_file(n)
    opt = "[scale=1]" if f in NATURAL_SIZE else ""
    return ("\\begin{figure*}[tbp]\n\\centering\n"
            f"\\paperfigure{opt}{{{f}}}\n"
            f"\\caption{{{cap}}}\n\\label{{fig:{n}}}\n\\end{{figure*}}\n")


def table_block(n, caption, rows):
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    head, body = cells[0], cells[2:]
    ncol = len(head)
    # column widths in proportion to the longest words / average text per column
    cols = []
    for j in range(ncol):
        col = [r[j] if j < len(r) else "" for r in cells[:1] + body]
        longest = max(len(w) for c in col for w in (c.split() or [""]))
        if all(len(c) <= 2 for c in col[1:]):
            cols.append(("C", longest * 3.0))  # dots and dashes: centred
            continue
        avg = sum(len(c) for c in col) / len(col)
        cols.append(("L", max(avg, longest * 3.5, 8)))
    total = sum(w for _, w in cols)
    spec = "@{}"
    for t, w in cols:
        spec += f"{t}{{\\dimexpr{w / total:.3f}\\linewidth-2\\tabcolsep}}"
    spec += "@{}"
    def cell_cite(c):
        m = re.match(rf"({AUTH}),\s*({YEAR})(\b.*)$", c)
        k = key_for(m.group(1), m.group(2)) if m else None
        return f"\\citet{{{k}}}{m.group(3)}" if k else c
    esc = lambda c: re.sub(r"^(\d+)\.\s", r"\1\\. ", c)  # '1. Main' is not a list
    conv = lambda s: inline(prep(cell_cite(esc(s)))) if s else ""
    lines = [" & ".join(conv(c) for c in head) + " \\\\"]
    body_tex = [" & ".join(conv(c) for c in r) + " \\\\" for r in body]
    captex = f"\\caption{{{inline(prep(caption))}}}\n\\label{{tab:{n}}}\n" if caption else ""
    size = "\\footnotesize" if sum(len(c) for r in cells for c in r) > 1200 else "\\small"
    return ("\\begin{table*}[tbp]\n\\centering\n" + size + "\n" + captex +
            f"\\begin{{tabular}}{{{spec}}}\n\\toprule\n"
            + lines[0] + "\n\\midrule\n" + "\n".join(body_tex) +
            "\n\\bottomrule\n\\end{tabular}\n\\end{table*}\n")


def heading(line):
    m = re.match(r"(#+)\s+(.*)", line)
    level, txt = len(m.group(1)), m.group(2).strip()
    am = re.match(r"Appendix ([A-Z])\.\s*(.*)", txt)
    if am:
        L = am.group(1)
        return (f"\\section{{{inline(am.group(2))}}}\\label{{app:{L}}}\n"
                "\\setcounter{figure}{0}\\setcounter{table}{0}\n"
                f"\\renewcommand{{\\thefigure}}{{{L}\\arabic{{figure}}}}\n"
                f"\\renewcommand{{\\thetable}}{{{L}\\arabic{{table}}}}\n")
    nm = re.match(r"(\d+(?:\.\d+)*)\s+(.*)", txt)
    cmd = {2: "section", 3: "subsection", 4: "subsubsection"}[level]
    if nm:
        return f"\\{cmd}{{{inline(nm.group(2))}}}\\label{{sec:{nm.group(1)}}}\n"
    return f"\\{cmd}*{{{inline(txt)}}}\n"


def convert(md_lines):
    out, para = [], []

    def flush():
        if para:
            out.append(pandoc(prep("\n".join(para))))
            para.clear()

    i = 0
    while i < len(md_lines):
        line = md_lines[i]
        s = line.strip()
        fm = re.match(r"(?:&#91;|\[)image: Figure ([A-Z]?\d+)\.", s)
        tm = re.match(r"\*?Table ([A-Z]?\d+)\.\s(.*?)\*?$", s)
        if fm:
            flush()
            n = fm.group(1)
            j = i + 1
            while j < len(md_lines) and not md_lines[j].strip():
                j += 1
            cap = md_lines[j].strip()
            cap = re.sub(rf"^Figure {n}\.\s*", "", cap)
            out.append(figure_block(n, cap))
            i = j + 1
            continue
        if tm and i + 2 < len(md_lines) and (md_lines[i + 2].lstrip().startswith("|")
                                             or md_lines[i + 1].lstrip().startswith("|")):
            flush()
            n, cap = tm.group(1), tm.group(2)
            j = i + 1
            while not md_lines[j].lstrip().startswith("|"):
                j += 1
            rows = []
            while j < len(md_lines) and md_lines[j].lstrip().startswith("|"):
                rows.append(md_lines[j])
                j += 1
            out.append(table_block(n, cap, rows))
            i = j
            continue
        if s.startswith("|"):
            flush()
            rows = []
            while i < len(md_lines) and md_lines[i].lstrip().startswith("|"):
                rows.append(md_lines[i])
                i += 1
            warn("table without a caption:", rows[0][:60])
            out.append(table_block(None, None, rows))
            continue
        if s.startswith("#"):
            flush()
            out.append(heading(s))
        elif not s:
            flush()
        else:
            para.append(line)
        i += 1
    flush()
    return "\n".join(out)


def section(md, title):
    m = re.search(rf"^##\s+{re.escape(title)}\s*$(.*?)(?=^##\s|\Z)", md, re.S | re.M)
    return m.group(1).strip() if m else ""


def main(path):
    global KEYS
    KEYS = load_keys()
    md = Path(path).read_text(encoding="utf-8")

    abstract = section(md, "Abstract")
    hl = re.search(r"\*\*Highlights\*\*\s*(.*?)\n\n\*\*Keywords:\*\*\s*(.*)$", abstract, re.S)
    abs_text = abstract.split("**Highlights**")[0].strip()
    (SECT / "abstract.tex").write_text(inline(prep(abs_text)) + "\n", encoding="utf-8")
    items = [l[2:].strip() for l in hl.group(1).splitlines() if l.startswith("- ")]
    for it in items:
        if len(it) > 85:
            warn(f"highlight longer than 85 characters ({len(it)}): {it}")
    (SECT / "highlights.tex").write_text(
        "".join(f"\\item {inline(prep(it))}\n" for it in items),
        encoding="utf-8")
    kws = [k.strip() for k in hl.group(2).split(";")]
    (SECT / "keywords.tex").write_text(" \\sep ".join(inline(k) for k in kws) + "\n", encoding="utf-8")

    lines = md.splitlines()
    start = next(i for i, l in enumerate(lines) if re.match(r"##\s+1\s", l))
    end = next(i for i, l in enumerate(lines) if l.startswith("## Data and code availability"))
    app = next(i for i, l in enumerate(lines) if l.startswith("## Appendix A"))
    refs = next(i for i, l in enumerate(lines) if l.startswith("## References"))
    (SECT / "body.tex").write_text(convert(lines[start:end]), encoding="utf-8")
    (SECT / "appendix.tex").write_text(convert(lines[app:refs]), encoding="utf-8")

    for t, fn in [("Data and code availability", "data_availability"),
                  ("Acknowledgements", "acknowledgements"),
                  ("Declaration of generative AI and AI-assisted technologies in the writing process",
                   "ai_declaration")]:
        (SECT / f"{fn}.tex").write_text(pandoc(prep(section(md, t))), encoding="utf-8")

if __name__ == "__main__":
    main(sys.argv[1])
