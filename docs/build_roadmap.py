#!/usr/bin/env python3
"""Generate roadmap.html from roadmap.md.

roadmap.md is the single source of truth. This script converts it with pandoc,
inlines the figures from figures/*.svg (so the page is self-contained and works
offline), and wraps the result in the stylesheet.

Figures are stored once and used by both formats: the markdown references them as
images, this script inlines the same files. They cannot drift.

Standalone SVGs use fixed mid-tones so they stay legible on GitHub in either theme.
When inlined here they are remapped onto the page's theme tokens.

    python3 docs/build_roadmap.py
"""
import json
import pathlib
import re
import shutil
import subprocess
import sys

DOCS = pathlib.Path(__file__).resolve().parent
MD = DOCS / "roadmap.md"
HTML = DOCS / "roadmap.html"
CSS = DOCS / "roadmap.css"

# standalone SVG palette -> page theme tokens
SVG_THEME = {"#6B7280": "currentColor", "#7C89E8": "var(--accent)",
             "#C0714F": "var(--reverse)"}

HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{desc}">
<meta name="generator" content="docs/build_roadmap.py from docs/roadmap.md">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22%3E%3Ctext y=%22.9em%22 font-size=%2290%22%3E%F0%9F%A7%AC%3C/text%3E%3C/svg%3E">
<title>{title}</title>
<style>
{css}
</style>
</head>
<body>
"""

DESC = ("Architecture and 17-hour build plan for an agent that takes a protein target "
        "and returns structures, chemical matter, and a graded go/no-go on "
        "structure-based design.")


def inline_figures(html: str) -> tuple[str, int]:
    """Replace <img src="figures/x.svg"> with the file's <svg>, themed."""
    count = 0

    def repl(m: re.Match) -> str:
        nonlocal count
        src = m.group("src")
        path = DOCS / src
        if not path.exists():
            print(f"  ! missing figure: {src}", file=sys.stderr)
            return m.group(0)
        svg = path.read_text(encoding="utf-8")
        svg = re.sub(r'\s(?:width|height)="[\d.]+"', "", svg, count=2)
        for a, b in SVG_THEME.items():
            svg = svg.replace(a, b)
        alt = m.group("alt")
        svg = svg.replace("<svg ", f'<svg role="img" aria-label="{alt}" ', 1)
        count += 1
        return svg.strip()

    html = re.sub(
        r'<img\s+src="(?P<src>figures/[^"]+\.svg)"\s+alt="(?P<alt>[^"]*)"\s*/?>',
        repl, html)
    return html, count


def main() -> int:
    if not shutil.which("pandoc"):
        print("pandoc not found — install with: brew install pandoc", file=sys.stderr)
        return 1
    for f in (MD, CSS):
        if not f.exists():
            print(f"missing {f}", file=sys.stderr)
            return 1

    body = subprocess.run(
        ["pandoc", str(MD), "--from", "gfm", "--to", "html5", "--wrap=none"],
        capture_output=True, text=True, check=True).stdout

    body, n = inline_figures(body)

    # a figure plus its italic caption becomes one <figure>
    body = re.sub(
        r'<p>(<svg\b.*?</svg>)</p>\s*<p><em>(.*?)</em></p>',
        lambda m: f"<figure>{m.group(1)}<figcaption>{m.group(2)}</figcaption></figure>",
        body, flags=re.S)

    # tables scroll inside their own container, never the page body
    body = re.sub(r'<table>', '<div class="scroll"><table>', body)
    body = re.sub(r'</table>', '</table></div>', body)

    title = re.search(r"^#\s+(.+)$", MD.read_text(encoding="utf-8"), re.M).group(1)
    title = title.split("—")[-1].strip().title()

    css = CSS.read_text(encoding="utf-8").strip()
    page = '<div class="wrap">\n' + body.strip() + "\n</div>\n"

    HTML.write_text(HEAD.format(css=css, title=title, desc=DESC) + page
                    + "</body>\n</html>\n", encoding="utf-8")
    print(f"wrote {HTML.relative_to(DOCS.parent)}  "
          f"{HTML.stat().st_size:,} bytes  ({n} figures inlined)")

    # The Artifact publisher supplies its own doctype/head/body, so it needs a
    # fragment: title and style only, no document skeleton.
    if "--fragment" in sys.argv:
        out = pathlib.Path(sys.argv[sys.argv.index("--fragment") + 1])
        out.write_text(f"<title>{title}</title>\n<style>\n{css}\n</style>\n{page}",
                       encoding="utf-8")
        print(f"wrote {out}  {out.stat().st_size:,} bytes  (artifact fragment)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
