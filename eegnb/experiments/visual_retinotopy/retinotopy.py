"""SSVEP sector-retinotopy paradigm (frequency-tagged visual field mapping).

Contrast-reversing checkerboard patches are placed in visual-field sectors
(four quadrants by default) around a central fixation. Each sector reverses
at a distinct frequency that is an integer divisor of the monitor refresh
rate, so every tag lands in exactly one FFT bin. The steady-state visual
evoked potential (SSVEP) at each tag frequency — and, crucially, its scalp
topography — indexes the retinotopic position that drove it: upper vs lower
visual field flip the polarity of the early response about the calcarine
(the "cruciform"/C1 sign inversion at Oz), and left vs right hemifield
lateralize to the contralateral occipital electrode.

Two run modes:

* ``mode="multiplex"`` (default) — all sectors flicker simultaneously, each
  at its own frequency, for the whole block. Sectors are separated *by
  frequency* in the spectrum. Fast (one block maps the whole field) and the
  design used by frequency-encoded EEG retinotopy (e.g. Xu et al. 2019).
* ``mode="sequential"`` — one sector flickers per block, cycling through
  sectors across blocks. The active sector's SSVEP topography is read
  directly with no inter-modulation, which is the more robust readout on a
  low-density occipital montage.

Scope / honesty note
--------------------
This delivers *coarse* (quadrant / hemifield) retinotopy on a low-density
occipital montage. It is deliberately **not** population-receptive-field
(pRF) mapping: standalone scalp-EEG lacks the spatial specificity to
estimate pRF position+size. True pRF work is fMRI/ECoG, or MEG using an
fMRI-derived forward model (Kupers, Benson & Winawer 2021, NeuroImage). Do
not label this paradigm's output "pRF".

Design lineage
--------------
* SSVEP methods & frequency-domain analysis conventions (harmonics,
  complex-plane vector averaging, SNR vs neighbouring bins): Norcia,
  Appelbaum, Ales, Cottereau & Rossion (2015), J Vision 15(6):4.
* Tiling the visual field with independently-tagged sectors follows the
  multifocal-VEP objective-perimetry tradition (Sutter's m-sequences;
  Klistorner & Graham; Hood). We use *distinct flicker frequencies* per
  sector rather than m-sequence tagging — simpler to analyse per-tag by FFT,
  at the cost of the m-sequence method's orthogonality across many sectors.
* Interpreting which scalp topography a sector should produce (and the
  caution that C1 polarity alone does not uniquely identify V1): Ales,
  Carney & Klein (2010) and Ales, Yates & Norcia (2010), NeuroImage.
* A transparent analysis pipeline for the recorded data: the FreqTag
  toolbox (Peykarjou, Norcia et al. 2022, Dev Cogn Neurosci).

Like the FPVS/SSVEP paradigms this runs the *time-based* trial loop, not the
frame-locked hold loop: all per-frame flicker is drawn inside
``present_stimulus`` and is frame-accurate by construction (it counts frames,
never wall-clock time), so each tag stays phase-stable across a block.
"""

from __future__ import annotations

from time import time

import numpy as np
from pandas import DataFrame
from psychopy import visual

from eegnb.experiments import Experiment


def _checkerboard(n_checks: int = 8, res: int = 256) -> np.ndarray:
    """A ``res``×``res`` texture of ±1 forming an ``n_checks``×``n_checks``
    checkerboard, suitable as a ``GratingStim`` texture whose contrast can be
    flipped (±1) to produce a pattern reversal."""
    idx = np.floor(np.linspace(0, n_checks, res, endpoint=False)).astype(int)
    board = (idx[:, None] + idx[None, :]) % 2
    return (board * 2 - 1).astype(float)


class VisualRetinotopySSVEP(Experiment.BaseExperiment):
    """Frequency-tagged SSVEP mapping of visual-field sectors.

    Parameters
    ----------
    duration : float | None
        Total run duration in seconds. If None it is derived from the
        number of blocks and the per-block on/off times (with margin).
    eeg : EEG | None
    save_fn : str | None
    mode : {"multiplex", "sequential"}
        ``"multiplex"``: all sectors flicker at once (separated by
        frequency). ``"sequential"``: one sector per block, cycling.
    n_blocks : int
        Number of stimulation blocks. In sequential mode each sector gets
        ``n_blocks`` // ``n_sectors`` blocks (rounded up), cycling in order.
    block_s : float
        Duration of each stimulation block in seconds (the SSVEP epoch).
    gap_s : float
        Blank fixation gap between blocks in seconds.
    eccentricity_deg : float
        Centre-to-patch distance for the default quadrant layout.
    patch_size_deg : float
        Side length of each square checkerboard patch (degrees).
    n_checks : int
        Checks per patch side.
    target_freqs_hz : sequence[float] | None
        Desired reversal frequency per sector. Snapped to the nearest
        integer-divisor of the measured refresh rate at load time, so the
        realised tags may differ slightly (they are printed on start). The
        default 15 / 12 / 10 / 8.57 Hz are exact on a 60 Hz display.
    sectors : list[dict] | None
        Custom sector layout; each dict needs ``name``, ``marker``,
        ``pos`` (x, y in deg) and optionally ``target_freq``. Defaults to
        four quadrants.
    refresh_hz : float | None
        Override the monitor refresh rate instead of measuring it.
    use_fullscr, screen_num : passed through to BaseExperiment.
    """

    name = "Visual Retinotopy SSVEP"
    __title__ = "SSVEP sector retinotopy — frequency-tagged field mapping"

    # BIDS-EEG metadata lives in eegnb.bids.paradigms so non-PsychoPy
    # callers (CLI, exporters) can read it without loading PsychoPy.
    from eegnb.bids.paradigms import RETINOTOPY_SSVEP as _bids
    bids_task_name = _bids.bids_task_name
    bids_event_id = _bids.bids_event_id
    bids_task_json = _bids.bids_task_json
    del _bids

    # Time-based loop: the flicker is drawn frame-by-frame inside
    # present_stimulus (see module docstring), NOT via the frame-locked
    # hold loop, so default_frame_locked stays False.
    default_frame_locked = False

    # The retinotopic SSVEP is maximal over occipital cortex; upper/lower
    # field differ in C1 polarity about Oz and left/right lateralize to the
    # contralateral electrode. Advises downstream analysis only.
    channels_of_interest = ("Oz", "O1", "O2", "POz")

    # Marker for a multiplex block (all sectors on). Sequential blocks use
    # each sector's own marker (1..4 by default).
    MULTIPLEX_MARKER = 5

    def __init__(
        self,
        duration: float | None = None,
        eeg=None,
        save_fn=None,
        mode: str = "multiplex",
        n_blocks: int = 8,
        block_s: float = 12.0,
        gap_s: float = 1.5,
        eccentricity_deg: float = 5.0,
        patch_size_deg: float = 5.0,
        n_checks: int = 8,
        target_freqs_hz=None,
        sectors=None,
        refresh_hz: float | None = None,
        use_fullscr: bool = True,
        screen_num: int = 0,
    ):
        if mode not in ("multiplex", "sequential"):
            raise ValueError(
                f"mode must be 'multiplex' or 'sequential', got {mode!r}"
            )

        # Default quadrant layout: (name, marker, (x, y)). Frequencies are
        # attached from target_freqs_hz below so a caller can retune them.
        ecc = eccentricity_deg
        if sectors is None:
            sectors = [
                {"name": "upperLeft", "marker": 1, "pos": (-ecc, ecc)},
                {"name": "upperRight", "marker": 2, "pos": (ecc, ecc)},
                {"name": "lowerLeft", "marker": 3, "pos": (-ecc, -ecc)},
                {"name": "lowerRight", "marker": 4, "pos": (ecc, -ecc)},
            ]
        if target_freqs_hz is None:
            target_freqs_hz = [15.0, 12.0, 10.0, 8.571]
        for i, s in enumerate(sectors):
            s.setdefault(
                "target_freq",
                target_freqs_hz[i] if i < len(target_freqs_hz) else 10.0,
            )

        self.mode = mode
        self.sectors = sectors
        self.n_sectors = len(sectors)
        self.n_blocks = n_blocks
        self.block_s = block_s
        self.gap_s = gap_s
        self.patch_size_deg = patch_size_deg
        self.n_checks = n_checks
        self._refresh_override = refresh_hz

        if duration is None:
            duration = n_blocks * (block_s + gap_s) + 5.0

        # SOA = block length, ITI = blank gap. jitter 0 for phase-stable tags.
        super().__init__(
            exp_name=self.name,
            duration=duration,
            eeg=eeg,
            save_fn=save_fn,
            n_trials=n_blocks,
            iti=gap_s,
            soa=block_s,
            jitter=0.0,
            use_vr=False,
            use_fullscr=use_fullscr,
            screen_num=screen_num,
        )

        # Marker per block. Multiplex: every block is MULTIPLEX_MARKER.
        # Sequential: cycle through the sectors' own markers.
        if mode == "multiplex":
            self.parameter = np.full(n_blocks, self.MULTIPLEX_MARKER, dtype=int)
        else:
            seq = [sectors[i % self.n_sectors]["marker"] for i in range(n_blocks)]
            self.parameter = np.asarray(seq, dtype=int)
        self.trials = DataFrame(
            dict(parameter=self.parameter, timestamp=np.zeros(n_blocks))
        )

        self.markernames = {s["marker"]: s["name"] for s in sectors}
        self.markernames[self.MULTIPLEX_MARKER] = "multiplexBlock"

        # Populated in load_stimulus.
        self._patches: list[visual.GratingStim] = []
        self._hold_frames: list[int] = []
        self.actual_freqs_hz: list[float] = []
        self.fixation = None

    # ------------------------------------------------------------------ #
    # Stimulus loading
    # ------------------------------------------------------------------ #
    def load_stimulus(self):
        refresh = self._refresh_override or self.window.getActualFrameRate() or 60.0
        refresh = float(np.round(refresh))
        self._refresh = refresh

        tex = _checkerboard(self.n_checks)
        size = self.patch_size_deg
        for s in self.sectors:
            self._patches.append(
                visual.GratingStim(
                    win=self.window,
                    tex=tex,
                    mask="circle",
                    units="deg",
                    size=size,
                    # One texture copy across the patch (no tiling).
                    sf=1.0 / size,
                    pos=s["pos"],
                )
            )
            # Frames each pattern state is held; reversal rate = refresh/hold.
            # hold>=2 (a 1-frame hold would reverse every frame = refresh/1,
            # aliasing to a static mean-grey percept).
            hold = max(2, int(round(refresh / s["target_freq"])))
            self._hold_frames.append(hold)
            self.actual_freqs_hz.append(refresh / hold)

        # Central fixation dot; kept up during blocks and blank gaps so the
        # participant always has a fixation target (essential for a clean
        # retinotopic map — the field position is defined relative to gaze).
        self.fixation = visual.GratingStim(
            win=self.window, pos=[0, 0], sf=0, size=0.3, color=[1, 0, 0]
        )

        print(
            "SSVEP retinotopy [{}]: refresh ~{:.0f} Hz\n".format(self.mode, refresh)
            + "\n".join(
                "  {:<11s} @ {:6.3f} Hz  (hold {} frames)  pos {}".format(
                    s["name"], f, h, s["pos"]
                )
                for s, f, h in zip(self.sectors, self.actual_freqs_hz, self._hold_frames)
            )
        )
        return self._patches

    # ------------------------------------------------------------------ #
    # Presentation
    # ------------------------------------------------------------------ #
    def present_iti(self):
        """Blank gap between blocks — hold fixation, no flicker."""
        if self.fixation is not None:
            self.fixation.draw()
        self.window.flip()

    def _push(self, marker: int):
        if not self.eeg:
            return
        code = [marker] if self.eeg.backend == "muselsl" else marker
        self.eeg.push_sample(marker=code, timestamp=time())

    def present_stimulus(self, idx: int):
        """Run one stimulation block: draw every frame for ``block_s`` seconds,
        toggling each active sector's checkerboard contrast on its own
        frame-hold schedule. Frame-accurate because it counts frames."""
        if idx >= len(self.parameter):
            return

        block_marker = int(self.parameter[idx])
        if self.mode == "multiplex":
            active = list(range(self.n_sectors))
        else:
            # Sequential: the one sector whose marker matches this block.
            active = [
                i for i, s in enumerate(self.sectors)
                if s["marker"] == block_marker
            ]

        self._push(block_marker)

        n_frames = max(1, int(round(self._refresh * self.block_s)))
        for f in range(n_frames):
            for i in active:
                # state 0 -> contrast +1, state 1 -> contrast -1 (reversal).
                state = (f // self._hold_frames[i]) % 2
                patch = self._patches[i]
                patch.contrast = 1.0 if state == 0 else -1.0
                patch.draw()
            if self.fixation is not None:
                self.fixation.draw()
            self.window.flip()
