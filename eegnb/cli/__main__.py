import click
import os

from eegnb import DATA_DIR
from eegnb.datasets.datasets import zip_data_folders

from .introprompt import intro_prompt, analysis_intro_prompt
from .utils import run_experiment
from eegnb import generate_save_fn
from eegnb.devices.eeg import EEG
from eegnb.analysis.utils import check_report
from eegnb.analysis.pipelines import load_eeg_data, make_erp_plot, analysis_report, example_analysis_report
from typing import Optional



@click.group(name="eegnb")
def main():
    """eeg-notebooks command line interface"""
    pass


@main.command()
@click.option("-ex", "--experiment", help="Experiment to run")
@click.option("-ed", "--eegdevice", help="EEG device to use")
@click.option("-ma", "--macaddr", help="MAC address of device to use (if applicable)")
@click.option("-rd", "--recdur", help="Recording duration", type=float)
@click.option("-of", "--outfname", help="Output filename")
@click.option(
    "-ip", "--prompt", help="Use interactive prompt to ask for parameters", is_flag=True
)
@click.option(
    "--report/--no-report", "report", default=True,
    help="Generate a Pweave LaTeX report after the run (default: on).",
)
@click.option(
    "--report-no-pdf", is_flag=True,
    help="Emit only the .tex; skip pdflatex (useful on machines without TeX).",
)
def runexp(
    experiment: str,
    eegdevice: Optional[str] = None,
    macaddr: Optional[str] = None,
    recdur: Optional[float] = None,
    outfname: Optional[str] = None,
    prompt: bool = False,
    report: bool = True,
    report_no_pdf: bool = False,
    dosigqualcheck = True,
):
    """
    Run experiment.

    Examples:

    Run experiment explicitly defining all necessary parameters
    (eeg device, experiment, duration, output file)
    This is the quickest way to run eeg-notebooks experiments,
    but requires knowledge of formatting for available options

    $ eegnb runexp -ex visual-N170 -ed museS -rd 10 -of test.csv


    Launch the interactive command line experiment setup+run tool
    This takes you through every experiment parameter in order
    and figures out + runs the complete function calls for you

    $ eegnb runexp -ip
    """

    if prompt:
        eeg, experiment, recdur, outfname = intro_prompt()
    else:
        # Random values for outfile for now
        outfname = str(generate_save_fn(str(eegdevice), experiment,7, 7))
        if eegdevice == "ganglion":
            # if the ganglion is chosen a MAC address should also be provided
            eeg = EEG(device=eegdevice, mac_addr=macaddr)
        else:
            eeg = EEG(device=eegdevice)

    def askforsigqualcheck():
        do_sigqual = input("\n\nRun signal quality check? (y/n). Recommend y \n")
        if do_sigqual == 'y':
            check_report(eeg)
        elif do_sigqual != 'n':
            "Sorry, didn't recognize answer. "
            askforsigqualcheck()
    
    if dosigqualcheck:
        askforsigqualcheck()

    run_experiment(experiment, eeg, recdur, outfname)

    print(f"\n\n\nExperiment complete! Recorded data is saved @ {outfname}")

    if report:
        try:
            from eegnb.reports import generate_report

            device_for_report = eegdevice or "unicorn"
            out = generate_report(
                csv_path=outfname,
                paradigm=experiment,
                device=device_for_report,
                run_pdflatex=not report_no_pdf,
            )
            print(f"Report generated: {out}")
        except Exception as exc:
            # Don't let a report failure mask a successful recording.
            print(f"[report] skipped: {exc}")


@main.command()
@click.option("-ex", "--experiment", help="Experiment to run")
@click.option("-ed", "--eegdevice", help="EEG device to use")
@click.option("-sub", "--subject", help="Subject ID")
@click.option("-sess", "--session", help="Session number")
@click.option("-site", "--site", help="Site/Study Name")
@click.option("-fp", "--filepath", help="Filepath to save data")
@click.option("-ip", "--prompt", help="Use interactive prompt to ask for parameters", is_flag=True
)
def create_analysis_report(
    experiment: str,
    eegdevice: Optional[str] = None,
    subject: Optional[str] = None, 
    session: Optional[str] = None,
    site: Optional[str] = None,
    filepath: Optional[str] = None,
    prompt: bool = False,
):
    """
    Create analysis report of recorded data
    """
    
    if prompt:
        example = input("Do you want to load an example experiment? (y/n)\n")
        print()
        if example == 'y':
            example_analysis_report()
            return
        else:
            experiment, eegdevice, subject, session, site, filepath = analysis_intro_prompt()
    analysis_report(experiment, eegdevice, subject, session, site, filepath)

@main.command()
@click.option("-ed", "--eegdevice", help="EEG device to use", required=True)
def checksigqual(eegdevice: str):
    """
    Run signal quality check.

    Usage:
        eegnb checksigqual --eegdevice museS
    """

    from eegnb.devices.eeg import EEG
    from eegnb.analysis.utils import check_report

    eeg = EEG(device=eegdevice)

    check_report(eeg)

    # TODO: implement command line options for non-default check_report params
    #       ( n_times, pause_time, thres_var, etc. )
    #       [ tried to do this but keeps defaulting to None rather than default
    #         valuess in the function definition ]




@main.command()
@click.option("-ex", "--experiment", help="Experiment to zip", required=False)
@click.option(
    "-s", "--site", help="Specific Directory", default="local_ntcs", required=False
)
@click.option(
    "-ip", "--prompt", help="Use interactive prompt to ask for parameters", is_flag=True
)
def runzip(experiment: str, site: str, prompt: bool = False):

    """eeg
    Run data zipping

    Usage

    $ eegnb runzip -ex visual-N170
    $ eegnb runzip -ex visual-N170 -s local-ntcs-2
    
    Launch the interactive command line to select experiment

    $ eegnb runzip -ip

    """

    if prompt:
        from .introprompt import intro_prompt_zip

        experiment, site = intro_prompt_zip()

    zip_data_folders(experiment, site)


@main.command()
def localdata_report():
    """
    Run local data summary

    Usage

    $eegnb localdata-report
    """

    print("\n EEG-Notebooks Local Data Report")
    print("\n ===============================\n")
    print(
        " Here is a short report of eeg-notebooks-related EEG data that was found on this machine:\n"
    )

    directory_contents = os.listdir(DATA_DIR)
    # print(directory_contents)

    example_datasets = []
    recorded_datasets = []
    for dir in directory_contents:

        dir_contents = os.path.join(DATA_DIR, dir)
        subdir_contents = os.listdir(dir_contents)
        for subdir in subdir_contents:
            subdir_path = os.path.join(DATA_DIR, dir, subdir)
            print(subdir_path)
            if os.path.isdir(subdir_path):
                if len(os.listdir(subdir_path)) == 0:
                    subdir_path = subdir_path + " [EMPTY]"
                if "eegnb_examples" in subdir:
                    example_datasets.append(subdir_path)
                else:
                    recorded_datasets.append(subdir_path)

    print("\n 1. Default Data \n")
    print(" ------------------\n")
    print(" The default eeg-notebooks data location on this machine is\n")
    print(" {}".format(DATA_DIR))
    print("\n (note that `.eegnb` is a hidden folder)\n")
    print("\n Folders where you have downloaded the eeg-notebooks example datasets:\n")
    for items in example_datasets:
        print(" {}".format(items))

    print("\n\n 2. Your recorded data\n")
    print(" ------------------\n")
    print("\n Folders where you have recorded your own data:\n")
    for items in recorded_datasets:
        print(" {}".format(items))


@main.command()
@click.option("-ed", "--eegdevice", default="unicorn",
              help="EEG device (only unicorn is supported at present).")
@click.option("-d", "--duration", type=float, default=10.0,
              help="Seconds to record for the precheck.")
@click.option("--line", type=float, default=50.0,
              help="Line frequency in Hz (50 EU, 60 US).")
@click.option("-sp", "--serial-port", default="/dev/ttyACM0",
              help="Serial port for the BLED112 dongle.")
def impcheck(eegdevice: str, duration: float, line: float,
             serial_port: str):
    """Dry-electrode signal-quality precheck before a recording session."""
    from eegnb.analysis.signal_quality import run_signal_quality_check

    report = run_signal_quality_check(
        device=eegdevice,
        duration_s=duration,
        line_freq_hz=line,
        serial_port=serial_port,
    )
    print(report.summary())
    for c in report.channels:
        for note in c.notes:
            print(f"  {c.name}: {note}")


@main.command()
@click.option("-b", "--baseline", "baseline_csv", required=True,
              type=click.Path(exists=True),
              help="CSV of a resting-state (eyes-open) baseline recording.")
@click.option("-ex", "--experiment", required=True,
              help="Paradigm to tune "
                   "(visual-fpvs-stothart | visual-fpvs-rossion).")
@click.option("--margin", type=float, default=0.5,
              help="Safety margin in Hz around each subject peak.")
@click.option("--harmonics", type=int, default=5,
              help="Number of oddball harmonics to check.")
def tune(baseline_csv: str, experiment: str, margin: float,
         harmonics: int):
    """Check paradigm tag frequencies against subject baseline peaks.

    Fits FOOOF / specparam to the baseline recording, then flags any
    paradigm base or oddball harmonic that lands within a subject peak
    (± bandwidth/2 ± safety margin). Reports whether the design is
    clear and suggests a nearby base rate if it isn't.
    """
    from eegnb.analysis.baseline import fit_resting_peaks
    from eegnb.analysis.power import check_paradigm_collisions

    paradigm_params = {
        "visual-fpvs-stothart": dict(base_hz=3.0, oddball_hz=0.6),
        "visual-fpvs-rossion":  dict(base_hz=5.88, oddball_hz=1.176),
    }
    if experiment not in paradigm_params:
        print(f"unknown paradigm {experiment!r}; expected one of "
              f"{sorted(paradigm_params)}")
        return
    pp = paradigm_params[experiment]

    print(f"Fitting FOOOF to {baseline_csv}...")
    profile = fit_resting_peaks(baseline_csv)
    print(f"  {len(profile.channels)} channels, "
          f"{profile.duration_s:.1f}s duration, {profile.sfreq_hz} Hz")
    for peak in profile.alpha_peaks[:4]:
        print(f"  alpha: {peak.channel} @ {peak.centre_hz:.2f} Hz "
              f"(bw {peak.bandwidth_hz:.2f})")
    for peak in profile.beta_peaks[:4]:
        print(f"  beta:  {peak.channel} @ {peak.centre_hz:.2f} Hz "
              f"(bw {peak.bandwidth_hz:.2f})")
    print()

    print(f"Checking {experiment} (base {pp['base_hz']} Hz, "
          f"oddball {pp['oddball_hz']} Hz, {harmonics} harmonics):")
    cols = check_paradigm_collisions(
        base_hz=pp["base_hz"],
        oddball_hz=pp["oddball_hz"],
        peaks=profile,
        n_oddball_harmonics=harmonics,
        safety_margin_hz=margin,
    )
    if not cols:
        print("  [OK] no collisions between tags and subject peaks.")
        return

    print(f"  [WARN] {len(cols)} collision(s):")
    for c in cols:
        print(f"    {c.tag_label} @ {c.tag_hz:.2f} Hz vs "
              f"{c.peak_channel} peak @ {c.peak_hz:.2f} Hz "
              f"(gap {c.gap_hz:.2f} Hz)")

    import numpy as np

    base_hz = pp["base_hz"]
    candidates = np.linspace(base_hz * 0.8, base_hz * 1.2, 41)
    clean: list[tuple[float, float]] = []
    for cand_base in candidates:
        cand_odd = cand_base * pp["oddball_hz"] / base_hz
        if check_paradigm_collisions(
            base_hz=cand_base, oddball_hz=cand_odd,
            peaks=profile, n_oddball_harmonics=harmonics,
            safety_margin_hz=margin,
        ):
            continue
        clean.append((cand_base, cand_odd))
    if clean:
        cand_base, cand_odd = min(
            clean, key=lambda x: abs(x[0] - base_hz)
        )
        print(
            f"  Suggestion: shift base to {cand_base:.2f} Hz "
            f"(oddball {cand_odd:.3f} Hz) to clear collisions."
        )
    else:
        print(
            "  No clean base rate found within ±20%; reduce harmonics "
            "or accept that a harmonic collides with endogenous rhythms."
        )


if __name__ == "__main__":
    main()
