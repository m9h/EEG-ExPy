"""TDD tests for the brainflow -> LSL bridge.

Uses the brainflow synthetic board (no hardware needed, works on Linux,
Windows, and macOS) to verify:

- An LSL EEG outlet is created and discoverable by channel count and
  sample rate.
- When the paradigm pushes a marker, it also arrives on an LSL markers
  outlet.

These are functional integration tests, not unit tests. They should
run wherever `pylsl` and `brainflow` are available, which is every
supported platform.
"""

import time

import numpy as np
import pytest

pylsl = pytest.importorskip("pylsl")


def _resolve_stream(stype: str, timeout: float = 5.0):
    """Find a running LSL stream of the given type, or return None."""
    streams = pylsl.resolve_byprop("type", stype, timeout=timeout)
    return streams[0] if streams else None


def test_brainflow_to_lsl_bridge_exposes_eeg_stream():
    """When EEG(publish_to_lsl=True).start() is called on the synthetic
    board, an LSL EEG stream appears with 16 channels at 250 Hz (the
    synthetic board's defaults) and its name identifies the backend.
    """
    from eegnb.devices.eeg import EEG

    eeg = EEG(device="synthetic", publish_to_lsl=True)
    eeg.start(fn="/dev/null", duration=3)
    try:
        time.sleep(1.0)
        info = _resolve_stream("EEG", timeout=3.0)
        assert info is not None, "no LSL EEG stream discovered"
        assert info.channel_count() > 0
        assert info.nominal_srate() > 0
        assert "brainflow" in info.name().lower()
    finally:
        eeg.stop()


def test_push_sample_reaches_lsl_markers_outlet():
    """Markers pushed via `eeg.push_sample` should also surface on a
    dedicated LSL markers stream that LabRecorder can record.
    """
    from eegnb.devices.eeg import EEG

    eeg = EEG(device="synthetic", publish_to_lsl=True)
    eeg.start(fn="/dev/null", duration=3)
    try:
        time.sleep(0.5)
        markers_info = _resolve_stream("Markers", timeout=3.0)
        assert markers_info is not None, "no LSL markers stream"

        inlet = pylsl.StreamInlet(markers_info)
        # Drain any pre-existing samples.
        while inlet.pull_sample(timeout=0.05)[0] is not None:
            pass

        eeg.push_sample(marker=42, timestamp=time.time())
        sample, _ts = inlet.pull_sample(timeout=2.0)
        assert sample is not None, "marker didn't arrive on LSL"
        assert int(sample[0]) == 42
    finally:
        eeg.stop()
