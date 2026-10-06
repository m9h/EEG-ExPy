"""Tests for EEG._prepare_session_with_retry.

BLE boards (Muse, BrainBit) routinely refuse the first prepare_session()
while the adapter settles, which made a working headset look broken. These
tests drive the retry loop with a fake board, so no hardware is needed.
"""

from __future__ import annotations

import pytest

pytest.importorskip("brainflow")

from eegnb.devices.eeg import EEG


class _FakeBoard:
    """prepare_session() fails `fail_times` times, then succeeds."""

    def __init__(self, fail_times: int):
        self.fail_times = fail_times
        self.attempts = 0

    def prepare_session(self):
        self.attempts += 1
        if self.attempts <= self.fail_times:
            raise RuntimeError(f"simulated BLE refusal #{self.attempts}")


def _bare_eeg(board, device_name="muse2_bfn"):
    """An EEG instance with the retry method bound but __init__ bypassed,
    so no real device is touched."""
    eeg = EEG.__new__(EEG)
    eeg.board = board
    eeg.device_name = device_name
    return eeg


def test_succeeds_first_attempt_without_retrying():
    board = _FakeBoard(fail_times=0)
    _bare_eeg(board)._prepare_session_with_retry()
    assert board.attempts == 1


def test_recovers_after_transient_failures():
    # the real-world case: connects on attempt 2
    board = _FakeBoard(fail_times=1)
    _bare_eeg(board)._prepare_session_with_retry()
    assert board.attempts == 2


def test_recovers_near_the_retry_limit():
    board = _FakeBoard(fail_times=EEG.CONNECT_RETRIES - 1)
    _bare_eeg(board)._prepare_session_with_retry()
    assert board.attempts == EEG.CONNECT_RETRIES


def test_raises_after_exhausting_retries(monkeypatch):
    # don't actually sleep 12 x 1.4 s in the test suite
    monkeypatch.setattr("eegnb.devices.eeg.sleep", lambda _s: None)
    board = _FakeBoard(fail_times=EEG.CONNECT_RETRIES + 5)
    eeg = _bare_eeg(board)
    with pytest.raises(RuntimeError, match="could not connect"):
        eeg._prepare_session_with_retry()
    assert board.attempts == EEG.CONNECT_RETRIES


def test_failure_message_names_device_and_wraps_cause(monkeypatch):
    monkeypatch.setattr("eegnb.devices.eeg.sleep", lambda _s: None)
    eeg = _bare_eeg(_FakeBoard(fail_times=999), device_name="muse2_bfn")
    with pytest.raises(RuntimeError) as exc:
        eeg._prepare_session_with_retry()
    assert "muse2_bfn" in str(exc.value)
    assert str(EEG.CONNECT_RETRIES) in str(exc.value)
    # original brainflow error preserved for debugging
    assert exc.value.__cause__ is not None
    assert "simulated BLE refusal" in str(exc.value.__cause__)


def test_retry_delay_is_sane():
    assert EEG.CONNECT_RETRIES >= 3
    assert 0 < EEG.CONNECT_RETRY_DELAY_S <= 5
