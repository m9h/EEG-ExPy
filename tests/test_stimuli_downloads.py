"""Tests for eegnb.stimuli.downloads.

TDD-minded: each test states a behaviour before the implementation
has to honour it.
"""

import zipfile
from pathlib import Path

import pytest

from eegnb.stimuli.downloads import fetch_boss


def test_fetch_boss_rejects_non_zip(tmp_path, monkeypatch):
    """If the download step writes a non-zip file, fetch_boss must
    raise instead of silently "extracting" nothing.

    Regression: empty files returned by a failing CDN previously
    produced an uncaught `BadZipFile` from inside extractall.
    """
    def fake_gdown_download(id=None, output=None, quiet=True):
        Path(output).write_text("<html>404</html>")

    import eegnb.stimuli.downloads as dl
    dummy = type("G", (), {"download": staticmethod(fake_gdown_download)})
    monkeypatch.setattr(dl, "gdown", dummy, raising=False)
    monkeypatch.setitem(__import__("sys").modules, "gdown", dummy)

    with pytest.raises(RuntimeError, match="not a zip"):
        fetch_boss(out_dir=tmp_path, overwrite=True)


def test_fetch_boss_extracts_valid_zip(tmp_path, monkeypatch):
    """Given a valid zip at the download destination, fetch_boss must
    extract it and return the extraction directory."""
    import eegnb.stimuli.downloads as dl

    def fake_gdown_download(id=None, output=None, quiet=True):
        with zipfile.ZipFile(output, "w") as zf:
            zf.writestr("object1.jpg", b"\xff\xd8\xff\xe0fake jpg data")
            zf.writestr("object2.jpg", b"\xff\xd8\xff\xe0more jpg data")

    dummy = type("G", (), {"download": staticmethod(fake_gdown_download)})
    monkeypatch.setattr(dl, "gdown", dummy, raising=False)
    monkeypatch.setitem(__import__("sys").modules, "gdown", dummy)

    out = fetch_boss(out_dir=tmp_path, overwrite=True)
    assert out == tmp_path
    assert (tmp_path / "object1.jpg").exists()
    assert (tmp_path / "object2.jpg").exists()
