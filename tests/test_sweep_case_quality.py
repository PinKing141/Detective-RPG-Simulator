from noir.tools.sweep_case_quality import ci_recommendation, summarize_results, triage_candidates


def test_summarize_results_tracks_clean_rate_and_non_clean() -> None:
    results = [
        {"seed": 1, "tier": "clean", "summary": "ok"},
        {"seed": 2, "tier": "shaky", "summary": "thin"},
        {"seed": 3, "tier": "failed", "summary": "broken"},
    ]

    summary = summarize_results(results)

    assert summary["tier_counts"] == {"clean": 1, "shaky": 1, "failed": 1}
    assert summary["clean_count"] == 1
    assert summary["clean_rate"] == 1 / 3
    assert [result["seed"] for result in summary["non_clean"]] == [2, 3]


def test_triage_candidates_prefers_shaky_cases_before_failed() -> None:
    results = [
        {"seed": 1, "tier": "failed", "summary": "broken"},
        {"seed": 2, "tier": "shaky", "summary": "thin"},
        {"seed": 3, "tier": "shaky", "summary": "thin"},
        {"seed": 4, "tier": "failed", "summary": "broken"},
    ]

    triage = triage_candidates(results, limit=2)

    assert [result["seed"] for result in triage] == [2, 3]


def test_ci_recommendation_requires_target_clean_rate() -> None:
    assert ci_recommendation(0.7, None) is None
    assert "non-blocking CI/reporting job" in ci_recommendation(0.7, 0.6)
    assert "Keep --fail-on-non-clean out of automation" in ci_recommendation(0.4, 0.6)