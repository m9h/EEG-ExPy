"""Subject-specific baseline spectral analysis.

Given a short resting-state EEG recording (brainflow CSV or a numpy
array), fit FOOOF/specparam to identify each channel's aperiodic
1/f background plus periodic peaks — alpha, beta, anything else the
subject carries into the session. The output is then used by
`eegnb.analysis.power.check_paradigm_collisions` to flag FPVS tag
frequencies that would collide with the subject's endogenous rhythms.

Protocol: record ~2 minutes of eyes-open resting state while the
subject looks at a fixation cross, then pass the CSV to
`fit_resting_peaks`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class SpectralPeak:
    """A single periodic peak extracted by FOOOF.

    Attributes
    ----------
    channel : str
        Which EEG channel it came from.
    centre_hz : float
        Peak centre frequency.
    power : float
        Peak power (log10(uV^2/Hz) above the aperiodic component).
    bandwidth_hz : float
        Peak full-width at half-max (in Hz).
    """

    channel: str
    centre_hz: float
    power: float
    bandwidth_hz: float


@dataclass
class PeakProfile:
    """Per-subject spectral profile summarising their baseline EEG."""

    channels: list[str]
    aperiodic_offset: dict[str, float] = field(default_factory=dict)
    aperiodic_exponent: dict[str, float] = field(default_factory=dict)
    peaks: list[SpectralPeak] = field(default_factory=list)
    sfreq_hz: float = 0.0
    duration_s: float = 0.0

    def peaks_in_band(self, low: float, high: float) -> list[SpectralPeak]:
        return [p for p in self.peaks if low <= p.centre_hz <= high]

    @property
    def alpha_peaks(self) -> list[SpectralPeak]:
        return self.peaks_in_band(7.0, 14.0)

    @property
    def beta_peaks(self) -> list[SpectralPeak]:
        return self.peaks_in_band(14.0, 30.0)


def fit_resting_peaks(
    csv_path: str | Path,
    channels: list[str] | None = None,
    band: tuple[float, float] = (1.0, 45.0),
    peak_width_limits: tuple[float, float] = (1.0, 8.0),
    max_n_peaks: int = 6,
    min_peak_height: float = 0.05,
    peak_threshold: float = 2.0,
) -> PeakProfile:
    """Fit FOOOF to each channel of a resting-state recording.

    Parameters
    ----------
    csv_path : path
        A brainflow-format CSV with columns ``timestamps,
        <channel>..., stim``.
    channels : list[str] | None
        Subset of channels to analyse. Defaults to all EEG channels
        (everything except ``timestamps`` and ``stim``).
    band : (low, high)
        Frequency range for the FOOOF fit.
    peak_width_limits : (low, high)
        Passed through to FOOOF.
    max_n_peaks, min_peak_height, peak_threshold : FOOOF knobs.

    Returns
    -------
    PeakProfile
    """
    try:
        from fooof import FOOOF
    except ImportError as exc:  # pragma: no cover - optional dep
        raise ImportError(
            "fooof / specparam is required. Install with: "
            "uv pip install 'eeg-expy[analysis]' or "
            "uv pip install fooof"
        ) from exc

    import pandas as pd
    from scipy.signal import welch

    df = pd.read_csv(csv_path)
    timestamps = df["timestamps"].to_numpy()
    if "stim" in df.columns:
        eeg_cols = [
            c for c in df.columns if c not in ("timestamps", "stim")
        ]
    else:
        eeg_cols = [c for c in df.columns if c != "timestamps"]

    if channels is not None:
        eeg_cols = [c for c in eeg_cols if c in channels]
        if not eeg_cols:
            raise ValueError(
                f"None of the requested channels {channels} are in the CSV."
            )

    sfreq = float(round(1.0 / np.median(np.diff(timestamps))))
    duration = float(timestamps[-1] - timestamps[0])

    profile = PeakProfile(
        channels=eeg_cols, sfreq_hz=sfreq, duration_s=duration
    )

    nperseg = min(int(sfreq * 4), len(df))  # ~4 s Welch segments

    for name in eeg_cols:
        trace = df[name].to_numpy() - df[name].mean()
        freqs, psd = welch(trace, fs=sfreq, nperseg=nperseg)
        mask = (freqs >= band[0]) & (freqs <= band[1])
        fm = FOOOF(
            peak_width_limits=peak_width_limits,
            max_n_peaks=max_n_peaks,
            min_peak_height=min_peak_height,
            peak_threshold=peak_threshold,
            verbose=False,
        )
        fm.fit(freqs[mask], psd[mask], band)

        profile.aperiodic_offset[name] = float(fm.aperiodic_params_[0])
        profile.aperiodic_exponent[name] = float(fm.aperiodic_params_[-1])
        for cf, pw, bw in fm.peak_params_:
            profile.peaks.append(
                SpectralPeak(
                    channel=name,
                    centre_hz=float(cf),
                    power=float(pw),
                    bandwidth_hz=float(bw),
                )
            )
    return profile
