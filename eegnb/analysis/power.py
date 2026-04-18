"""Power / design-efficiency analysis for frequency-tagged EEG paradigms.

Two complementary framings, each answering a different design question.

1. `fpvs_detection_power(...)`
   Analytical narrow-band detection power. Given an expected oddball
   amplitude and a noise-floor estimate, returns the expected z-score
   against neighbouring bins, the detection probability at a chosen
   alpha, and the minimum recording duration needed to hit a target
   power. This is the "am I going to see it?" question.

2. `design_efficiency(...)`
   FEAT-style GLM efficiency. Builds a sine/cosine regression matrix
   X for the base rate, the oddball fundamental, and chosen harmonics,
   computes diag((X'X)^-1), and returns per-contrast efficiencies.
   Useful for comparing designs — e.g. does including a 3rd harmonic
   add information beyond the 2nd? This is the "is my design well-
   conditioned?" question.

The analytical model is a pragmatic engineering approximation:
y(t) = A * sin(2 pi f_target t) + n(t), n(t) bandpass-filtered
Gaussian with RMS sigma in the analysis band. The resulting z-score
formula

    z ~= (A / sigma) * sqrt(H * T * fs / 2)

rests on Parseval plus a white-noise-within-band assumption, neither
of which is strictly true for EEG. Treat the outputs as order-of-
magnitude predictions, not statistical guarantees. For strict sample-
size planning, validate against a pilot recording's measured
sigma on the target subject / device.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.stats import norm


# Literature-informed defaults. These are rough — real values vary by
# subject, montage, and electrode wetness. See `PowerInputs.notes` in
# each paradigm's `predicted_power()` for paradigm-specific guidance.
DEFAULTS = {
    # Expected oddball amplitude in uV at a single harmonic, wet
    # montage. The dry-electrode factor applies a further discount.
    "expected_amp_uv_rossion": 1.0,
    "expected_amp_uv_stothart": 0.8,
    # Time-domain RMS of band-limited EEG (uV) in the analysis band
    # (0.5 - 10 Hz) after a standard notch + bandpass.
    "noise_rms_uv_wet": 8.0,
    "noise_rms_uv_dry": 15.0,
    # Empirical attenuation factor for dry-electrode amplitudes at
    # occipito-temporal sites relative to a published 64-ch wet
    # montage. Rough value; calibrate per device.
    "dry_amplitude_factor": 0.4,
    # Two-sided alpha for z-threshold.
    "alpha": 0.05,
}


@dataclass
class DetectionPower:
    """Result of an FPVS narrow-band detection-power calculation."""

    duration_s: float
    base_hz: float
    oddball_hz: float
    n_harmonics: int
    expected_amp_uv: float
    noise_rms_uv: float
    alpha: float
    z_expected: float
    power: float
    z_threshold: float
    min_duration_for_power_0_8: float
    notes: list[str] = field(default_factory=list)


def fpvs_detection_power(
    duration_s: float,
    base_hz: float,
    oddball_hz: float,
    n_harmonics: int = 4,
    expected_amp_uv: float = 1.0,
    noise_rms_uv: float = 10.0,
    sfreq_hz: float = 250.0,
    alpha: float = 0.05,
    dry_electrode_factor: float | None = None,
) -> DetectionPower:
    """Analytical FPVS oddball detection power.

    Parameters
    ----------
    duration_s : float
        Planned recording duration (s). Only the portion that contains
        an integer number of oddball cycles counts; if duration isn't
        aligned we floor to that.
    base_hz : float
        Base stimulation rate (Hz). Used only for documentation in the
        returned object.
    oddball_hz : float
        Oddball frequency (Hz). Target of the detection.
    n_harmonics : int
        Number of harmonics assumed to contribute independently
        (the oddball fundamental counts as the first harmonic).
    expected_amp_uv : float
        Expected amplitude of the oddball response at a single harmonic
        in microvolts (wet-montage scale).
    noise_rms_uv : float
        Expected time-domain RMS of the band-limited EEG in the
        analysis band (uV).
    sfreq_hz : float
        Sample rate of the acquisition.
    alpha : float
        Two-sided significance threshold.
    dry_electrode_factor : float | None
        If supplied, multiplies `expected_amp_uv` by this factor to
        model the amplitude attenuation seen with dry contacts.
        Typical value 0.3 - 0.5.

    Returns
    -------
    DetectionPower
    """
    amp = expected_amp_uv
    notes: list[str] = []
    if dry_electrode_factor is not None:
        amp = amp * dry_electrode_factor
        notes.append(
            f"amplitude attenuated by {dry_electrode_factor:.2f} "
            "for dry electrodes"
        )

    # Crop to integer oddball cycles so the FFT has a bin exactly at
    # the target frequency. This is what a correct analysis would do;
    # we report the cropped duration.
    cycle_s = 1.0 / oddball_hz
    n_cycles = int(duration_s / cycle_s)
    usable_duration = n_cycles * cycle_s
    if usable_duration < duration_s - 1e-6:
        notes.append(
            f"cropping to {n_cycles} oddball cycles "
            f"({usable_duration:.2f} s)"
        )

    # Core analytical z-score: narrow-band coherent integration gives
    # signal amplitude proportional to T; incoherent noise gives
    # amplitude proportional to sqrt(T). Summing H harmonics adds H x
    # to the signal power. We apply a 1/sqrt(2) factor coming from the
    # one-sided spectrum normalisation.
    z = (amp / noise_rms_uv) * np.sqrt(
        n_harmonics * usable_duration * sfreq_hz / 2.0
    )
    z_threshold = norm.ppf(1.0 - alpha / 2.0)
    power = float(norm.cdf(z - z_threshold))

    # Invert for minimum T at 0.8 power.
    z_80 = norm.ppf(0.8) + z_threshold
    required_cycles = np.ceil(
        (z_80 / ((amp / noise_rms_uv))) ** 2 * 2.0
        / (n_harmonics * sfreq_hz)
        * oddball_hz
    )
    min_duration_80 = float(required_cycles) / oddball_hz

    return DetectionPower(
        duration_s=float(usable_duration),
        base_hz=base_hz,
        oddball_hz=oddball_hz,
        n_harmonics=n_harmonics,
        expected_amp_uv=amp,
        noise_rms_uv=noise_rms_uv,
        alpha=alpha,
        z_expected=float(z),
        power=power,
        z_threshold=float(z_threshold),
        min_duration_for_power_0_8=min_duration_80,
        notes=notes,
    )


@dataclass
class DesignEfficiency:
    """Result of a FEAT-style GLM design-efficiency analysis."""

    frequencies_hz: list[float]
    efficiencies: dict[str, float]
    condition_number: float
    notes: list[str] = field(default_factory=list)


def design_efficiency(
    duration_s: float,
    sfreq_hz: float,
    base_hz: float,
    oddball_hz: float,
    n_base_harmonics: int = 2,
    n_oddball_harmonics: int = 4,
) -> DesignEfficiency:
    """FEAT-style design-efficiency analysis for an FPVS design.

    Builds a cosine/sine regression matrix X with columns for the base
    rate, oddball fundamental, and their harmonics. Computes
    diag((X'X)^-1) and returns per-frequency efficiency
    (= 1 / diag((X'X)^-1)_k). Higher is better.

    The condition number of X'X flags near-rank-deficient designs —
    e.g. when a chosen harmonic collides with another tagged frequency.
    """
    n_samples = int(duration_s * sfreq_hz)
    t = np.arange(n_samples) / sfreq_hz

    freqs: list[tuple[str, float]] = []
    for k in range(1, n_base_harmonics + 1):
        freqs.append((f"base_h{k}_{base_hz*k:.3f}Hz", base_hz * k))
    for k in range(1, n_oddball_harmonics + 1):
        freqs.append(
            (f"odd_h{k}_{oddball_hz*k:.3f}Hz", oddball_hz * k)
        )

    # Each frequency contributes a cosine and a sine column.
    columns = []
    col_names: list[str] = []
    for name, f in freqs:
        columns.append(np.cos(2 * np.pi * f * t))
        col_names.append(name + "_cos")
        columns.append(np.sin(2 * np.pi * f * t))
        col_names.append(name + "_sin")
    X = np.column_stack(columns)

    xtx = X.T @ X
    inv = np.linalg.pinv(xtx)
    diag = np.diag(inv)
    # Report per-frequency efficiency by summing cos+sin efficiency
    # of that pair.
    efficiencies: dict[str, float] = {}
    for i in range(0, X.shape[1], 2):
        name = col_names[i].rsplit("_", 1)[0]
        efficiencies[name] = float(1.0 / (diag[i] + diag[i + 1]))

    cond = float(np.linalg.cond(xtx))
    return DesignEfficiency(
        frequencies_hz=[f for _, f in freqs],
        efficiencies=efficiencies,
        condition_number=cond,
    )


def format_detection_power(result: DetectionPower) -> str:
    """Human-readable one-paragraph summary of a detection-power result."""
    lines = [
        f"FPVS detection power at oddball {result.oddball_hz:.3f} Hz:",
        f"  duration (cropped): {result.duration_s:.2f} s",
        f"  harmonics summed:   {result.n_harmonics}",
        f"  expected amplitude: {result.expected_amp_uv:.2f} uV",
        f"  noise RMS:          {result.noise_rms_uv:.2f} uV",
        f"  alpha:              {result.alpha:.3f}  "
        f"(z threshold = {result.z_threshold:.2f})",
        f"  expected z:         {result.z_expected:.2f}",
        f"  power:              {result.power * 100:.1f}%",
        f"  duration for 0.8:   {result.min_duration_for_power_0_8:.1f} s",
    ]
    for note in result.notes:
        lines.append(f"  note: {note}")
    return "\n".join(lines)
