
from __future__ import annotations

import argparse
import os
import sys

from client import BinanceFuturesClient, BinanceAPIError, NetworkError
from logging_config import setup_logging
from orders import OrderPlacer
from validataors import (
    validate_order_type,
    validate_price,
    validate_quantity,
    validate_side,
    validate_stop_price,
    validate_symbol,
)

logger = setup_logging()
print("🔥 CLI FILE IS RUNNING")


# ── Argument parser ───────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trading_bot",
        description="Binance Futures Testnet – simple order CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument("--symbol", type=str, help="Trading pair, e.g. BTCUSDT")
    parser.add_argument(
        "--side", type=str, choices=["BUY", "SELL"], help="Order side"
    )
    parser.add_argument(
        "--type",
        dest="order_type",
        type=str,
        choices=["MARKET", "LIMIT", "STOP_MARKET"],
        default="MARKET",
        help="Order type (default: MARKET)",
    )
    parser.add_argument(
        "--quantity", type=float, help="Contract quantity (e.g. 0.001 BTC)"
    )
    parser.add_argument(
        "--price", type=float, default=None, help="Limit price (required for LIMIT)"
    )
    parser.add_argument(
        "--stop-price",
        type=float,
        default=None,
        dest="stop_price",
        help="Stop price (required for STOP_MARKET)",
    )

    # ── Credentials (env vars preferred) ─────────────────────────────────────
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="Binance API key (or set BINANCE_API_KEY env var)",
    )
    parser.add_argument(
        "--api-secret",
        type=str,
        default=None,
        help="Binance API secret (or set BINANCE_API_SECRET env var)",
    )

    # ── Misc ──────────────────────────────────────────────────────────────────
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and log inputs without sending to exchange",
    )
    parser.add_argument(
        "--strategy",
        action="store_true",
        help="Fetch recent candles and run the EMA+volume strategy before placing",
    )

    return parser




def resolve_credentials(args: argparse.Namespace) -> tuple[str, str]:
    api_key = args.api_key or os.environ.get("api_key", "")
    api_secret = args.api_secret or os.environ.get("secret_key", "")
    if not api_key or not api_secret:
        print(
            "\n❌  Credentials missing.\n"
            "    Set BINANCE_API_KEY and BINANCE_API_SECRET environment variables,\n"
            "    or pass --api-key / --api-secret on the command line.\n"
        )
        sys.exit(1)
    return api_key, api_secret



def print_request_summary(
    symbol: str,
    side: str,
    order_type: str,
    quantity: float,
    price: float | None,
    stop_price: float | None,
) -> None:
    sep = "─" * 56
    print(f"\n{sep}")
    print(f"  📋  ORDER REQUEST SUMMARY")
    print(f"{sep}")
    print(f"  Symbol     : {symbol}")
    print(f"  Side       : {side}")
    print(f"  Type       : {order_type}")
    print(f"  Quantity   : {quantity}")
    if price is not None:
        print(f"  Price      : {price}")
    if stop_price is not None:
        print(f"  Stop Price : {stop_price}")
    print(f"{sep}")



def run_strategy_flow(
    client: BinanceFuturesClient,
    symbol: str,
    quantity: float,
    order_type: str,
    price: float | None,
    dry_run: bool,
) -> None:
    """Fetch klines, run strategy, place order on signal."""
    import json

    try:
        import requests as _req

        url = "https://testnet.binancefuture.com/fapi/v1/klines"
        params = {"symbol": symbol, "interval": "1h", "limit": 250}
        resp = _req.get(url, params=params, timeout=10)
        resp.raise_for_status()
        klines = resp.json()
    except Exception as exc:
        print(f"\n❌  Failed to fetch klines: {exc}\n")
        sys.exit(1)

    import pandas as pd
    from bot.strategy import strategy_with_risk_and_trend

    df = pd.DataFrame(
        klines,
        columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "num_trades",
            "taker_buy_base", "taker_buy_quote", "ignore",
        ],
    )
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = df[col].astype(float)

    df = strategy_with_risk_and_trend(df)
    latest = df.iloc[-1]
    print(
        f"\n  Strategy (last bar) → signal={int(latest['signal'])}  "
        f"position={int(latest['position'])}  "
        f"ema50={latest['ema50']:.2f}  ema200={latest['ema200']:.2f}"
    )

    signal = int(latest["signal"])
    if signal == 0:
        print("\n  Strategy signal: HOLD — no order will be placed.\n")
        return

    side = "BUY" if signal == 1 else "SELL"
    print(f"  Strategy signal: {side}")

    if dry_run:
        print("\n  [DRY RUN] Would place order — skipping exchange call.\n")
        return

    placer = OrderPlacer(client)
    result = placer.place_order(
        symbol=symbol,
        side=side,
        order_type=order_type,
        quantity=quantity,
        price=price,
    )
    result.print_summary()


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # ── Validate required fields ──────────────────────────────────────────────
    missing = [f for f in ("symbol", "quantity") if getattr(args, f) is None]
    if not args.strategy and args.side is None:
        missing.append("side")
    if missing:
        parser.error(f"Missing required arguments: {', '.join('--' + m for m in missing)}")

    # ── Validate inputs early ─────────────────────────────────────────────────
    try:
        symbol = validate_symbol(args.symbol)
        quantity = validate_quantity(args.quantity)
        order_type = validate_order_type(args.order_type)
        price = validate_price(args.price, order_type)
        stop_price = validate_stop_price(args.stop_price, order_type)
        side = validate_side(args.side) if args.side else None
    except ValueError as exc:
        print(f"\n❌  Validation error: {exc}\n")
        sys.exit(1)

    logger.info(
        "CLI invoked: symbol=%s side=%s type=%s qty=%s price=%s stop_price=%s dry_run=%s",
        symbol, side, order_type, quantity, price, stop_price, args.dry_run,
    )

    # ── Credentials ───────────────────────────────────────────────────────────
    api_key, api_secret = resolve_credentials(args)

    # ── Build client ──────────────────────────────────────────────────────────
    try:
        client = BinanceFuturesClient(api_key=api_key, api_secret=api_secret)
    except ValueError as exc:
        print(f"\n❌  Client init error: {exc}\n")
        sys.exit(1)

    # ── Strategy mode ─────────────────────────────────────────────────────────
    if args.strategy:
        run_strategy_flow(client, symbol, quantity, order_type, price, args.dry_run)
        return

    # ── Manual order mode ─────────────────────────────────────────────────────
    print_request_summary(symbol, side, order_type, quantity, price, stop_price)

    if args.dry_run:
        print("\n  [DRY RUN] Inputs valid — skipping exchange call.\n")
        logger.info("Dry-run complete. No order sent.")
        return

    placer = OrderPlacer(client)
    try:
        result = placer.place_order(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
        )
    except Exception as exc:
        print(f"\n❌  Unexpected error: {exc}\n")
        logger.exception("Unexpected error during order placement.")
        sys.exit(1)

    result.print_summary()
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()