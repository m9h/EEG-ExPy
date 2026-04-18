Running the g.tec Unicorn on Fedora (Linux)
===========================================

This page documents the setup needed to acquire from a
**g.tec Unicorn Hybrid Black** on a Fedora 43 workstation using this
fork of EEG-ExPy. The same approach should work on any recent Fedora
or RHEL-family distribution.

Hardware checklist
------------------

* Unicorn Hybrid Black (8-ch dry, 250 Hz). Verify the serial number
  on the headset with::

      xvfb-run uv run python -c "from brainflow.board_shim import BoardShim, BoardIds, BrainFlowInputParams; \
          p = BrainFlowInputParams(); p.serial_port = '/dev/ttyACM0'; \
          b = BoardShim(BoardIds.UNICORN_BOARD.value, p); \
          b.prepare_session(); b.release_session()"

  BrainFlow will log the detected board's serial number (for example
  ``UN-2019.07.63``).
* Silicon Labs BLED112 BLE USB dongle. The system's built-in Bluetooth
  is **not** a substitute: BrainFlow's Linux Unicorn path uses
  Bluegiga's BGAPI over USB-CDC, not BlueZ. Verify the dongle is
  present at ``/dev/ttyACM0`` with::

      ls -la /dev/ttyACM0

System packages (dnf)
---------------------

Fedora provides most of the required native libraries. The ones worth
confirming are::

    sudo dnf install \
        gtk3-devel webkit2gtk4.1-devel \
        libnotify SDL2 portaudio \
        texlive-scheme-basic

``texlive-scheme-basic`` is only needed if you want to rebuild the
paradigm review PDF locally.

Serial-port permissions
-----------------------

The BLED112 appears as ``/dev/ttyACM0`` with mode ``0660`` and
group ``dialout``. Your user must be in that group. Persistent fix::

    sudo usermod -aG dialout $USER
    # log out and back in for the group change to apply

For a one-session quick-fix without logging out::

    sudo chmod a+rw /dev/ttyACM0

Python environment with uv
--------------------------

We manage the Python side with ``uv``. From a clean checkout of this
fork::

    cd EEG-ExPy
    uv venv --python 3.11
    uv pip install -e '.[streamstim]'

Installation will pull PsychoPy 2026.1, which in turn depends on
``wxpython``. PyPI does not ship a Fedora wxPython wheel, so the
install will fall back to a source build that typically fails. Work
around it by pre-installing a pre-built wheel from the wxPython extras
index:

.. code-block:: shell

    uv pip install \
        "https://extras.wxpython.org/wxPython4/extras/linux/gtk3/fedora-38/wxPython-4.2.1-cp311-cp311-linux_x86_64.whl"
    uv pip install -e '.[streamstim]'

libtiff compatibility shim
^^^^^^^^^^^^^^^^^^^^^^^^^^

The Fedora 38 wxPython wheel was built against ``libtiff.so.5``. Fedora
43 ships ``libtiff.so.6`` (ABI-compatible for basic TIFF use). Create a
shim inside the venv once, then activate via ``LD_LIBRARY_PATH`` before
running anything that imports ``wx`` (which is effectively every
PsychoPy paradigm)::

    mkdir -p .venv/libcompat
    ln -sf /usr/lib64/libtiff.so.6 .venv/libcompat/libtiff.so.5

    export LD_LIBRARY_PATH=$PWD/.venv/libcompat

A cleaner alternative is ``sudo dnf install compat-libtiff5`` which
places ``libtiff.so.5`` in the standard library path and removes the
need for the shim.

Wayland / XWayland caveats
--------------------------

Fedora 43 defaults to a Wayland session. PsychoPy draws via pyglet,
which on Linux uses XWayland (X11 emulation over Wayland). Two
consequences:

1. **Flip-time jitter** up to one monitor vblank interval. For N170
   and basic SSVEP this is usually fine. For FPVS/Fastball it is
   close to the tolerance and should be monitored via per-flip
   timestamp logging (see
   :doc:`../misc/frame_locked_presentation`).

2. **The welcome screen requires a keyboard.** The default paradigm
   wait-for-spacebar loop blocks indefinitely without a keyboard. Call
   ``exp.run(instructions=False)`` or wire up a programmatic start.

Running from SSH onto the NUC
-----------------------------

When you SSH into the Unicorn's host from another machine and want
PsychoPy to render on the NUC's physical monitor (not Xvfb), export
the local display and the user's XWayland cookie::

    export DISPLAY=:0
    export XAUTHORITY=/run/user/$UID/.mutter-Xwaylandauth.*
    export LD_LIBRARY_PATH=$PWD/.venv/libcompat
    uv run python your_paradigm_script.py

The ``mutter-Xwaylandauth.*`` cookie is set per-session and has a
random suffix — glob or look it up with ``ls /run/user/$UID/``.

Smoke-test sequence
-------------------

In order from cheapest to most expensive:

.. code-block:: shell

    # 1. Import + paradigm instantiation (no hardware, no display)
    LD_LIBRARY_PATH=$PWD/.venv/libcompat xvfb-run -a uv run python -c \
        "from eegnb.experiments import VisualFPVSStothart; VisualFPVSStothart()"

    # 2. BrainFlow + Unicorn connectivity (no display)
    uv run python smoke_brainflow.py   # 5-s acquisition, prints channel stats

    # 3. PsychoPy window (display required)
    LD_LIBRARY_PATH=$PWD/.venv/libcompat DISPLAY=:0 \
        XAUTHORITY=$(ls /run/user/$UID/.mutter-Xwaylandauth.*) \
        uv run python smoke_window.py

    # 4. Full paradigm (display + hardware)
    LD_LIBRARY_PATH=$PWD/.venv/libcompat DISPLAY=:0 \
        XAUTHORITY=$(ls /run/user/$UID/.mutter-Xwaylandauth.*) \
        uv run eegnb runexp -ex visual-fpvs-stothart -ed unicorn -rd 60 --no-report

The sample `smoke_brainflow.py` and `smoke_window.py` scripts are in
the project tree at ``~/dev/eeg-expy/`` (outside the repo) — copy or
adapt them as needed.

Known issues
------------

* PyPI ``pweave`` is unmaintained and fails to import on Python 3.11+.
  This fork ships ``eegnb.reports.pweave_lite`` instead; the external
  ``pweave`` binary is not required for either the review or
  per-run report.
* The Unicorn dry electrodes report raw ADC counts from brainflow,
  not microvolts. Mean baseline values near 40,000 are expected. Scale
  to microvolts as a last analysis step (divide by the device gain;
  BrainFlow's Unicorn gain is embedded in ``BoardShim.get_eeg_scale``).
