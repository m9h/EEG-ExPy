"""Fetch and prepare third-party stimulus sets used by the FPVS paradigms.

Two canonical sets:

* Bank of Standardised Stimuli (BOSS) — Brodeur et al 2010/2014; used
  by Stothart Fastball for recognition-memory objects.
* Chicago Face Database (CFD) — Ma, Correll, Wittenbrink 2015; the
  free face set most often used with Rossion-style FPVS once Liu-Shuang's
  non-distributable in-house identities are ruled out.

BOSS is publicly distributable and can be fetched automatically. CFD
requires registration on chicagofaces.org; our helper assumes the
user has downloaded the archive themselves and only handles the
extract / filter / preprocess step afterwards.

Every function here has side effects on the local filesystem; none
makes network calls other than `fetch_boss`, which pulls from
Figshare.
"""

from __future__ import annotations

import os
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path

# --- BOSS ---------------------------------------------------------------

# BOSS Phase II (930 normative photos) on PLOS Figshare:
BOSS_FIGSHARE_URL = (
    "https://plos.figshare.com/ndownloader/files/1635581"
)
BOSS_PROJECT_PAGE = (
    "https://plos.figshare.com/articles/dataset/"
    "_Bank_of_Standardized_Stimuli_BOSS_Phase_II_930_New_Normative_Photos_/"
    "1168008"
)


def fetch_boss(
    out_dir: str | os.PathLike | None = None, overwrite: bool = False
) -> Path:
    """Download BOSS Phase II from Figshare.

    Parameters
    ----------
    out_dir : path | None
        Where to extract the archive. Defaults to
        `eegnb/stimuli/visual/boss_v2/` in the installed package so
        paradigm code can find the images via
        `eegnb.stimuli.BOSS_V2`.
    overwrite : bool
        If True, re-download even if the output directory is populated.

    Returns
    -------
    Path
        Directory containing the extracted images.
    """
    if out_dir is None:
        from eegnb.stimuli import FACE_HOUSE

        # Default alongside the bundled face_house stim dir.
        out_dir = Path(FACE_HOUSE).parent / "boss_v2"
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    zip_path = out_dir / "boss_phase2.zip"
    if not zip_path.exists() or overwrite:
        _download(BOSS_FIGSHARE_URL, zip_path)

    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(out_dir)

    # Leave the zip in place; the user can delete it after confirming.
    return out_dir


# --- CFD ----------------------------------------------------------------

@dataclass
class CFDPreparation:
    source_zip: Path
    out_dir: Path
    n_neutral_frontals: int
    identities: list[str]
    notes: list[str]


def prepare_cfd(
    cfd_zip_path: str | os.PathLike,
    out_dir: str | os.PathLike | None = None,
    greyscale: bool = True,
    crop_external: bool = True,
    target_size_px: int = 512,
    overwrite: bool = False,
) -> CFDPreparation:
    """Extract Rossion-ready faces from a Chicago Face Database archive.

    CFD distributes a zip (e.g. `CFD Version 3.0.0.zip`) containing
    one directory per identity with multiple expression variants:

        CFD-AM-201-076-N.jpg     # neutral frontal
        CFD-AM-201-076-HO.jpg    # happy open
        CFD-AM-201-076-A.jpg     # angry
        ...

    We pull out only the `*-N.jpg` (neutral-frontal) files, optionally
    greyscale, crop to roughly exclude hair/ears (Rossion's spec),
    and resize to a square `target_size_px`. Output filenames preserve
    the CFD identity slug so provenance is clear.

    Requires Pillow at runtime.

    Parameters
    ----------
    cfd_zip_path : path
        Local path to the CFD release zip.
    out_dir : path | None
        Where to write the prepared images. Defaults to
        `eegnb/stimuli/visual/cfd_neutral/`.
    greyscale : bool
        If True (default), convert to luminance-normalised greyscale.
    crop_external : bool
        If True (default), centre-crop the image to a 0.8 × 0.8 square
        of its shorter edge, which roughly excludes hair and ears for
        CFD's frontal framing. Not a face-segmentation oracle.
    target_size_px : int
        Final square side length in pixels.
    overwrite : bool
        If True, re-process even if out_dir already has neutral images.
    """
    from PIL import Image, ImageOps

    cfd_zip_path = Path(cfd_zip_path).resolve()
    if out_dir is None:
        from eegnb.stimuli import FACE_HOUSE

        out_dir = Path(FACE_HOUSE).parent / "cfd_neutral"
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    already_prepared = list(out_dir.glob("CFD-*.jpg"))
    if already_prepared and not overwrite:
        return CFDPreparation(
            source_zip=cfd_zip_path,
            out_dir=out_dir,
            n_neutral_frontals=len(already_prepared),
            identities=sorted(
                {p.name.rsplit("-", 1)[0] for p in already_prepared}
            ),
            notes=["already prepared; pass overwrite=True to redo"],
        )

    identities: set[str] = set()
    written = 0
    notes: list[str] = []

    with zipfile.ZipFile(cfd_zip_path) as zf:
        neutral_names = [
            n for n in zf.namelist()
            if n.endswith("-N.jpg") and not n.startswith("__MACOSX")
        ]
        if not neutral_names:
            raise RuntimeError(
                "no neutral-frontal images (*-N.jpg) found in archive; "
                "is this a CFD release?"
            )
        for member in neutral_names:
            with zf.open(member) as src:
                img = Image.open(src).convert("RGB")
                if crop_external:
                    img = _centre_crop(img, fraction=0.8)
                if greyscale:
                    img = ImageOps.grayscale(img)
                    img = ImageOps.autocontrast(img)
                img = img.resize(
                    (target_size_px, target_size_px), Image.LANCZOS
                )
                stem = Path(member).stem  # CFD-AM-201-076-N
                identity = stem.rsplit("-", 1)[0]
                identities.add(identity)
                img.save(out_dir / f"{stem}.jpg", quality=92)
                written += 1

    return CFDPreparation(
        source_zip=cfd_zip_path,
        out_dir=out_dir,
        n_neutral_frontals=written,
        identities=sorted(identities),
        notes=notes,
    )


# --- helpers ------------------------------------------------------------

def _download(url: str, dest: Path) -> None:
    import urllib.request

    req = urllib.request.Request(
        url, headers={"User-Agent": "eegnb-stimuli-fetcher/0.3"}
    )
    with urllib.request.urlopen(req) as resp, open(dest, "wb") as fh:
        shutil.copyfileobj(resp, fh)


def _centre_crop(img, fraction: float):
    from PIL import Image  # noqa: F401

    w, h = img.size
    side = int(min(w, h) * fraction)
    left = (w - side) // 2
    top = (h - side) // 2
    return img.crop((left, top, left + side, top + side))
