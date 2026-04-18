Stimulus sets
=============

The visual paradigms that ship with EEG-ExPy (N170, P300, SSVEP,
FPVS-Stothart, FPVS-Rossion) each depend on a pool of images. The
N170 and face/house paradigms are bundled with the package; the two
FPVS paradigms expect you to supply stimuli downloaded from the
canonical third-party databases listed below.

This page catalogues the supported sets, their licensing, and how to
pull them into a form the paradigm code can consume.

Quick reference
---------------

.. list-table::
   :widths: 22 10 18 40 10
   :header-rows: 1

   * - Database
     - Size
     - License
     - Use with
     - Auto-fetch
   * - Bundled face/house
     - 70 files
     - Shipped with repo
     - ``VisualN170`` (default fallback)
     - —
   * - BOSS Phase II
     - 930 objects
     - CC-BY (see Figshare)
     - ``VisualFPVSStothart``
     - ✅
   * - Chicago Face Database
     - 597 identities
     - Research use; registration required
     - ``VisualFPVSRossion``
     - ⚠ semi
   * - KDEF
     - 70 × 7 expressions
     - Research use; registration
     - ``VisualFPVSRossion``
     - ✗
   * - FACES (MPIB)
     - 171 × 6
     - Research use; registration
     - ``VisualFPVSRossion``
     - ✗
   * - Thorpe / CerCo scenes
     - varies
     - Research use
     - Ultrarapid categorisation (not FPVS)
     - ✗

Bank of Standardized Stimuli (BOSS)
-----------------------------------

`BOSS Phase II <https://plos.figshare.com/articles/dataset/_Bank_of_Standardized_Stimuli_BOSS_Phase_II_930_New_Normative_Photos_/1168008>`_
(Brodeur, Guérard & Bouras, 2014) is the 930-image expansion of the
original 480-image BOSS (Brodeur et al., 2010). Colour photographs of
everyday objects on white backgrounds, normed for name agreement,
visual complexity, manipulability, and more. It is the canonical
stimulus set for Stothart's Fastball paradigm.

Fetch it into the local stimuli directory:

.. code-block:: python

    from eegnb.stimuli.downloads import fetch_boss
    fetch_boss()  # -> <package>/eegnb/stimuli/visual/boss_v2/

Then construct the paradigm pointing at it:

.. code-block:: python

    import os
    from eegnb.stimuli import FACE_HOUSE  # gives us <stimuli>/visual
    from eegnb.experiments import VisualFPVSStothart

    boss = os.path.join(os.path.dirname(FACE_HOUSE), "boss_v2")
    exp = VisualFPVSStothart(
        standard_dir=os.path.join(boss, "Standards"),
        deviant_dir=os.path.join(boss, "Deviants"),
        duration=173.0,
    )

**Citation:** Brodeur, M. B., Dionne-Dostie, E., Montreuil, T., & Lepage,
M. (2010). *PLoS ONE* 5(5):e10773. DOI:
`10.1371/journal.pone.0010773 <https://doi.org/10.1371/journal.pone.0010773>`_.
Brodeur, M. B., Guérard, K., & Bouras, M. (2014). *PLoS ONE* 9(9):e106953.

Chicago Face Database (CFD)
---------------------------

`CFD <https://www.chicagofaces.org/>`_ (Ma, Correll, Wittenbrink, 2015)
is the free face database most often used as a substitute for Rossion's
non-distributable in-house identities. High-resolution frontal photos of
597 unique individuals spanning multiple ethnicities, ages, and genders,
all with neutral expression plus additional expression variants.

Because access requires registration on ``chicagofaces.org``, download
the zip manually then pipe it through the preparer:

.. code-block:: python

    from eegnb.stimuli.downloads import prepare_cfd

    result = prepare_cfd(
        cfd_zip_path="~/Downloads/CFD Version 3.0.0.zip",
        target_size_px=512,
        greyscale=True,
        crop_external=True,
    )
    print(f"prepared {result.n_neutral_frontals} neutral frontals "
          f"across {len(result.identities)} identities -> {result.out_dir}")

Then wire the prepared folder into a paradigm. Rossion's canonical
split uses one identity as the repeated base and many others as
oddballs:

.. code-block:: python

    from eegnb.experiments import VisualFPVSRossion

    cfd_dir = result.out_dir
    base_id = result.identities[0]            # arbitrary choice
    # split: one folder for the base, another for the rest
    base_dir = cfd_dir / "_base"
    odd_dir = cfd_dir / "_odd"
    base_dir.mkdir(exist_ok=True)
    odd_dir.mkdir(exist_ok=True)
    for p in cfd_dir.glob("*.jpg"):
        if p.name.startswith(base_id):
            p.rename(base_dir / p.name)
        else:
            p.rename(odd_dir / p.name)

    exp = VisualFPVSRossion(
        base_identity_dir=str(base_dir),
        oddball_identities_dir=str(odd_dir),
        duration=70.0,
    )

**Citation:** Ma, D. S., Correll, J., & Wittenbrink, B. (2015).
*Behavior Research Methods* 47(4):1122. DOI:
`10.3758/s13428-014-0532-5 <https://doi.org/10.3758/s13428-014-0532-5>`_.

KDEF
----

`KDEF <https://kdef.se/>`_ (Karolinska Directed Emotional Faces,
Lundqvist, Flykt & Öhman, 1998). 70 identities × 7 expressions × 5
viewing angles. Older and smaller than CFD but still widely cited. No
auto-fetch yet; register on the site, download ``KDEF_AF.zip``, then
filter for the frontal neutral subset (``*AF*NE*.JPG``) manually.

FACES database (Max Planck Berlin)
----------------------------------

`FACES <https://faces.mpib-berlin.mpg.de/>`_ (Ebner, Riediger & Lindenberger,
2010). 171 identities × 6 expressions with young/middle-aged/older age
groups; 2,052 images total. Research registration required, no
auto-fetch.

Rossion lab in-house stimuli
----------------------------

Liu-Shuang, Norcia & Rossion (2014) used 50 neutral-expression identities
compiled from several sources. These are not publicly distributable due
to image-rights constraints; CFD is the standard substitute for any
public-facing replication.

Thorpe / CerCo scenes
---------------------

The Simon Thorpe lab (CerCo Toulouse) publishes natural-scene stimuli for
ultra-rapid categorisation (Thorpe, Fize & Marlot, 1996 *Nature*). These
are not used with FPVS oddball work — the paradigm is go/no-go rather
than frequency-tagged — but they are the canonical fixture of another
French vision-science line and are occasionally confused with face-FPVS
stimuli. Listed here to keep the terminology straight.

Dry-electrode notes
-------------------

Consumer dry-electrode headsets such as the g.tec Unicorn attenuate
lateral occipito-temporal signal by roughly a factor of 0.3–0.5
relative to the 64-channel wet montages used in the primary
publications. Use ``eegnb.analysis.power.fpvs_detection_power`` with
``dry_electrode_factor=0.4`` to estimate the effect on detection power
before running a subject. See the :doc:`../experiments/vn170` note on
channel selection for the Unicorn's fixed Fz/C3/Cz/C4/Pz/PO7/Oz/PO8
montage.
