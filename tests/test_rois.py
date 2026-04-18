"""Unit tests for eegnb.utils.rois."""

import pytest

from eegnb.utils.rois import channel_names_for_device, resolve_roi


def test_unicorn_channel_order():
    names = channel_names_for_device("unicorn")
    assert names == ["Fz", "C3", "Cz", "C4", "Pz", "PO7", "Oz", "PO8"]


def test_resolve_roi_matches_channels():
    roi = resolve_roi(("PO8", "Oz", "PO7"), "unicorn")
    assert roi == {"PO8": 7, "Oz": 6, "PO7": 5}


def test_resolve_roi_silently_drops_missing():
    roi = resolve_roi(("Oz", "P10"), "unicorn")  # P10 isn't on Unicorn
    assert roi == {"Oz": 6}


def test_unknown_device_raises():
    with pytest.raises(ValueError):
        channel_names_for_device("not-a-real-device")
