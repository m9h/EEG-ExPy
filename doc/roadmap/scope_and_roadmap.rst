Project scope and roadmap
==========================

This page captures the architecture decisions and open work items for
this fork of EEG-ExPy. It's kept in the repo so contributors and
future maintainers have a single source for *why* the code looks the
way it does, not just *what* it does.

Project scope
-------------

EEG-ExPy is explicitly an **EEG-specific integration layer between
PsychoPy and MNE-Python**. It is not a stimulus-presentation library
(that is PsychoPy's job) nor an analysis library (that is MNE /
specparam / pyRiemann's job). The value-add is the seams:

* EEG-specific marker synchronisation and board-timestamp alignment.
* Device wrappers (g.tec Unicorn, Muse, OpenBCI variants) that
  ``psychopy.iohub`` does not natively cover.
* Paradigm templates that are EEG-aware — FPVS Stothart, FPVS Rossion,
  classical N170 / P300 / SSVEP — exposed as plain Python classes.
* Design-validation tooling that respects EEG constraints —
  dry-electrode noise factors, frequency-tag / endogenous-peak
  collision checks, per-paradigm channel regions of interest.
* Format bridging — brainflow CSV to MNE Raw to XDF to BIDS-EEG — so
  recordings flow cleanly into the standard analysis ecosystem.

**When considering new features:** if PsychoPy or iohub already does
it, wrap or rewrap; if MNE does it, pipe into MNE; only hand-roll
things that sit at the EEG-specific integration seam.

Ecosystem alignment
-------------------

The following canonical tools cover adjacent responsibilities. This
fork aims to **interoperate** with each, not replace them.

.. list-table::
   :widths: 22 56 22
   :header-rows: 1

   * - Tool
     - Role
     - Our relationship
   * - `PsychoPy <https://www.psychopy.org/>`_
     - Stimulus presentation, timing, eye-tracking via iohub
     - We subclass ``BaseExperiment``; paradigm stim code is
       idiomatic PsychoPy
   * - `LSL <https://labstreaminglayer.org/>`_
     - Cross-process / cross-machine real-time data streaming
     - EEG data and markers are published to LSL outlets; our
       ``EEG`` device class will gain a brainflow -> LSL bridge
   * - `LabRecorder <https://github.com/labstreaminglayer/App-LabRecorder>`_
     - Canonical LSL recorder; writes XDF
     - Users launch LabRecorder alongside the paradigm; we provide
       no custom on-disk format
   * - `MNE-LSL <https://github.com/mne-tools/mne-lsl>`_
     - Live monitoring with an ``mne.Raw``-shaped streaming API,
       built-in ``StreamViewer``
     - Default live-monitoring path; we add only a small
       FPVS-specific ROI-spectrum panel
   * - `MNELAB <https://github.com/cbrnr/mnelab>`_
     - Offline Qt GUI for MNE-Python with XDF import, ICA, ICLabel
     - Recommended post-session browser; no custom GUI from us
   * - `mne-bids <https://github.com/mne-tools/mne-bids>`_
     - BIDS-EEG conversion from MNE Raw
     - Called by ``eegnb.bids`` to emit standards-compliant datasets
   * - `specparam / FOOOF <https://fooof-tools.github.io/fooof/>`_
     - Aperiodic / periodic spectral decomposition
     - Used by ``eegnb.analysis.baseline`` to identify subject peaks
   * - `mne-python <https://mne.tools/>`_
     - Offline analysis core: filtering, ICA, epoching, source
     - Target of the conversion pipeline; consumers of our XDF / BIDS

What EEG-ExPy builds vs. what it wraps
--------------------------------------

Build
^^^^^

* **FPVS paradigm classes** — Stothart and Rossion — as Python
  subclasses of ``BaseExperiment``.
* **Frequency-tagged analysis** — narrow-band SNR, harmonic summation,
  collision checking against subject baseline peaks.
* **Design-validation tooling** — ``eegnb tune``, dry-electrode power
  analysis, signal-quality precheck.
* **Brainflow device wrappers** for Unicorn and similar — bridging to
  LSL when needed.
* **Marker sync** that is sub-frame accurate via PsychoPy's frame-count
  loop, logged for post-hoc verification.
* **BIDS-EEG export** — the small amount of paradigm metadata plumbing
  needed to produce standards-compliant datasets via mne-bids.
* **Pweave reports** — a scholarly review document and a per-recording
  analysis report; live updating is out of scope.

Wrap
^^^^

* **Stimulus presentation** — all timing and drawing via PsychoPy.
* **Real-time streaming** — defer to MNE-LSL's ``Stream`` / ``StreamViewer``.
* **Recording format** — defer to LabRecorder / XDF.
* **Offline GUI browsing** — defer to MNELAB.
* **Eye-tracking** — defer to PsychoPy iohub's Tobii / EyeLink drivers.
* **Trial sequencing** — defer to PsychoPy ``TrialHandler`` when possible.

Non-goals
---------

These were considered and explicitly cut to avoid duplicating upstream
tooling:

* A full PySide6 / Qt experiment-launcher GUI that replicates
  PsychoPy Builder / Runner.
* A custom recording format competing with XDF.
* Custom live-EEG plotting that duplicates MNE-LSL's ``StreamViewer``.
* A forked / realtime variant of MNELAB (would require reworking its
  in-memory Raw data model).
* Direct Tobii Pro SDK integration; iohub is the right layer.

Roadmap
-------

Short-term (concrete, scoped)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 6 40 10 8
   :header-rows: 1

   * - #
     - Item
     - Approx size
     - Status
   * - 1
     - Brainflow -> LSL bridge on ``eegnb.devices.EEG``
     - ~2 hours
     - pending
   * - 2
     - Paradigm markers to LSL outlet (alongside brainflow in-process)
     - ~30 minutes
     - pending
   * - 3
     - Document "launch LabRecorder alongside your paradigm" in
       ``unicorn_fedora_linux.rst``
     - ~15 minutes
     - pending
   * - 4
     - ``eegnb.bids.to_bids()`` converter + ``--bids-root`` flag on
       ``runexp``; ``bids_task_name`` / ``bids_task_json`` class
       attributes on each paradigm
     - ~2 hours
     - pending
   * - 5
     - Small FPVS ROI-spectrum pyqtgraph panel (not a full dashboard)
     - ~1 hour
     - pending
   * - 6
     - Fix BOSS stimulus auto-fetch via ``gdown`` + the real Google
       Drive ID
     - ~15 minutes
     - pending
   * - 7
     - Textual TUI for session orchestration (``eegnb-tui``)
     - ~3 hours
     - pending

Medium-term (design decisions open)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* **``.psyexp`` Builder export** — generate PsychoPy Builder files
  from our paradigm classes so users can open the paradigm in the
  Builder GUI, tweak it, and re-save. This lets PsychoPy Runner
  serve as our "GUI launcher" at zero maintenance cost.
* **Tobii eye-tracker integration** — when the Windows rig comes
  online, use ``psychopy.iohub.devices.tobii``. Add an optional
  ``use_eyetracker=True`` kwarg on the paradigm classes that wires
  iohub events into the marker stream.
* **Multi-monitor subject / experimenter split** — formalise the
  ``--screen`` flag and document refresh-rate matching, primary
  display assignment, compositor quirks per OS.
* **Fastball extensions** — Hermann et al 2025 have extended
  Stothart's paradigm to line-orientation discrimination and to
  Alzheimer / Lewy Body Dementia cohorts. Both reuse the base
  machinery; worth adding as ``VisualFPVSLineOrientation`` etc.
* **Real-time FPVS SNR during a session** — compute rolling
  FFT-SNR at oddball frequency and show it on the MNE-LSL viewer
  or a companion panel, so experimenters see the oddball response
  build up. Conceptually a continuous version of ``eegnb tune``.

Long-term (ideas, not committed)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* **Hyperscanning** — two Unicorns + two LabRecorder streams into one
  XDF for simultaneous-subject designs.
* **LSL-based experimenter dashboard** running on a separate machine,
  reading the paradigm's LSL outlet — natural evolution of (5) once
  the LSL bridge is in.
* **Community paradigm templates** — a ``paradigms/`` directory with
  contributed FSL timing files + BIDS task descriptors so published
  paradigms can be replicated by ``eegnb runexp -sched file.txt``.

Upstream contribution
---------------------

This fork exists primarily to support research using the g.tec Unicorn
under Linux and to add the FPVS / Fastball paradigm family. Some
changes are candidates for upstream contribution back to
``NeuroTechX/EEG-ExPy`` as narrow PRs:

* Drop pynput to fix Linux installs — already open as
  `NeuroTechX/EEG-ExPy#323 <https://github.com/NeuroTechX/EEG-ExPy/pull/323>`_.
* Conditional PsychoPy audio backend (try PTB, fall back to sounddevice).
* Guard ``pyxid2`` import.

Larger changes — PEP 621 pyproject.toml migration, FPVS paradigms,
Pweave reports, BIDS export — stay on the fork's ``morgan/modernize``
branch unless / until the upstream project signals appetite for them.

References
----------

The scholarly context for the FPVS paradigm family (SSVEP, Rossion
face individuation, Stothart Fastball) is in
:doc:`../reports/ssvep_fpvs_fastball_review`. That document is built
from ``eegnb/reports/templates/review.Pnw`` by
``eegnb.reports.build_review``.
