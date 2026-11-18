#!/usr/bin/env python3
"""build_pdf.py — build the paper's PDF (and, with --docx, a Word file) from its Markdown source with pandoc and xelatex.

Usage:  python3 build_pdf.py <paper.md> [out.pdf] [--docx]

Why a script and not a bare pandoc call: the source writes inline mathematics as $...$ and
often follows it directly with a digit ($\\sim$386,000; $>$146$\\times$). Pandoc does not read
an inline span as mathematics when a digit follows its closing delimiter, so a bare call
misreads them (219 spans are followed by a digit in the draft of 2026-11-16; measured on the
parsed document, a bare call reads 1,155 of its 1,365 inline spans as mathematics). This script leaves the
source untouched and, in a temporary copy, (1) converts every $...$ to \\(...\\) and every
$$...$$ line to \\[...\\], pairing the dollars itself, line by line, and (2) where a digit
follows a span, puts an empty raw-LaTeX group between them, which prints nothing and lets
pandoc read the span. It also lifts the title, author and date lines into the PDF's title
block, handing them to pandoc in a temporary YAML metadata file rather than as -M flags (the
publishing procedure, section 5: non-ASCII characters broke on the command line). With --docx
it also writes a .docx beside the PDF from the same transformed text; the docx writer drops the
raw-LaTeX fragments. Fonts follow the procedure: TeX Gyre Pagella for text and Latin Modern
Math for mathematics when `fc-list` finds Pagella (installed for the user on 2026-11-17);
otherwise pandoc's defaults, and the summary line says which. Standard library only; needs
pandoc and xelatex on the PATH.

Added 2026-11-18: if a file named like the source with the suffix .meta.yaml sits beside it
(paper_X.meta.yaml for paper_X.md), its lines are appended to the metadata file, so the PDF and
Word file carry a subject and keywords for search. The earlier script is in
archive/2026-11-18_before-new-abstract/.
"""
import json, pathlib, re, subprocess, sys, tempfile

INLINE = re.compile(r'(?<!\\)\$(?:[^$\\\n]|\\.)+?(?<!\\)\$')


def convert_math(text):
    out = []
    for n, line in enumerate(text.split("\n"), 1):
        s = line.strip()
        if s.startswith("$$"):
            if not (s.endswith("$$") and s.count("$$") == 2 and len(s) > 4):
                sys.exit(f"line {n}: display mathematics is not on one line; not converted")
            out.append("\\[" + s[2:-2] + "\\]")
            continue
        if len(re.findall(r'(?<!\\)\$', line)) % 2:
            sys.exit(f"line {n}: odd number of unescaped dollar signs; not converted")
        parts, pos = [], 0
        for m in INLINE.finditer(line):
            parts.append(line[pos:m.start()])
            inner = m.group(0)[1:-1]
            if re.match(r'\\sim(?=[ \d\\])', inner):  # "\sim 1.6\times" -> tight, as "$\sim$1.6" prints
                inner = "{\\sim}" + inner[4:].lstrip()
            parts.append("\\(" + inner + "\\)")
            if line[m.end():m.end() + 1].isdigit():
                parts.append("`{}`{=latex}")  # prints nothing; see the module docstring
            pos = m.end()
        parts.append(line[pos:])
        out.append("".join(parts))
    return "\n".join(out)


def _cells(row):
    return [c.strip() for c in row.strip().strip("|").split("|")]


def _plain_len(cell):
    c = re.sub(r'\\[a-zA-Z]+', 'x', cell)          # a TeX command prints as about one character
    c = re.sub(r'[$\\{}^_*`]', '', c)
    return len(c)


def widen_tables(text):
    """Pandoc sets the relative widths of a pipe table's columns from the dashes in its
    separator row. The source writes every separator as |---|---|, which gives equal columns
    and lets long first-column names run into the next. Here each separator is rewritten with
    dashes in proportion to the longest word-wrapped content of its column (bounded)."""
    lines = text.split("\n")
    i = 0
    while i < len(lines) - 1:
        if lines[i].lstrip().startswith("|") and re.fullmatch(r'\s*\|(\s*:?-{3,}:?\s*\|)+\s*', lines[i + 1]):
            j = i + 2
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                j += 1
            rows = [_cells(lines[k]) for k in [i] + list(range(i + 2, j))]
            ncol = len(_cells(lines[i + 1]))
            width = []
            for c in range(ncol):
                col = [r[c] for r in rows if c < len(r)]
                longest_word = max((max((_plain_len(w) for w in cell.split()), default=0) for cell in col), default=3)
                total = max((_plain_len(cell) for cell in col), default=3)
                width.append(max(4, min(40, max(longest_word + 2, int(total ** 0.75) + 2))))
            lines[i + 1] = "|" + "|".join("-" * w for w in width) + "|"
            i = j
        else:
            i += 1
    return "\n".join(lines)


def lift_title_block(text):
    """The source opens with '# Title', '**Author**', an affiliation line and a date line,
    then a rule. Returns (metadata, body-without-those-lines)."""
    lines = text.split("\n")
    meta = {}
    i = 0
    head = []
    while i < len(lines) and lines[i].strip() != "---":
        if lines[i].strip():
            head.append(lines[i].strip())
        i += 1
    if not head or not head[0].startswith("# "):
        return {}, text
    meta["title"] = head[0][2:].strip()
    rest = head[1:]
    if rest and rest[0].startswith("**") and rest[0].endswith("**"):
        meta["author"] = rest[0].strip("*")
        rest = rest[1:]
    if rest:
        meta["date"] = rest[-1]
        if len(rest) > 1:
            meta["institute"] = "; ".join(rest[:-1])
    body = "\n".join(lines[i + 1:])  # drop the rule that closed the head
    return meta, body


def _report(r, out):
    """Print one summary line (and any warning that is not a missing glyph) for a pandoc run."""
    warnings = [w for w in r.stderr.splitlines() if w.strip()]
    missing = sorted({re.search(r'There is no (\S+)', w).group(1) for w in warnings if "Missing character" in w})
    print(f"pandoc exit {r.returncode} · {out.name} · {out.stat().st_size if out.exists() else 0} bytes · "
          f"warnings {len(warnings)} · characters missing from the font: {' '.join(missing) if missing else 'none'}")
    for w in warnings:
        if "Missing character" not in w:
            print("  ", w[:200])
    return r.returncode


def main():
    args = sys.argv[1:]
    flags = [a for a in args if a.startswith("--")]
    paths = [a for a in args if not a.startswith("--")]
    if not paths or len(paths) > 2 or set(flags) - {"--docx"}:
        sys.exit(__doc__)
    src = pathlib.Path(paths[0]).resolve()
    out = pathlib.Path(paths[1]).resolve() if len(paths) > 1 else src.with_suffix(".pdf")
    meta, body = lift_title_block(src.read_text())
    body = convert_math(widen_tables(body))
    author = meta.get("author", "")
    if meta.get("institute"):
        author = f"{author} ({meta['institute']})" if author else meta["institute"]
    title_block = [(k, v) for k, v in (("title", meta.get("title")), ("author", author),
                                        ("date", meta.get("date"))) if v]
    codes = []
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td) / "paper.md"
        tmp.write_text(body)
        metafile = pathlib.Path(td) / "metadata.yaml"
        # a JSON string is a valid YAML double-quoted scalar, so any character survives
        sidecar = src.with_suffix(".meta.yaml")
        extra = sidecar.read_text(encoding="utf-8") if sidecar.exists() else ""
        if extra:
            print("metadata added from", sidecar.name)
        metafile.write_text("".join(f"{k}: {json.dumps(v, ensure_ascii=False)}\n" for k, v in title_block) + extra,
                            encoding="utf-8")
        common = ["pandoc", str(tmp),
                  "-f", "markdown-tex_math_dollars+tex_math_single_backslash-implicit_figures+autolink_bare_uris",
                  f"--resource-path={src.parent}", f"--metadata-file={metafile}"]
        cmd = common + ["-o", str(out), "--pdf-engine=xelatex",
                        "-V", "geometry:margin=1in", "-V", "fontsize=10pt", "-V", "colorlinks=true",
                        "-V", "linkcolor=black", "-V", "urlcolor=blue", "-V", "citecolor=black"]
        try:
            has_pagella = "pagella" in subprocess.run(["fc-list"], capture_output=True, text=True).stdout.lower()
        except OSError:
            has_pagella = False
        if has_pagella:
            cmd += ["-V", "mainfont=TeX Gyre Pagella", "-V", "mathfont=latinmodern-math.otf"]  # by file name: the math font lives in the TeX tree, not among the system fonts
        print("text font:", "TeX Gyre Pagella" if has_pagella else "pandoc default (Pagella not found)")
        codes.append(_report(subprocess.run(cmd, capture_output=True, text=True), out))
        if "--docx" in flags:
            docx = out.with_suffix(".docx")
            codes.append(_report(subprocess.run(common + ["-o", str(docx)], capture_output=True, text=True), docx))
    sys.exit(next((c for c in codes if c), 0))


if __name__ == "__main__":
    main()
