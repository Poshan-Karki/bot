

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from client import BinanceFuturesClient, BinanceAPIError, NetworkError
from validataors import (
    validate_symbol,
    validate_side,
    validate_order_type,
    validate_quantity,
    validate_price,
    validate_stop_price,
)

logger = logging.getLogger("trading_bot.orders")




@dataclass
class OrderResult:
    success: bool
    order_id: int | None = None
    symbol: str = ""
    side: str = ""
    order_type: str = ""
    status: str = ""
    executed_qty: float = 0.0
    avg_price: float = 0.0
    raw: dict = field(default_factory=dict)
    error: str = ""

    def print_summary(self) -> None:
        """Pretty-print to stdout (mirrors what the CLI shows)."""
        sep = "─" * 56
        if self.success:
            print(f"\n{sep}")
            print(f"   ORDER ACCEPTED")
            print(f"{sep}")
            print(f"  Order ID   : {self.order_id}")
            print(f"  Symbol     : {self.symbol}")
            print(f"  Side       : {self.side}")
            print(f"  Type       : {self.order_type}")
            print(f"  Status     : {self.status}")
            print(f"  Exec Qty   : {self.executed_qty}")
            print(f"  Avg Price  : {self.avg_price if self.avg_price else 'N/A (pending)'}")
            print(f"{sep}\n")
        else:
            print(f"\n{sep}")
            print(f"  ❌  ORDER FAILED")
            print(f"{sep}")
            print(f"  Reason     : {self.error}")
            print(f"{sep}\n")


def _parse_response(raw: dict) -> OrderResult:
    """Map a raw Binance order response to an OrderResult."""
    return OrderResult(
        success=True,
        order_id=raw.get("orderId"),
        symbol=raw.get("symbol", ""),
        side=raw.get("side", ""),
        order_type=raw.get("type", ""),
        status=raw.get("status", ""),
        executed_qty=float(raw.get("executedQty", 0)),
        avg_price=float(raw.get("avgPrice", 0) or 0),
        raw=raw,
    )




class OrderPlacer:
    """
    High-level order placement with validation + logging.

    Parameters
    ----------
    client : BinanceFuturesClient
    """

    def __init__(self, client: BinanceFuturesClient):
        self._client = client

    # ── Public methods ────────────────────────────────────────────────────────

    def place_market_order(self, symbol: str, side: str, quantity: float) -> OrderResult:
        """Place a MARKET order."""
        symbol = validate_symbol(symbol)
        side = validate_side(side)
        quantity = validate_quantity(quantity)

        params = dict(symbol=symbol, side=side, type="MARKET", quantity=quantity)
        return self._execute(params)

    def place_limit_order(
        self, symbol: str, side: str, quantity: float, price: float
    ) -> OrderResult:
        """Place a LIMIT GTC order."""
        symbol = validate_symbol(symbol)
        side = validate_side(side)
        quantity = validate_quantity(quantity)
        price = validate_price(price, "LIMIT")

        params = dict(
            symbol=symbol,
            side=side,
            type="LIMIT",
            quantity=quantity,
            price=price,
            timeInForce="GTC",
        )
        return self._execute(params)

    def place_stop_market_order(
        self, symbol: str, side: str, quantity: float, stop_price: float
    ) -> OrderResult:
        """
        Place a STOP_MARKET order (bonus order type).
        Triggers a market order when stopPrice is hit.
        """
        symbol = validate_symbol(symbol)
        side = validate_side(side)
        quantity = validate_quantity(quantity)
        stop_price = validate_stop_price(stop_price, "STOP_MARKET")

        params = dict(
            symbol=symbol,
            side=side,
            type="STOP_MARKET",
            quantity=quantity,
            stopPrice=stop_price,
        )
        return self._execute(params)

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: float | None = None,
        stop_price: float | None = None,
    ) -> OrderResult:
        """
        Unified dispatcher — routes to the specific method based on order_type.
        """
        order_type = validate_order_type(order_type)
        if order_type == "MARKET":
            return self.place_market_order(symbol, side, quantity)
        elif order_type == "LIMIT":
            return self.place_limit_order(symbol, side, quantity, price)
        elif order_type == "STOP_MARKET":
            return self.place_stop_market_order(symbol, side, quantity, stop_price)
        else:
            raise ValueError(f"Unsupported order type: {order_type}")

    

    def run_strategy_order(
        self,
        df: pd.DataFrame,
        symbol: str,
        quantity: float,
        order_type: str = "MARKET",
        price: float | None = None,
    ) -> OrderResult | None:
        """
        Inspect the latest signal row of a strategy DataFrame and place an order
        if the signal is non-zero.

        Signal convention:
          +1 → BUY
          -1 → SELL
           0 → hold (no order placed, returns None)

        Parameters
        ----------
        df          : output of strategy_with_risk_and_trend()
        symbol      : trading pair, e.g. "BTCUSDT"
        quantity    : contract quantity
        order_type  : "MARKET" or "LIMIT"
        price       : required when order_type == "LIMIT"
        """
        if "signal" not in df.columns:
            raise ValueError("DataFrame must contain a 'signal' column.")

        latest_signal = int(df["signal"].iloc[-1])
        latest_price = float(df["close"].iloc[-1])

        if latest_signal == 0:
            logger.info("Strategy signal: HOLD — no order placed.")
            return None

        side = "BUY" if latest_signal == 1 else "SELL"
        logger.info(
            "Strategy signal: %s at close price %.4f", side, latest_price
        )

        return self.place_order(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
        )

    

    def _execute(self, params: dict[str, Any]) -> OrderResult:
        logger.info(
            "Placing order → symbol=%s side=%s type=%s qty=%s%s",
            params.get("symbol"),
            params.get("side"),
            params.get("type"),
            params.get("quantity"),
            f" price={params['price']}" if "price" in params else "",
        )
        try:
            raw = self._client.place_order(**params)
            result = _parse_response(raw)
            logger.info(
                "Order accepted → id=%s status=%s execQty=%s avgPrice=%s",
                result.order_id,
                result.status,
                result.executed_qty,
                result.avg_price or "N/A",
            )
            return result
        except BinanceAPIError as exc:
            logger.error("Binance API error: %s", exc)
            return OrderResult(success=False, error=str(exc))
        except NetworkError as exc:
            logger.error("Network error: %s", exc)
            return OrderResult(success=False, error=str(exc))
        except ValueError as exc:
            logger.error("Validation error: %s", exc)
            return OrderResult(success=False, error=str(exc))