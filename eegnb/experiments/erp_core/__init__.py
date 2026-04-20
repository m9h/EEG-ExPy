"""Kappenman & Luck ERP CORE paradigm suite.

This subpackage implements the six canonical tasks from the ERP CORE
battery (Kappenman, Farrens, Zhang, Stewart, & Luck 2021, NeuroImage
225:117465) as :class:`eegnb.experiments.Experiment.BaseExperiment`
subclasses. Each paradigm exposes BIDS-EEG metadata via the shared
registry in :mod:`eegnb.bids.paradigms`.

Paradigms
---------

- :class:`VisualERPCoreN170` — face perception (faces / cars / scrambled)
- :class:`AuditoryERPCoreMMN` — passive auditory oddball (1000/1200 Hz)
- :class:`VisualERPCoreN2pc` — lateralized attention (colour-gap search)
- :class:`VisualERPCoreN400` — semantic priming (word pairs)
- :class:`VisualERPCoreP3` — active visual oddball (letters A–E)
- :class:`VisualERPCoreFlanker` — Eriksen arrow flanker (ERN + LRP)

Stimuli
-------

Four paradigms generate stimuli procedurally (MMN tones, N2pc coloured
squares with gaps, P3 letters, flanker arrow strings). Two rely on
external assets:

- N170 defaults to the bundled ``FACE_HOUSE`` photos (faces plus
  auto-scrambled variants); set ``faces_dir`` / ``cars_dir`` to point at
  Kappenman's exact OSF stimulus set (https://osf.io/thsqg/).
- N400 reads word pairs from ``eegnb/stimuli/word_pairs_erp_core.csv``;
  supply your own CSV via ``word_pairs_csv=`` for different stimuli
  (e.g. non-English).

Timing defaults are taken from Kappenman et al 2021. Subject-level
fidelity reproduction requires the exact OSF stimuli where applicable.
"""

from eegnb.experiments.erp_core.n170_faces_cars import VisualERPCoreN170
from eegnb.experiments.erp_core.mmn import AuditoryERPCoreMMN
from eegnb.experiments.erp_core.n2pc import VisualERPCoreN2pc
from eegnb.experiments.erp_core.n400 import VisualERPCoreN400
from eegnb.experiments.erp_core.p3_oddball import VisualERPCoreP3
from eegnb.experiments.erp_core.flanker import VisualERPCoreFlanker

__all__ = [
    "VisualERPCoreN170",
    "AuditoryERPCoreMMN",
    "VisualERPCoreN2pc",
    "VisualERPCoreN400",
    "VisualERPCoreP3",
    "VisualERPCoreFlanker",
]
