"""Tests for the forecasting engine in agents.py.

Uses deterministic synthetic data (fixed RNG seed) rather than mocks so
these exercise the real statsmodels/scipy/scikit-learn fitting code —
the point is to prove the forecasting is genuinely working, not just
that the functions are callable.
"""

import numpy as np
import pandas as pd
import pytest

import agents


def make_sales_df(n_days=120, seed=42, flat=False):
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2026-01-01", periods=n_days, freq="D")

    if flat:
        revenue = np.full(n_days, 500.0)
    else:
        trend = np.linspace(1000, 1800, n_days)
        weekly_seasonality = 150 * np.sin(2 * np.pi * np.arange(n_days) / 7)
        noise = rng.normal(0, 60, n_days)
        revenue = np.clip(trend + weekly_seasonality + noise, 50, None)

    regions = rng.choice(["West", "East", "Central"], size=n_days)
    products = rng.choice(["Widget", "Gadget", "Gizmo"], size=n_days)
    units = np.clip((revenue / 20).astype(int), 1, None)

    return pd.DataFrame({
        "date": dates,
        "revenue": revenue,
        "units_sold": units,
        "product": products,
        "region": regions,
    })


class TestMetrics:
    def test_mape_matches_hand_calculation(self):
        actual = [100, 200, 300]
        predicted = [110, 180, 300]
        # |10|/100 + |20|/200 + |0|/300 = 0.10 + 0.10 + 0 -> mean 0.0667 -> 6.67%
        assert agents._mape(actual, predicted) == pytest.approx(6.6667, abs=0.01)

    def test_mape_none_when_all_actuals_zero(self):
        assert agents._mape([0, 0], [1, 2]) is None

    def test_rmse_zero_for_perfect_forecast(self):
        assert agents._rmse([1, 2, 3], [1, 2, 3]) == 0


class TestRunAllAgents:
    def test_returns_three_scenario_forecasts(self):
        results = agents.run_all_agents(make_sales_df())
        assert set(results.keys()) == {"conservative", "moderate", "aggressive"}
        for key in results:
            assert "error" not in results[key]
            assert results[key]["forecasted_total_revenue"] >= 0
            assert len(results[key]["forecast"]) == agents.FORECAST_HORIZON

    def test_conservative_moderate_aggressive_are_risk_ordered(self):
        results = agents.run_all_agents(make_sales_df())
        c = results["conservative"]["forecasted_total_revenue"]
        m = results["moderate"]["forecasted_total_revenue"]
        a = results["aggressive"]["forecasted_total_revenue"]
        assert c <= m <= a

    def test_backtest_accuracy_is_sane_on_clean_synthetic_data(self):
        results = agents.run_all_agents(make_sales_df())
        mape = results["moderate"]["backtest"]["mape"]
        assert mape is not None
        # generous ceiling to avoid flakiness across library versions —
        # clean seasonal+trend synthetic data should be an easy fit
        assert mape < 50

    def test_model_selection_picks_a_real_candidate(self):
        results = agents.run_all_agents(make_sales_df())
        assert results["moderate"]["model_used"] is not None
        assert len(results["moderate"]["candidates_evaluated"]) >= 1

    def test_aggressive_agent_reports_anomaly_diagnostics(self):
        results = agents.run_all_agents(make_sales_df())
        aggressive = results["aggressive"]
        assert "anomalies_found" in aggressive
        assert isinstance(aggressive["anomalies"], list)

    def test_conservative_agent_reports_region_and_product_breakdown(self):
        results = agents.run_all_agents(make_sales_df())
        conservative = results["conservative"]
        assert conservative["revenue_by_region"]
        assert conservative["revenue_by_product"]

    def test_insufficient_data_degrades_gracefully(self):
        tiny_df = make_sales_df(n_days=5)
        results = agents.run_all_agents(tiny_df)
        for key in results:
            assert "error" in results[key]

    def test_flat_series_does_not_crash(self):
        results = agents.run_all_agents(make_sales_df(n_days=20, flat=True))
        for key in results:
            assert "error" not in results[key]

    def test_single_agent_helpers_match_run_all_agents(self):
        df = make_sales_df()
        all_results = agents.run_all_agents(df)
        assert agents.run_conservative_agent(df)["model_used"] == all_results["conservative"]["model_used"]
