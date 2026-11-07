"""Convert the manuscript's Markdown reference list into BibTeX.

Usage: python refs_md_to_bib.py paper.md > refs.bib
The reference section must start with '## References'. Each entry is
'Authors (Year). Title. Source. https://doi.org/...'. Hand-check the output.
"""
import re, sys, unicodedata

ORGS = {"ASHRAE", "CIBSE", "EVO", "NREL", "SMHI", "Sveby", "diyepw",
        "SB-Chalmers", "IEA PVPS Task 16"}

def tex_escape(s):
    s = s.replace("\\[", "[").replace("\\]", "]").replace("\\_", "_")
    for a, b in [("&", r"\&"), ("%", r"\%"), ("_", r"\_"), ("#", r"\#")]:
        s = s.replace(a, b)
    return s

def ascii_key(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", s.lower())

def split_authors(a):
    a = a.strip().rstrip(",")
    if a in ORGS:
        return "{" + a + "}", a
    others = a.endswith("et al.")
    if others:
        a = a[: -len("et al.")].strip().rstrip(",")
    parts = re.findall(r"\s*([^,]+?),\s*((?:[A-ZÀ-Ý][a-zà-ý]?\.(?:-|\s)?)+)(?:,|$)", a)
    if not parts:
        return "{" + a + "}", a
    # BibTeX cuts accented initials in half, so write them as LaTeX accents
    acc = {"Á": "{\\'A}", "É": "{\\'E}", "Ö": '{\\"O}', "Å": "{\\AA}"}
    fix = lambda ini: "".join(acc.get(c, c) for c in ini)
    names = [f"{last.strip()}, {fix(ini.strip())}" for last, ini in parts]
    if others:
        names.append("others")
    return " and ".join(names), parts[0][0].strip()

def main(path):
    text = open(path, encoding="utf-8").read()
    refs = text.split("## References", 1)[1]
    entries = [l.strip()[2:] if l.strip().startswith("- ") else l.strip()
               for l in refs.splitlines()]
    entries = [e for e in entries if re.match(r".+?\(\d{4}[a-z]?\)\.", e)]
    seen = {}
    out = []
    for e in entries:
        m = re.match(r"(.+?)\s*\((\d{4})([a-z]?)\)\.\s*(.*)", e)
        authors, year, suffix, rest = m.groups()
        doi = url = None
        dm = re.search(r"https://doi\.org/(\S+)$", rest)
        if dm:
            doi = dm.group(1); rest = rest[: dm.start()].strip()
        else:
            um = re.search(r"(https?://\S+?)(?:\s*\((accessed[^)]*)\))?\.?$", rest)
            if um:
                url = um.group(1); note = um.group(2)
                rest = rest[: um.start()].strip()
        auth, first = split_authors(authors)
        key = ascii_key(first) + year + suffix
        if key in seen:
            key += "b"
        seen[key] = 1
        # title = up to first '. ' that is followed by an uppercase letter or digit
        tm = re.match(r"(.+?[.?!])\s+(.*)$", rest)
        title, src = (tm.group(1), tm.group(2)) if tm else (rest, "")
        title = title.rstrip(".")
        jm = re.match(r"(.+?)\s+(\d+)(?:\((\d+)\))?,\s*([\w–-]+)\.?$", src)
        fields = [("author", auth), ("title", "{" + tex_escape(title) + "}"), ("year", year)]
        if jm:
            typ = "article"
            fields += [("journal", tex_escape(jm.group(1))), ("volume", jm.group(2))]
            if jm.group(3): fields.append(("number", jm.group(3)))
            fields.append(("pages", jm.group(4).replace("–", "--")))
        else:
            typ = "misc"
            if src: fields.append(("howpublished", tex_escape(src.rstrip("."))))
        if doi: fields.append(("doi", doi))
        if url: fields.append(("url", url))
        if url and 'note' in dir() and note: fields.append(("note", note[0].upper() + note[1:]))
        note = None
        body = ",\n".join(f"  {k} = {{{v}}}" if not v.startswith("{") or k != "title" else f"  {k} = {v}" for k, v in fields)
        out.append(f"@{typ}{{{key},\n{body}\n}}\n")
    sys.stdout.write("% Generated from the manuscript reference list, then checked by hand.\n\n" + "\n".join(out))

main(sys.argv[1])
