"""
SSVEP sector-retinotopy run experiment
=======================================

Runs the frequency-tagged SSVEP retinotopy paradigm: contrast-reversing
checkerboard patches in four visual-field quadrants, each tagged at a
distinct integer-divisor frequency, for coarse (quadrant/hemifield)
retinotopy. Analyse the recording with
``eegnb.analysis.frequency_tagging.sector_snr``.

Present on the internal display, **fullscreen and focused** — an unfocused
window is throttled to ~1 Hz on some Wayland compositors, which destroys the
tag timing. Keep it off any DisplayLink/USB display (no reliable vsync).
"""

import os
from eegnb import generate_save_fn
from eegnb.devices.eeg import EEG
from eegnb.experiments import VisualRetinotopySSVEP

# Device / session
board_name = "unicorn"          # or "muse2", "ganglion", ...
experiment = "visual_retinotopy_ssvep"
subject_id = 0
session_nb = 0

eeg_device = EEG(device=board_name)
save_fn = generate_save_fn(board_name, experiment, subject_id, session_nb)
print(save_fn)

# multiplex = all sectors flicker at once (separated by frequency);
# sequential = one sector per block (cleaner topography on few channels).
retinotopy = VisualRetinotopySSVEP(
    mode="multiplex",
    n_blocks=8,
    block_s=12.0,
    eeg=eeg_device,
    save_fn=save_fn,
)
retinotopy.run()
