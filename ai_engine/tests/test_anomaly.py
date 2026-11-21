"""Anomaly detection tests on SYNTHETIC data (data_class simulated). These check detector logic
and guardrails; they are not evidence of field detection performance."""

import json

import pandas as pd
import pytest

from qatra_ai.evaluation.anomaly_benchmark import run_benchmark, score
from qatra_ai.evaluation.synthetic_water import ALL_FAULTS, generate
from qatra_ai.predictive.anomaly import FORBIDDEN_TERMS, DetectorConfig, detect_anomalies


def detect(system, **kw):
    return detect_anomalies(
        system.data, system.schedule, DetectorConfig(design_flow_m3h=system.design_flow_m3h, **kw)
    )


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_clean_data_has_no_events(seed):
    assert detect(generate(seed=seed)).events == []


@pytest.mark.parametrize("fault", ALL_FAULTS)
def test_each_fault_detected_by_an_expected_detector(fault):
    sysd = generate(seed=3, faults=(fault,))
    rows, false_alarms = score(sysd, detect(sysd))
    assert rows[0]["detected"], rows
    assert false_alarms == 0


def test_per_zone_calibration_recovers_hidden_flow_factors():
    res = detect(generate(seed=4))
    assert res.zone_calibration["A"] == pytest.approx(0.95, abs=0.02)
    assert res.zone_calibration["B"] == pytest.approx(1.03, abs=0.02)
    assert res.zone_calibration["C"] == pytest.approx(0.90, abs=0.02)


def test_no_accusatory_language_in_any_output():
    sysd = generate(seed=5, faults=ALL_FAULTS)
    res = detect(sysd)
    text = json.dumps([e.model_dump(mode="json") for e in res.events]).lower()
    text += " ".join(res.assumptions).lower()
    for term in FORBIDDEN_TERMS:
        assert term not in text, term
    for e in res.events:
        assert e.hypotheses and e.recommended_checks  # every event is explained


def test_events_carry_volume_and_detection_time():
    sysd = generate(seed=6, faults=("valve_C_stuck_open",))
    ev = next(e for e in detect(sysd).events if e.kind == "idle_flow")
    assert ev.estimated_volume_m3 == pytest.approx(3 * 8 * 0.90, rel=0.15)  # 3 h of zone C
    assert pd.Timestamp(ev.detected_at) >= pd.Timestamp(ev.start)


def test_training_window_never_alerts():
    sysd = generate(seed=7, faults=ALL_FAULTS)
    res = detect(sysd)
    train_end = sysd.data.index[0] + pd.Timedelta(days=7)
    assert all(pd.Timestamp(e.start) >= train_end for e in res.events)


def test_adaptive_thresholds_control_false_alarms_on_noisy_meters():
    noisy = generate(seed=8, meter_noise_rel=0.06)
    fixed = detect(noisy, adaptive_thresholds=False).events
    adaptive = detect(noisy).events
    assert len(adaptive) < len(fixed)


def test_missing_inlet_and_unknown_zone_rejected():
    sysd = generate(seed=0)
    with pytest.raises(ValueError, match="inlet"):
        detect_anomalies(
            sysd.data.drop(columns="inlet_m3h"),
            sysd.schedule,
            DetectorConfig(design_flow_m3h=sysd.design_flow_m3h),
        )
    with pytest.raises(ValueError, match="design flow"):
        detect_anomalies(sysd.data, sysd.schedule, DetectorConfig(design_flow_m3h={"A": 10}))


@pytest.mark.slow
def test_benchmark_detection_and_false_alarm_rates():
    summary, fa = run_benchmark(seeds=range(10))
    assert (summary["detection_rate"] == 1.0).all()
    assert fa.set_index("run").loc["clean", "mean_per_week"] < 0.1
