"""Prism forecasting agents.

Three "risk scenario" agents share one underlying model-selection +
backtesting pipeline:

  1. build_daily_series   — collapse raw rows into a regular daily series
  2. backtest_candidates  — fit several candidate models on a holdout
                             split, score each by backtested MAPE/RMSE/MAE
  3. select_and_forecast  — refit the winning model on the full series,
                             produce conservative / moderate / aggressive
                             revenue projections from its confidence band

Conservative = lower-bound (pessimistic) forecast, Moderate = point
(expected) forecast, Aggressive = upper-bound (optimistic) forecast —
plus each agent keeps its own supporting analysis (region/product
breakdown for conservative, anomaly detection for aggressive).
"""

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import curve_fit
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from sklearn.ensemble import IsolationForest
import warnings

warnings.filterwarnings("ignore")

MIN_POINTS = 14
FORECAST_HORIZON = 30
CONF_ALPHA = 0.20  # 80% confidence band for the conservative/aggressive spread


# ---------------------------------------------------------------------------
# Series prep
# ---------------------------------------------------------------------------

def build_daily_series(df: pd.DataFrame) -> pd.Series:
    """Collapse raw rows into a daily revenue series with no calendar gaps
    (models need a regular frequency; missing days are treated as $0)."""
    daily = df.groupby("date")["revenue"].sum().sort_index()
    full_index = pd.date_range(daily.index.min(), daily.index.max(), freq="D")
    daily = daily.reindex(full_index, fill_value=0.0)
    daily.index.name = "date"
    return daily


def _forecast_table(series: pd.Series, values) -> list:
    last_date = series.index[-1]
    return [
        {
            "day": i + 1,
            "date": str((last_date + pd.Timedelta(days=i + 1)).date()),
            "predicted_revenue": round(float(v), 2),
        }
        for i, v in enumerate(values)
    ]


def _insufficient_data_response(agent_name: str, n_points: int) -> dict:
    return {
        "agent": agent_name,
        "error": f"Not enough data for forecasting. Found {n_points} daily data points, need at least {MIN_POINTS}.",
        "insight": "Upload at least two weeks of daily sales history for a reliable forecast.",
    }


# ---------------------------------------------------------------------------
# Accuracy metrics
# ---------------------------------------------------------------------------

def _mape(actual, predicted):
    actual, predicted = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    mask = actual != 0
    if not mask.any():
        return None
    return float(np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask])) * 100)


def _rmse(actual, predicted):
    actual, predicted = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    return float(np.sqrt(np.mean((actual - predicted) ** 2)))


def _mae(actual, predicted):
    actual, predicted = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    return float(np.mean(np.abs(actual - predicted)))


def _fmt_pct(v):
    return f"{v}%" if v is not None else "N/A"


# ---------------------------------------------------------------------------
# Candidate models — each fit_fn(train_series, steps) -> (forecast, label, fitted)
# ---------------------------------------------------------------------------

def _fit_arima_best(train: pd.Series, steps: int):
    """Grid search ARIMA(p,d,q) over small orders, select by lowest AIC —
    the 'model selection' step: try several specifications, keep the one
    that best explains the training data rather than guessing an order."""
    best = None
    for p in range(3):
        for d in range(2):
            for q in range(3):
                if p == 0 and q == 0:
                    continue
                try:
                    fitted = ARIMA(train, order=(p, d, q)).fit()
                    if best is None or fitted.aic < best[0]:
                        best = (fitted.aic, (p, d, q), fitted)
                except Exception:
                    continue
    if best is None:
        raise ValueError("ARIMA fit failed for all candidate orders")
    _, order, fitted = best
    forecast = np.asarray(fitted.forecast(steps=steps))
    return forecast, f"ARIMA{order}", fitted


def _fit_holt_winters(train: pd.Series, steps: int):
    seasonal_periods = 7 if len(train) >= 21 else None
    kwargs = dict(trend="add", damped_trend=True)
    if seasonal_periods:
        kwargs.update(seasonal="add", seasonal_periods=seasonal_periods)
    fitted = ExponentialSmoothing(train, **kwargs).fit()
    forecast = np.asarray(fitted.forecast(steps))
    label = "Holt-Winters" if seasonal_periods else "Holt Linear Trend"
    return forecast, label, fitted


def _fit_log_linear_growth(train: pd.Series, steps: int):
    """Numerical-optimization candidate: fit a * exp(b*x) + c via
    scipy.optimize.curve_fit (Levenberg-Marquardt) rather than the
    closed-form linear regression used for the descriptive trend line."""
    x = np.arange(len(train), dtype=float)
    y_shift = train.values.astype(float) + 1.0  # avoid log(0)/domain issues at 0

    def growth(x, a, b, c):
        return a * np.exp(b * x) + c

    p0 = [max(y_shift[0], 1.0), 0.001, 0.0]
    params, _ = curve_fit(
        growth, x, y_shift, p0=p0, maxfev=5000,
        bounds=([0, -1, -np.inf], [np.inf, 1, np.inf]),
    )
    future_x = np.arange(len(train), len(train) + steps, dtype=float)
    forecast = growth(future_x, *params) - 1.0
    return forecast, "Log-linear Growth (curve_fit)", params


CANDIDATES = [
    ("arima", _fit_arima_best),
    ("holt_winters", _fit_holt_winters),
    ("log_linear", _fit_log_linear_growth),
]


def backtest_candidates(series: pd.Series):
    """Fit every candidate on a holdout split, score each against the
    real held-out days, return them ranked best-first (lowest MAPE)."""
    n = len(series)
    holdout = min(14, max(3, n // 4))
    train, test = series.iloc[:-holdout], series.iloc[-holdout:]

    results = []
    for name, fit_fn in CANDIDATES:
        try:
            preds, label, _ = fit_fn(train, holdout)
            preds = np.clip(preds, 0, None)
            residual_std = float(np.std(test.values - preds))
            results.append({
                "name": name,
                "label": label,
                "mape": _mape(test.values, preds),
                "rmse": _rmse(test.values, preds),
                "mae": _mae(test.values, preds),
                "residual_std": residual_std,
            })
        except Exception:
            continue

    scored = [r for r in results if r["mape"] is not None]
    scored.sort(key=lambda r: r["mape"])
    ranked = scored if scored else sorted(results, key=lambda r: r["rmse"])
    return ranked, holdout


def select_and_forecast(series: pd.Series, horizon: int = FORECAST_HORIZON) -> dict:
    """Backtest all candidates, pick the winner, refit on the full series,
    and derive conservative/moderate/aggressive scenario forecasts from
    its confidence band."""
    ranked, holdout = backtest_candidates(series)
    if not ranked:
        raise ValueError("All candidate forecasting models failed to fit this data")

    best_name = ranked[0]["name"]
    fit_fn = dict(CANDIDATES)[best_name]

    point_forecast, label, fitted = fit_fn(series, horizon)
    point_forecast = np.clip(point_forecast, 0, None)

    if best_name == "arima":
        conf = fitted.get_forecast(steps=horizon).conf_int(alpha=CONF_ALPHA)
        lower = np.clip(conf.iloc[:, 0].values, 0, None)
        upper = np.clip(conf.iloc[:, 1].values, 0, None)
    else:
        # non-ARIMA winners don't expose a native confidence interval —
        # derive one from the model's own backtested forecast error (how
        # far off it actually was on held-out days), rather than the raw
        # series volatility, widening with horizon but capped so the band
        # doesn't blow up over a 30-day projection
        resid_std = ranked[0]["residual_std"]
        if not resid_std or np.isnan(resid_std):
            resid_std = series.std() or 1.0
        growth_steps = np.clip(np.arange(1, horizon + 1), None, holdout * 2)
        spread = resid_std * np.sqrt(growth_steps)
        z = stats.norm.ppf(1 - CONF_ALPHA / 2)
        lower = np.clip(point_forecast - z * spread, 0, None)
        upper = np.clip(point_forecast + z * spread, 0, None)

    winner = ranked[0]
    return {
        "model_used": label,
        "candidates_evaluated": [r["name"] for r in ranked],
        "backtest": {
            "holdout_days": holdout,
            "mape": round(winner["mape"], 2) if winner["mape"] is not None else None,
            "rmse": round(winner["rmse"], 2),
            "mae": round(winner["mae"], 2),
        },
        "conservative": lower,
        "moderate": point_forecast,
        "aggressive": upper,
    }


# ---------------------------------------------------------------------------
# Agent builders (all three share one forecast fit, computed once by run_all_agents)
# ---------------------------------------------------------------------------

def _build_conservative(df: pd.DataFrame, series: pd.Series, forecast: dict) -> dict:
    x = np.arange(len(series))
    y = series.values
    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
    trend = "upward" if slope > 0 else "downward" if slope < 0 else "flat"

    region_performance = df.groupby("region")["revenue"].sum().sort_values(ascending=False).to_dict()
    product_performance = df.groupby("product")["revenue"].sum().sort_values(ascending=False).to_dict()

    total = float(np.sum(forecast["conservative"]))
    mape = forecast["backtest"]["mape"]

    return {
        "agent": "conservative",
        "scenario": "Pessimistic case — lower-bound revenue projection",
        "trend": trend,
        "slope": round(slope, 2),
        "r_squared": round(r_value ** 2, 3),
        "mean_daily_revenue": round(float(series.mean()), 2),
        "std_deviation": round(float(series.std()), 2),
        "revenue_by_region": region_performance,
        "revenue_by_product": product_performance,
        "forecast_days": FORECAST_HORIZON,
        "forecasted_total_revenue": round(total, 2),
        "forecasted_daily_average": round(total / FORECAST_HORIZON, 2),
        "forecast": _forecast_table(series, forecast["conservative"]),
        "model_used": forecast["model_used"],
        "backtest": forecast["backtest"],
        "insight": (
            f"Revenue shows a {trend} trend (R²={r_value**2:.2f} against a linear baseline). "
            f"Even in a pessimistic scenario, we project ${total:,.2f} over the next {FORECAST_HORIZON} days "
            f"using {forecast['model_used']} (backtested MAPE {_fmt_pct(mape)})."
        ),
    }


def _build_moderate(series: pd.Series, forecast: dict) -> dict:
    total = float(np.sum(forecast["moderate"]))
    mape = forecast["backtest"]["mape"]

    return {
        "agent": "moderate",
        "scenario": "Expected case — point-forecast revenue projection",
        "forecast_days": FORECAST_HORIZON,
        "forecasted_total_revenue": round(total, 2),
        "forecasted_daily_average": round(total / FORECAST_HORIZON, 2),
        "forecast": _forecast_table(series, forecast["moderate"]),
        "model_used": forecast["model_used"],
        "candidates_evaluated": forecast["candidates_evaluated"],
        "backtest": forecast["backtest"],
        "insight": (
            f"{forecast['model_used']} was selected from {len(forecast['candidates_evaluated'])} candidate "
            f"models by backtested accuracy (MAPE {_fmt_pct(mape)}). We forecast ${total:,.2f} in revenue "
            f"over the next {FORECAST_HORIZON} days, averaging ${total / FORECAST_HORIZON:,.2f} per day."
        ),
    }


def _build_aggressive(df: pd.DataFrame, series: pd.Series, forecast: dict) -> dict:
    total = float(np.sum(forecast["aggressive"]))
    mape = forecast["backtest"]["mape"]

    features = pd.DataFrame({
        "revenue": df["revenue"].values,
        "units_sold": df["units_sold"].values,
        "day_of_week": df["date"].dt.dayofweek.values,
        "month": df["date"].dt.month.values,
    })
    iso_forest = IsolationForest(contamination=0.03, random_state=42)
    scores = iso_forest.fit_predict(features)

    df = df.copy()
    df["is_anomaly"] = scores == -1
    anomalies = df.loc[df["is_anomaly"], ["date", "revenue", "units_sold", "product", "region"]].copy()
    anomalies["date"] = anomalies["date"].astype(str)

    df["revenue_per_unit"] = df["revenue"] / df["units_sold"].replace(0, np.nan)
    per_unit = df.groupby("product")["revenue_per_unit"].mean().dropna()
    best_product = per_unit.idxmax() if not per_unit.empty else None
    worst_product = per_unit.idxmin() if not per_unit.empty else None

    region_avg = df.groupby("region")["revenue"].mean()
    overall_avg = df["revenue"].mean()
    underperforming = region_avg[region_avg < overall_avg].index.tolist()

    return {
        "agent": "aggressive",
        "scenario": "Optimistic case — upper-bound revenue projection",
        "forecast_days": FORECAST_HORIZON,
        "forecasted_total_revenue": round(total, 2),
        "forecasted_daily_average": round(total / FORECAST_HORIZON, 2),
        "forecast": _forecast_table(series, forecast["aggressive"]),
        "model_used": forecast["model_used"],
        "backtest": forecast["backtest"],
        "anomalies_found": int(len(anomalies)),
        "anomalies": anomalies.to_dict(orient="records"),
        "best_performing_product": best_product,
        "worst_performing_product": worst_product,
        "underperforming_regions": underperforming,
        "insight": (
            f"In an optimistic scenario, revenue could reach ${total:,.2f} over the next {FORECAST_HORIZON} days "
            f"(backtested MAPE {_fmt_pct(mape)}). We flagged {len(anomalies)} anomalous sales events via "
            f"Isolation Forest that could affect this outlook"
            + (f"; regions underperforming vs. average: {', '.join(underperforming)}." if underperforming else ".")
        ),
    }


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def run_all_agents(df: pd.DataFrame) -> dict:
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    series = build_daily_series(df)

    if len(series) < MIN_POINTS:
        insufficient = _insufficient_data_response("shared", len(series))
        return {
            "conservative": {**insufficient, "agent": "conservative"},
            "moderate": {**insufficient, "agent": "moderate"},
            "aggressive": {**insufficient, "agent": "aggressive"},
        }

    try:
        forecast = select_and_forecast(series)
    except Exception as e:
        failed = {
            "agent": "shared",
            "error": f"Forecasting failed: {e}",
            "insight": "Your data may have gaps, non-numeric values, or too little variation to model.",
        }
        return {
            "conservative": {**failed, "agent": "conservative"},
            "moderate": {**failed, "agent": "moderate"},
            "aggressive": {**failed, "agent": "aggressive"},
        }

    return {
        "conservative": _build_conservative(df, series, forecast),
        "moderate": _build_moderate(series, forecast),
        "aggressive": _build_aggressive(df, series, forecast),
    }


def run_conservative_agent(df: pd.DataFrame) -> dict:
    return run_all_agents(df)["conservative"]


def run_moderate_agent(df: pd.DataFrame) -> dict:
    return run_all_agents(df)["moderate"]


def run_aggressive_agent(df: pd.DataFrame) -> dict:
    return run_all_agents(df)["aggressive"]
