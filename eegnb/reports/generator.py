"""Generate a Pweave-based LaTeX report from a recorded EEG CSV.

Workflow:
    CSV  ->  Pweave (render Python chunks, emit .tex)  ->  pdflatex  ->  PDF

Produces one report per recording. The template branches on the
`paradigm` field so FPVS Stothart, FPVS Rossion and standard SSVEP
recordings each get the analysis section appropriate to their design,
plus shared metadata and signal-quality blocks.

External requirements at runtime:
    * pweave (Python)
    * a working TeX installation providing `pdflatex` (e.g.
      `dnf install texlive-scheme-basic texlive-collection-latexrecommended`
      on Fedora, or the full `texlive-scheme-medium` for broader
      package coverage).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

TEMPLATE_PATH = Path(__file__).parent / "templates" / "report.Pnw"
REVIEW_TEMPLATE_PATH = Path(__file__).parent / "templates" / "review.Pnw"

PARADIGM_ALIASES = {
    "visual-fpvs-stothart": "stothart",
    "visual-fpvs-rossion": "rossion",
    "visual-ssvep": "ssvep",
    "visual-N170": "n170",
    "visual-P300": "p300",
    "auditory-oddball orig": "auditory_oddball",
}


def generate_report(
    csv_path: str | os.PathLike,
    paradigm: str,
    out_dir: str | os.PathLike | None = None,
    device: str = "unicorn",
    run_pdflatex: bool = True,
) -> Path:
    """Render a LaTeX/PDF report for a single recording.

    Parameters
    ----------
    csv_path : path
        The EEG recording CSV (columns: timestamps, <channels...>, stim).
    paradigm : str
        The paradigm name as used in the CLI (e.g. "visual-fpvs-stothart").
    out_dir : path | None
        Directory to write the report into. Defaults to
        `<csv_parent>/report/<csv_stem>/`.
    device : str
        brainflow device identifier; drives channel ordering used in
        plots (default "unicorn").
    run_pdflatex : bool
        If True (default), run pdflatex on the rendered .tex. Disable
        for CI / environments without a TeX install.

    Returns
    -------
    Path to the generated .tex file (or the .pdf if pdflatex ran).
    """
    csv_path = Path(csv_path).resolve()
    if out_dir is None:
        out_dir = csv_path.parent / "report" / csv_path.stem
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    paradigm_tag = PARADIGM_ALIASES.get(paradigm, paradigm.lower())

    pnw_dest = out_dir / "report.Pnw"
    shutil.copy2(TEMPLATE_PATH, pnw_dest)

    # Write a tiny params.json alongside the .Pnw so the template can
    # read its context via stdlib only — no Jinja pre-pass required.
    params = {
        "csv_path": str(csv_path),
        "paradigm": paradigm_tag,
        "paradigm_label": paradigm,
        "device": device,
    }
    (out_dir / "params.json").write_text(_to_json(params))

    tex_path = _run_pweave(pnw_dest, out_dir)

    if run_pdflatex:
        pdf_path = _run_pdflatex(tex_path, out_dir)
        return pdf_path
    return tex_path


def build_review(
    out_dir: str | os.PathLike | None = None,
    run_pdflatex: bool = True,
) -> Path:
    """Render the standalone scholarly review document.

    The review covers the three frequency-tagged EEG paradigms supported
    by this project — SSVEP, Rossion face-FPVS, Stothart Fastball — and
    their applications. It is *not* tied to a specific recording;
    illustrative figures are generated procedurally by the embedded
    Python chunks.

    Parameters
    ----------
    out_dir : path | None
        Target directory. Defaults to `<cwd>/review_build/`.
    run_pdflatex : bool
        If True (default), run pdflatex on the rendered .tex.

    Returns
    -------
    Path to the generated .pdf (or .tex if pdflatex was skipped).
    """
    if out_dir is None:
        out_dir = Path.cwd() / "review_build"
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pnw_dest = out_dir / "review.Pnw"
    shutil.copy2(REVIEW_TEMPLATE_PATH, pnw_dest)

    tex_path = _run_pweave(pnw_dest, out_dir)

    if run_pdflatex:
        return _run_pdflatex(tex_path, out_dir)
    return tex_path


def _run_pweave(pnw_path: Path, cwd: Path) -> Path:
    """Render the .Pnw into a .tex alongside it.

    Uses the in-project `pweave_lite` processor — the upstream `pweave`
    package is broken on Python >=3.11 (imports an IPython API that
    was removed in IPython 8.x). Our subset covers the chunk options
    and conditional blocks that the review and per-run report templates
    actually use.
    """
    from .pweave_lite import weave

    tex_path = pnw_path.with_suffix(".tex")
    return weave(pnw_path, tex_path)


def _run_pdflatex(tex_path: Path, cwd: Path) -> Path:
    """Invoke pdflatex twice to resolve refs. Returns PDF path."""
    cmd = [
        "pdflatex",
        "-interaction=nonstopmode",
        "-halt-on-error",
        str(tex_path.name),
    ]
    # Two passes for cross-reference / table-of-contents stability.
    for _ in range(2):
        subprocess.run(cmd, cwd=cwd, check=True)
    return tex_path.with_suffix(".pdf")


def _to_json(obj) -> str:
    import json

    return json.dumps(obj, indent=2)
