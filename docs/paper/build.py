"""Build the LiftPilot paper with the Typst compiler bundled in the ``typst`` wheel.

    .\\.venv\\Scripts\\python.exe docs\\paper\\build.py [--no-png]

Writes ``docs/paper/LiftPilot_IEEE.pdf`` and, unless ``--no-png`` is given, one PNG per page
into ``docs/_scratch/paper_pages`` for a visual check. No network, no LaTeX. The build fails
on any compiler warning (for example a missing font), so a silent fallback cannot slip through.
"""

from __future__ import annotations

import sys
from pathlib import Path

import typst

HERE = Path(__file__).resolve().parent
DOCS = HERE.parent
SRC = HERE / "paper.typ"
PDF = HERE / "LiftPilot_IEEE.pdf"
PAGES = DOCS / "_scratch" / "paper_pages"


def main() -> int:
    result = typst.compile_with_warnings(str(SRC), root=str(DOCS))
    pdf, warnings = result if isinstance(result, tuple) else (result, [])
    for w in warnings:
        print("WARNING:", getattr(w, "message", w))
    PDF.write_bytes(pdf)
    print(f"wrote {PDF} ({len(pdf):,} bytes)")

    if "--no-png" not in sys.argv:
        PAGES.mkdir(parents=True, exist_ok=True)
        for old in PAGES.glob("page-*.png"):
            old.unlink()
        typst.compile(
            str(SRC), output=str(PAGES / "page-{n}.png"), root=str(DOCS), format="png", ppi=110
        )
        pages = sorted(PAGES.glob("page-*.png"))
        print(f"rendered {len(pages)} page images into {PAGES}")
    return 1 if warnings else 0


if __name__ == "__main__":
    raise SystemExit(main())
