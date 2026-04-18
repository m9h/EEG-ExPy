"""Unit tests for eegnb.analysis.power."""

from eegnb.analysis.power import (
    design_efficiency,
    fpvs_detection_power,
    check_paradigm_collisions,
)
from eegnb.analysis.baseline import PeakProfile, SpectralPeak


def test_detection_power_grows_with_duration():
    short = fpvs_detection_power(
        duration_s=10, base_hz=3.0, oddball_hz=0.6, n_harmonics=4,
        expected_amp_uv=1.0, noise_rms_uv=10.0,
    )
    long = fpvs_detection_power(
        duration_s=100, base_hz=3.0, oddball_hz=0.6, n_harmonics=4,
        expected_amp_uv=1.0, noise_rms_uv=10.0,
    )
    assert long.z_expected > short.z_expected
    assert long.power >= short.power


def test_detection_power_duration_crops_to_oddball_cycles():
    res = fpvs_detection_power(
        duration_s=60.3, base_hz=3.0, oddball_hz=0.6, n_harmonics=4,
        expected_amp_uv=1.0, noise_rms_uv=10.0,
    )
    # 60.3 s / (1/0.6 s) = 36.18 cycles -> cropped to 36.
    assert abs(res.duration_s - 36 / 0.6) < 1e-6


def test_detection_power_dry_factor_lowers_amp():
    wet = fpvs_detection_power(
        duration_s=60, base_hz=3.0, oddball_hz=0.6, n_harmonics=4,
        expected_amp_uv=1.0, noise_rms_uv=10.0,
    )
    dry = fpvs_detection_power(
        duration_s=60, base_hz=3.0, oddball_hz=0.6, n_harmonics=4,
        expected_amp_uv=1.0, noise_rms_uv=10.0, dry_electrode_factor=0.5,
    )
    assert dry.expected_amp_uv < wet.expected_amp_uv
    assert dry.z_expected < wet.z_expected


def test_design_efficiency_flags_stothart_rank_collision():
    # With 5 oddball harmonics Stothart's 5th oddball harmonic (3 Hz) is
    # rank-equal to the base rate; cond(X'X) should blow up.
    eff = design_efficiency(
        duration_s=60, sfreq_hz=250, base_hz=3.0, oddball_hz=0.6,
        n_base_harmonics=1, n_oddball_harmonics=5,
    )
    assert eff.condition_number > 1e6

    # With 4 oddball harmonics there is no collision.
    ok = design_efficiency(
        duration_s=60, sfreq_hz=250, base_hz=3.0, oddball_hz=0.6,
        n_base_harmonics=1, n_oddball_harmonics=4,
    )
    assert ok.condition_number < 100


def test_collision_checker_finds_alpha_overlap():
    # Simulate a subject with a PO8 alpha peak at 11.7 Hz, bw 2.0.
    profile = PeakProfile(
        channels=["PO8"],
        peaks=[SpectralPeak(channel="PO8", centre_hz=11.7,
                            power=1.0, bandwidth_hz=2.0)],
    )
    # Rossion: base 5.88, oddball 1.176. 2nd oddball harmonic
    # (2.352) and the 10th (11.76) will be tested; with
    # n_oddball_harmonics=10 one harmonic falls near the alpha peak.
    cols = check_paradigm_collisions(
        base_hz=5.88, oddball_hz=1.176, peaks=profile,
        n_oddball_harmonics=10, safety_margin_hz=0.2,
    )
    assert any(abs(c.tag_hz - 11.76) < 0.01 for c in cols)


def test_collision_checker_skips_base_rate_by_default():
    profile = PeakProfile(
        channels=["Oz"],
        peaks=[SpectralPeak(channel="Oz", centre_hz=3.0,
                            power=1.0, bandwidth_hz=1.0)],
    )
    # base 3 Hz lands exactly on the peak.
    default = check_paradigm_collisions(
        base_hz=3.0, oddball_hz=0.6, peaks=profile,
    )
    # With ignore_base_rate=True the 3 Hz base is excluded from the
    # collision set. The 5th oddball harmonic (3.0 Hz) should still
    # collide though.
    tag_labels = {c.tag_label for c in default}
    assert not any(l.startswith("base") for l in tag_labels)
