"""Turns DOCUMENTATION_V2.md into an Overleaf-ready LaTeX project in docs/documentation-v2/latex/.

The Markdown file is the source of truth (it renders on GitHub). Re-run this after editing it:
    pip install pypandoc_binary
    python docs/documentation-v2/tools/build_latex.py
Then upload the whole latex/ folder to Overleaf and compile DOCUMENTATION_V2.tex with pdfLaTeX.
"""
import re
import shutil
from pathlib import Path

import pypandoc

HERE = Path(__file__).resolve().parents[1]
SOURCE = HERE / "DOCUMENTATION_V2.md"
OUT = HERE / "latex"


def main():
    text = SOURCE.read_text(encoding="utf-8")
    # The first heading and the subtitle line become the LaTeX title page
    title = re.search(r"^# (.+)$", text, re.M).group(1)
    subtitle = re.search(r"^\*\*(.+)\*\*$", text, re.M).group(1)
    body = text.split("\n", 1)[1].replace(f"**{subtitle}**", "", 1)

    OUT.mkdir(exist_ok=True)
    shutil.copytree(HERE / "figures", OUT / "figures", dirs_exist_ok=True)
    pypandoc.convert_text(
        body, "latex", format="gfm", outputfile=str(OUT / "DOCUMENTATION_V2.tex"),
        extra_args=[
            "--standalone", "--toc", "--columns=80", "--shift-heading-level-by=-1",
            f"--metadata=title:{title}", f"--metadata=subtitle:{subtitle}",
            "--metadata=author:Harsh Amberkar, California State University, Monterey Bay",
            "--metadata=date:November 2, 2026",
            "-V", "documentclass=article", "-V", "fontsize=11pt", "-V", "geometry:margin=1in",
            "-V", "colorlinks=true", "-V", "linkcolor=ocean", "-V", "urlcolor=ocean",
            # Same ocean blue as the website; hyperref needs a named colour
            "-V", r"header-includes=\definecolor{ocean}{HTML}{1E5A8A}",
            "-V", "toccolor=black",
        ],
    )
    print("wrote", OUT / "DOCUMENTATION_V2.tex")


if __name__ == "__main__":
    main()
