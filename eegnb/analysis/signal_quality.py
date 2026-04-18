"""Pre-recording signal-quality check for dry-electrode EEG devices.

Streams ~10 seconds from the board, then reports per-channel:

* DC offset (uV-equivalent ADC counts — dry electrodes run high).
* Broadband RMS after mean-subtraction.
* Ratio of power in the 50 / 60 Hz line-noise band to surrounding bins.
* Rolling spike count (>5 sigma samples) as an artifact proxy.

Output is a traffic-light verdict per channel so the experimenter
can re-seat a bad electrode before committing to a full session.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np


@dataclass
class ChannelQuality:
    name: str
    dc_offset: float
    rms_uv: float
    line_ratio: float
    n_spikes: int
    verdict: str  # "ok", "warn", "bad"
    notes: list[str] = field(default_factory=list)


@dataclass
class SignalQualityReport:
    duration_s: float
    sfreq_hz: float
    line_freq_hz: float
    channels: list[ChannelQuality]

    def summary(self) -> str:
        lines = [
            f"Signal-quality check: {self.duration_s:.1f}s at "
            f"{self.sfreq_hz} Hz, line freq {self.line_freq_hz} Hz",
        ]
        lines.append(
            f"{'ch':<6}{'DC':>12}{'RMS (µV)':>12}"
            f"{'line ratio':>14}{'spikes':>10}{'verdict':>10}"
        )
        for c in self.channels:
            lines.append(
                f"{c.name:<6}{c.dc_offset:>12.0f}{c.rms_uv:>12.1f}"
                f"{c.line_ratio:>14.2f}{c.n_spikes:>10}{c.verdict:>10}"
            )
        return "\n".join(lines)


def run_signal_quality_check(
    device: str = "unicorn",
    duration_s: float = 10.0,
    line_freq_hz: float = 50.0,
    serial_port: str = "/dev/ttyACM0",
) -> SignalQualityReport:
    """Run a short acquisition and score per-channel quality.

    Thresholds are heuristic: RMS > 500 uV-equivalent and line-ratio
    > 10 both earn a "bad" verdict, spike count > 5 earns "warn".
    Adjust for your device-specific scaling.
    """
    from brainflow.board_shim import (
        BoardIds,
        BoardShim,
        BrainFlowInputParams,
    )

    if device != "unicorn":
        raise NotImplementedError(
            f"signal_quality only wired up for unicorn; got {device!r}"
        )

    params = BrainFlowInputParams()
    params.serial_port = serial_port
    board = BoardShim(BoardIds.UNICORN_BOARD.value, params)
    board.prepare_session()
    board.start_stream()
    time.sleep(duration_s)
    data = board.get_board_data()
    board.stop_stream()
    board.release_session()

    names = BoardShim.get_eeg_names(BoardIds.UNICORN_BOARD.value)
    chan_idxs = BoardShim.get_eeg_channels(BoardIds.UNICORN_BOARD.value)
    sfreq = BoardShim.get_sampling_rate(BoardIds.UNICORN_BOARD.value)

    channels: list[ChannelQuality] = []
    for name, ch in zip(names, chan_idxs):
        trace = data[ch]
        dc = float(np.mean(trace))
        ac = trace - dc
        rms = float(np.sqrt(np.mean(ac**2)))

        # Crude line-noise ratio: PSD peak in [line-2, line+2] vs median.
        freqs = np.fft.rfftfreq(len(ac), d=1.0 / sfreq)
        amp = np.abs(np.fft.rfft(ac)) / len(ac)
        line_mask = np.abs(freqs - line_freq_hz) <= 2.0
        line_amp = float(np.max(amp[line_mask])) if line_mask.any() else 0.0
        baseline = float(np.median(amp[(freqs > 1) & (freqs < 40)]) + 1e-9)
        line_ratio = line_amp / baseline

        spike_thresh = 5.0 * np.std(ac) + 1e-9
        n_spikes = int(np.sum(np.abs(ac) > spike_thresh))

        verdict, notes = _score(rms, line_ratio, n_spikes)
        channels.append(
            ChannelQuality(
                name=name,
                dc_offset=dc,
                rms_uv=rms,
                line_ratio=line_ratio,
                n_spikes=n_spikes,
                verdict=verdict,
                notes=notes,
            )
        )

    actual_duration = float(data.shape[1] / sfreq)
    return SignalQualityReport(
        duration_s=actual_duration,
        sfreq_hz=float(sfreq),
        line_freq_hz=line_freq_hz,
        channels=channels,
    )


def _score(rms: float, line_ratio: float, n_spikes: int) -> tuple[str, list[str]]:
    notes: list[str] = []
    verdict = "ok"
    if line_ratio > 10:
        verdict = "bad"
        notes.append("heavy line noise; reseat electrode or move away from mains")
    elif line_ratio > 5:
        verdict = "warn" if verdict == "ok" else verdict
        notes.append("elevated line noise")
    if rms > 500:
        verdict = "bad"
        notes.append("very high broadband RMS; likely loose contact")
    elif rms > 100:
        verdict = "warn" if verdict == "ok" else verdict
        notes.append("elevated broadband RMS")
    if n_spikes > 20:
        verdict = "warn" if verdict == "ok" else verdict
        notes.append(f"{n_spikes} large excursions; motion or blink artifact")
    return verdict, notes
