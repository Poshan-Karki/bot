"""
strategy.py – EMA + Volume trend-following strategy with stop-loss / take-profit.

Ported from the candidate's original logic; no behavioural changes.
"""

from __future__ import annotations

import pandas as pd


def strategy_with_risk_and_trend(
    df: pd.DataFrame,
    vol_window: int = 20,
    ema_short: int = 50,
    ema_long: int = 200,
    stop_loss_pct: float = 0.02,
    take_profit_pct: float = 0.04,
) -> pd.DataFrame:
    """
    Volume-confirmed EMA crossover strategy with stop-loss and take-profit.

    Entry conditions (long only):
      - volume > rolling average volume   (volume confirmation)
      - EMA-50 > EMA-200                  (uptrend filter)
      - not currently in a position

    Exit conditions:
      - price ≤ entry × (1 − stop_loss_pct)   → stop-loss
      - price ≥ entry × (1 + take_profit_pct) → take-profit

    Returns
    -------
    DataFrame with additional columns:
      vol_avg, ema50, ema200, signal (1=buy, -1=sell, 0=hold), position (0/1)
    """
    df = df.copy()

    df["vol_avg"] = df["volume"].rolling(vol_window).mean()
    df["ema50"] = df["close"].ewm(span=ema_short, adjust=False).mean()
    df["ema200"] = df["close"].ewm(span=ema_long, adjust=False).mean()

    df["signal"] = 0
    df["position"] = 0

    entry_price: float | None = None

    for i in range(max(vol_window, ema_long), len(df)):
        price = df["close"].iloc[i]
        vol = df["volume"].iloc[i]
        vol_avg = df["vol_avg"].iloc[i]
        ema50 = df["ema50"].iloc[i]
        ema200 = df["ema200"].iloc[i]
        prev_pos = df["position"].iloc[i - 1]

        if vol > vol_avg and ema50 > ema200 and prev_pos == 0:
            # ── Entry ──────────────────────────────────────────────────────
            df.loc[df.index[i], "signal"] = 1
            df.loc[df.index[i], "position"] = 1
            entry_price = price

        elif prev_pos == 1:
            # ── Manage open position ───────────────────────────────────────
            df.loc[df.index[i], "position"] = 1

            if price <= entry_price * (1 - stop_loss_pct):      # Stop-loss
                df.loc[df.index[i], "signal"] = -1
                df.loc[df.index[i], "position"] = 0
                entry_price = None

            elif price >= entry_price * (1 + take_profit_pct):  # Take-profit
                df.loc[df.index[i], "signal"] = -1
                df.loc[df.index[i], "position"] = 0
                entry_price = None

        else:
            df.loc[df.index[i], "position"] = 0

    return df