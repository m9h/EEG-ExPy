"""Measured frequency-domain analysis for frequency-tagged EEG paradigms.

Where :mod:`eegnb.analysis.power` answers *design* questions ("will I see it?
is my design well-conditioned?"), this module analyses *recorded* data: it
turns an epoch of EEG into an amplitude spectrum and a baseline-corrected
signal-to-noise (SNR) spectrum, and reads out the response at specific tag
frequencies and their harmonics. It is the analysis counterpart to the
SSVEP, FPVS (Stothart/Rossion) and SSVEP-retinotopy paradigms.

The SNR convention follows the steady-state / FPVS literature (Norcia,
Appelbaum, Ales, Cottereau & Rossion 2015; the FreqTag toolbox, Peykarjou
et al. 2022): the response at a bin is divided by the mean amplitude of a
set of neighbouring "noise" bins, skipping a few immediately-adjacent guard
bins so spectral leakage from the peak does not inflate the noise estimate.
A z-score against the same neighbours is also provided.

All functions are plain NumPy on a 1-D signal (single channel/epoch) or a
2-D ``(n_channels, n_samples)`` array; they make no assumption about the
recording backend. For a real recording, band-pass/notch-filter and detrend
before calling these.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


def amplitude_spectrum(
    data: np.ndarray, sfreq: float
) -> tuple[np.ndarray, np.ndarray]:
    """Single-sided amplitude spectrum of a 1-D signal.

    Returns ``(freqs, amplitude)`` where ``amplitude[k]`` is the amplitude
    (in the signal's units) of a sinusoid at ``freqs[k]`` — i.e. a pure
    ``A*sin(2*pi*f*t)`` landing on bin ``k`` gives ``amplitude[k] ≈ A``.
    """
    data = np.asarray(data, dtype=float)
    n = data.shape[-1]
    if n < 2:
        raise ValueError("need at least 2 samples")
    spec = np.fft.rfft(data)
    amp = np.abs(spec) * 2.0 / n
    amp[0] /= 2.0  # DC is not doubled
    if n % 2 == 0:  # Nyquist bin (present only for even n) is not doubled
        amp[-1] /= 2.0
    freqs = np.fft.rfftfreq(n, d=1.0 / sfreq)
    return freqs, amp


def _noise_indices(
    k: int, n_bins: int, n_neighbors: int, n_guard: int
) -> np.ndarray:
    """Indices of the neighbouring noise bins around bin ``k`` (both sides),
    skipping ``n_guard`` bins immediately adjacent to ``k`` and clipped to
    the valid range."""
    lo = np.arange(k - n_guard - n_neighbors, k - n_guard)
    hi = np.arange(k + n_guard + 1, k + n_guard + 1 + n_neighbors)
    idx = np.concatenate([lo, hi])
    return idx[(idx >= 0) & (idx < n_bins)]


def snr_spectrum(
    data: np.ndarray,
    sfreq: float,
    n_neighbors: int = 10,
    n_guard: int = 1,
) -> tuple[np.ndarray, np.ndarray]:
    """Baseline-corrected SNR spectrum.

    ``snr[k] = amplitude[k] / mean(amplitude of neighbouring noise bins)``.
    A flat (pure-noise) spectrum sits near 1.0; a tagged response rises well
    above it. Bins without enough neighbours (spectrum edges) are ``nan``.
    """
    freqs, amp = amplitude_spectrum(data, sfreq)
    n_bins = amp.shape[0]
    snr = np.full(n_bins, np.nan)
    for k in range(n_bins):
        idx = _noise_indices(k, n_bins, n_neighbors, n_guard)
        if idx.size == 0:
            continue
        noise = amp[idx].mean()
        snr[k] = amp[k] / noise if noise > 0 else np.nan
    return freqs, snr


@dataclass
class HarmonicResponse:
    """Response at one harmonic of a tag frequency."""

    harmonic: int
    freq_hz: float
    amplitude: float
    noise_mean: float
    noise_std: float
    snr: float          # amplitude / noise_mean
    z: float            # (amplitude - noise_mean) / noise_std
    baseline_corrected: float  # amplitude - noise_mean


@dataclass
class TagResponse:
    """Full response at a tag frequency and its harmonics."""

    tag_hz: float
    freq_resolution_hz: float
    harmonics: list[HarmonicResponse] = field(default_factory=list)
    summed_baseline_corrected: float = 0.0  # sum over harmonics (Rossion)

    @property
    def fundamental_snr(self) -> float:
        return self.harmonics[0].snr if self.harmonics else float("nan")


def tag_response(
    data: np.ndarray,
    sfreq: float,
    tag_hz: float,
    n_harmonics: int = 1,
    n_neighbors: int = 10,
    n_guard: int = 1,
) -> TagResponse:
    """Response at ``tag_hz`` and its first ``n_harmonics`` harmonics.

    The summed baseline-corrected amplitude (sum of ``amplitude -
    noise_mean`` over harmonics) is the standard FPVS "harmonic sum"
    quantification of the total periodic response.
    """
    freqs, amp = amplitude_spectrum(data, sfreq)
    res = freqs[1] - freqs[0]
    n_bins = amp.shape[0]

    out = TagResponse(tag_hz=tag_hz, freq_resolution_hz=res)
    for h in range(1, n_harmonics + 1):
        fh = tag_hz * h
        k = int(round(fh / res))
        if k >= n_bins:
            break
        idx = _noise_indices(k, n_bins, n_neighbors, n_guard)
        noise = amp[idx]
        noise_mean = float(noise.mean()) if noise.size else float("nan")
        noise_std = float(noise.std(ddof=1)) if noise.size > 1 else float("nan")
        a = float(amp[k])
        out.harmonics.append(
            HarmonicResponse(
                harmonic=h,
                freq_hz=float(freqs[k]),
                amplitude=a,
                noise_mean=noise_mean,
                noise_std=noise_std,
                snr=(a / noise_mean) if noise_mean > 0 else float("nan"),
                z=((a - noise_mean) / noise_std)
                if noise_std and noise_std > 0 else float("nan"),
                baseline_corrected=a - noise_mean,
            )
        )
    out.summed_baseline_corrected = float(
        sum(h.baseline_corrected for h in out.harmonics)
    )
    return out


@dataclass
class SectorReadout:
    """Per-sector SNR across channels for an SSVEP-retinotopy block."""

    name: str
    tag_hz: float
    per_channel_snr: np.ndarray
    peak_channel: int
    peak_snr: float


def sector_snr(
    data: np.ndarray,
    sfreq: float,
    sector_freqs: dict[str, float],
    channel_names: list[str] | None = None,
    n_harmonics: int = 1,
    n_neighbors: int = 10,
    n_guard: int = 1,
) -> dict[str, SectorReadout]:
    """Per-sector SSVEP SNR across channels for a multiplex retinotopy block.

    ``data`` is ``(n_channels, n_samples)``. For each sector's tag frequency
    the SNR (summed over harmonics if ``n_harmonics`` > 1) is computed on
    every channel; the channel with the largest SNR is the topographic peak
    for that sector — the coarse-retinotopy read-out (which occipital
    electrode a given field position drives most).
    """
    data = np.asarray(data, dtype=float)
    if data.ndim != 2:
        raise ValueError("data must be 2-D (n_channels, n_samples)")
    n_ch = data.shape[0]

    out: dict[str, SectorReadout] = {}
    for name, f in sector_freqs.items():
        snrs = np.empty(n_ch)
        for c in range(n_ch):
            tr = tag_response(
                data[c], sfreq, f, n_harmonics=n_harmonics,
                n_neighbors=n_neighbors, n_guard=n_guard,
            )
            # Sum harmonic SNRs so a response spread across harmonics still
            # scores; for n_harmonics=1 this is just the fundamental SNR.
            snrs[c] = float(np.nansum([h.snr for h in tr.harmonics]))
        peak = int(np.argmax(snrs))
        out[name] = SectorReadout(
            name=name,
            tag_hz=f,
            per_channel_snr=snrs,
            peak_channel=peak,
            peak_snr=float(snrs[peak]),
        )
    return out
