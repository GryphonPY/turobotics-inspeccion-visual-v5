from __future__ import annotations

from tools.soak_v5 import PerformanceSample, summarize_samples


def test_summarize_samples_reports_percentiles_and_rss_growth() -> None:
    samples = [
        PerformanceSample(24.0, 10.0, 100.0, 100.0, 100.0),
        PerformanceSample(30.0, 20.0, 200.0, 200.0, 110.0),
        PerformanceSample(28.0, 30.0, 300.0, 300.0, 125.0),
    ]

    summary = summarize_samples(samples)

    assert summary.sample_count == 3
    assert summary.ui_fps_p50 == 28.0
    assert summary.stage_ms_p95 > summary.stage_ms_p50
    assert summary.rss_initial_mb == 100.0
    assert summary.rss_final_mb == 125.0
    assert summary.rss_growth_mb == 25.0
