"""Tests for eegnb.analysis.frequency_tagging.

Synthetic signals with a known tag frequency (chosen to land exactly on an
FFT bin) verify that the amplitude spectrum, SNR spectrum, harmonic
read-out and per-sector topography recover what was put in.
"""

from __future__ import annotations

import numpy as np
import pytest

from eegnb.analysis.frequency_tagging import (
    amplitude_spectrum,
    snr_spectrum,
    tag_response,
    sector_snr,
)


SFREQ = 250.0
DUR = 10.0  # -> 0.1 Hz resolution; integer Hz tags land on a bin


def _t():
    n = int(SFREQ * DUR)
    return np.arange(n) / SFREQ


def _sine(f, amp=1.0, phase=0.0):
    return amp * np.sin(2 * np.pi * f * _t() + phase)


# --- amplitude spectrum ------------------------------------------------------

def test_amplitude_of_pure_sine_recovered():
    freqs, amp = amplitude_spectrum(_sine(10.0, amp=2.0), SFREQ)
    k = np.argmin(np.abs(freqs - 10.0))
    assert freqs[k] == pytest.approx(10.0, abs=1e-6)
    assert amp[k] == pytest.approx(2.0, rel=1e-3)
    # neighbouring bins are ~0 for an on-bin sine
    assert amp[k + 5] < 1e-6


def test_amplitude_spectrum_rejects_tiny_input():
    with pytest.raises(ValueError):
        amplitude_spectrum(np.array([1.0]), SFREQ)


# --- SNR spectrum ------------------------------------------------------------

def test_snr_peaks_at_tag_and_noise_floor_near_one():
    rng = np.random.default_rng(0)
    sig = _sine(12.0, amp=1.0) + 0.1 * rng.standard_normal(int(SFREQ * DUR))
    freqs, snr = snr_spectrum(sig, SFREQ)
    k = np.argmin(np.abs(freqs - 12.0))
    assert snr[k] > 20  # strong tag stands far above neighbours
    # Away from the tag the SNR sits near the noise floor (~1). A single bin
    # is Rayleigh-distributed and noisy, so assert on the band median.
    band = (freqs > 20) & (freqs < 50)
    assert 0.7 < np.nanmedian(snr[band]) < 1.4


# --- harmonic tag response ---------------------------------------------------

def test_tag_response_fundamental_and_harmonic():
    # fundamental at 6 Hz + a 2nd harmonic at 12 Hz
    sig = _sine(6.0, amp=1.0) + _sine(12.0, amp=0.5)
    tr = tag_response(sig, SFREQ, tag_hz=6.0, n_harmonics=2)
    assert len(tr.harmonics) == 2
    assert tr.harmonics[0].freq_hz == pytest.approx(6.0, abs=1e-6)
    assert tr.harmonics[1].freq_hz == pytest.approx(12.0, abs=1e-6)
    assert tr.harmonics[0].amplitude == pytest.approx(1.0, rel=1e-2)
    assert tr.harmonics[1].amplitude == pytest.approx(0.5, rel=1e-2)
    assert tr.fundamental_snr > 20
    # harmonic sum ~= 1.0 + 0.5 (noise_mean ~0 in a clean signal)
    assert tr.summed_baseline_corrected == pytest.approx(1.5, rel=1e-2)


def test_tag_response_absent_tag_has_low_snr():
    rng = np.random.default_rng(1)
    noise = rng.standard_normal(int(SFREQ * DUR))
    tr = tag_response(noise, SFREQ, tag_hz=7.0, n_harmonics=1)
    assert tr.fundamental_snr < 5  # nothing there


def test_tag_response_stops_at_nyquist():
    sig = _sine(10.0)
    tr = tag_response(sig, SFREQ, tag_hz=100.0, n_harmonics=3)  # 200,300 > Nyq
    assert len(tr.harmonics) == 1  # only the 100 Hz fundamental fits


# --- per-sector topography read-out -----------------------------------------

def test_sector_snr_assigns_peak_channel_by_frequency():
    n = int(SFREQ * DUR)
    rng = np.random.default_rng(2)
    # ch0 carries 10 Hz strongly, ch1 carries 15 Hz strongly; both have noise
    ch0 = _sine(10.0, amp=2.0) + 0.1 * rng.standard_normal(n)
    ch1 = _sine(15.0, amp=2.0) + 0.1 * rng.standard_normal(n)
    data = np.vstack([ch0, ch1])
    out = sector_snr(
        data, SFREQ, {"lowerLeft": 10.0, "upperLeft": 15.0}
    )
    assert out["lowerLeft"].peak_channel == 0
    assert out["upperLeft"].peak_channel == 1
    assert out["lowerLeft"].peak_snr > 20
    assert out["upperLeft"].peak_snr > 20


def test_sector_snr_requires_2d():
    with pytest.raises(ValueError):
        sector_snr(_sine(10.0), SFREQ, {"a": 10.0})
