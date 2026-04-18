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

Every function here has side effects on the local filesystem; only
`fetch_boss` makes network calls, via `gdown` to Google Drive
(because the BOSS archive is hosted there rather than at a plain
HTTP endpoint).
"""

from __future__ import annotations

import os
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path

# --- BOSS ---------------------------------------------------------------

# Canonical BOSS project page; the Figshare mirror only holds the
# supplementary PDFs, not the image archive. The authors distribute
# the actual images via a Google Drive link advertised on the project
# site.
BOSS_PROJECT_PAGE = "https://sites.google.com/site/bosstimuli/"

# Google Drive file id of the BOSS archive. Hard-coded as the default;
# pass `gdrive_id=...` to override if the authors move the file.
BOSS_GDRIVE_ID = "1FpnEFkbqe_huRwfsCf7gs5R1zuc1ZOkn"


def fetch_boss(
    out_dir: str | os.PathLike | None = None,
    overwrite: bool = False,
    gdrive_id: str | None = None,
) -> Path:
    """Download the BOSS image archive from Google Drive via gdown.

    Google Drive's "confirm download for large file" handshake is not
    compatible with a naive urlopen; we delegate to ``gdown`` which
    already knows the dance. ``gdown`` is a base dependency of the
    package (used to fetch example datasets elsewhere).

    Parameters
    ----------
    out_dir : path | None
        Where to extract the archive. Defaults to
        `eegnb/stimuli/visual/boss_v2/`.
    overwrite : bool
        If True, re-download even if the output directory is populated.
    gdrive_id : str | None
        Override the hard-coded Google Drive file id.
    """
    try:
        import gdown
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "gdown is required to fetch BOSS. "
            "Install with: uv pip install gdown"
        ) from exc

    if out_dir is None:
        from eegnb.stimuli import FACE_HOUSE

        out_dir = Path(FACE_HOUSE).parent / "boss_v2"
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    zip_path = out_dir / "boss.zip"
    if not zip_path.exists() or overwrite or zip_path.stat().st_size == 0:
        gdown.download(
            id=gdrive_id or BOSS_GDRIVE_ID,
            output=str(zip_path),
            quiet=False,
        )

    if not zipfile.is_zipfile(zip_path):
        raise RuntimeError(
            f"downloaded file at {zip_path} is not a zip; "
            "the Google Drive id may have changed. See "
            f"{BOSS_PROJECT_PAGE} for the current location."
        )

    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(out_dir)

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
