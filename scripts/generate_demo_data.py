"""Generates sample_data/demo_sales.csv — synthetic B2B sales data with a
real trend, weekly seasonality, regional/product mix, and a handful of
injected anomalies, so the forecasting agents and anomaly detector have
real structure to find. Deterministic (fixed seed) so the demo is
reproducible.

Run from the repo root:
    python scripts/generate_demo_data.py
"""

import numpy as np
import pandas as pd

OUT_PATH = "sample_data/demo_sales.csv"
N_DAYS = 180
SEED = 7

REGIONS = ["North America", "EMEA", "APAC"]
PRODUCTS = ["Starter Plan", "Growth Plan", "Enterprise Plan", "Add-on Seats"]
PRODUCT_BASE_PRICE = {
    "Starter Plan": 49,
    "Growth Plan": 149,
    "Enterprise Plan": 349,
    "Add-on Seats": 25,
}


def main():
    rng = np.random.default_rng(SEED)
    dates = pd.date_range("2026-02-17", periods=N_DAYS, freq="D")

    rows = []
    for day_idx, date in enumerate(dates):
        # steady month-over-month growth
        growth_factor = 1 + (day_idx / N_DAYS) * 0.5
        # weekend dip (B2B sales are lighter on weekends)
        weekend_factor = 0.4 if date.dayofweek >= 5 else 1.0
        # a larger number of smaller deals per day (higher volume = lower
        # relative day-to-day variance from deal-count alone, like a real
        # mid-market SaaS company rather than a handful of lumpy whales)
        n_deals = rng.poisson(28 * weekend_factor)

        for _ in range(n_deals):
            region = rng.choice(REGIONS, p=[0.5, 0.3, 0.2])
            product = rng.choice(PRODUCTS, p=[0.35, 0.3, 0.15, 0.2])
            base = PRODUCT_BASE_PRICE[product]
            units = max(1, int(rng.normal(2, 0.6)))
            noise = rng.normal(1.0, 0.08)
            revenue = round(base * units * growth_factor * noise, 2)

            rows.append({
                "date": date.date().isoformat(),
                "revenue": max(revenue, 10),
                "units_sold": units,
                "product": product,
                "region": region,
            })

    df = pd.DataFrame(rows)

    # inject a few clear-but-moderate anomalies (scaled to that day's own
    # typical volume) so Isolation Forest has real outliers to find without
    # swamping the overall trend the forecasting models are fitting
    daily_totals = df.groupby("date")["revenue"].sum()
    typical_day = daily_totals.median()
    # keep anomalies out of the final ~20 days so they land in the training
    # window, not the backtest holdout — a demo dataset should show off
    # what the anomaly detector catches without also wrecking the forecast
    # accuracy metric on the one random day it happens to fall on
    anomaly_days = rng.choice(N_DAYS - 20, size=4, replace=False)
    for i, day_idx in enumerate(anomaly_days):
        date = dates[day_idx].date().isoformat()
        if i % 2 == 0:
            df.loc[len(df)] = {
                "date": date, "revenue": round(typical_day * 3.5, 2), "units_sold": 25,
                "product": "Enterprise Plan", "region": rng.choice(REGIONS),
            }
        else:
            df.loc[len(df)] = {
                "date": date, "revenue": round(typical_day * 0.05, 2), "units_sold": 1,
                "product": "Add-on Seats", "region": rng.choice(REGIONS),
            }

    df = df.sort_values("date").reset_index(drop=True)
    df.to_csv(OUT_PATH, index=False)
    print(f"Wrote {len(df)} rows across {df['date'].nunique()} days to {OUT_PATH}")


if __name__ == "__main__":
    main()
