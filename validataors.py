
from __future__ import annotations

VALID_SIDES = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"MARKET", "LIMIT", "STOP_MARKET"}


def validate_symbol(symbol: str) -> str:
    s = symbol.strip().upper()
    if not s:
        raise ValueError("Symbol must not be empty.")
    if len(s) < 3:
        raise ValueError(f"Symbol '{s}' looks invalid (too short).")
    return s


def validate_side(side: str) -> str:
    s = side.strip().upper()
    if s not in VALID_SIDES:
        raise ValueError(f"Side must be one of {VALID_SIDES}. Got: '{side}'.")
    return s


def validate_order_type(order_type: str) -> str:
    t = order_type.strip().upper()
    if t not in VALID_ORDER_TYPES:
        raise ValueError(
            f"Order type must be one of {VALID_ORDER_TYPES}. Got: '{order_type}'."
        )
    return t


def validate_quantity(quantity: float | str) -> float:
    try:
        q = float(quantity)
    except (TypeError, ValueError):
        raise ValueError(f"Quantity must be a positive number. Got: '{quantity}'.")
    if q <= 0:
        raise ValueError(f"Quantity must be > 0. Got: {q}.")
    return q


def validate_price(price: float | str | None, order_type: str) -> float | None:
    """
    Price is required for LIMIT and STOP_MARKET orders.
    Returns None for MARKET orders.
    """
    if order_type == "MARKET":
        return None
    if price is None:
        raise ValueError(f"Price is required for {order_type} orders.")
    try:
        p = float(price)
    except (TypeError, ValueError):
        raise ValueError(f"Price must be a positive number. Got: '{price}'.")
    if p <= 0:
        raise ValueError(f"Price must be > 0. Got: {p}.")
    return p


def validate_stop_price(stop_price: float | str | None, order_type: str) -> float | None:
    """Stop price is required for STOP_MARKET orders."""
    if order_type != "STOP_MARKET":
        return None
    if stop_price is None:
        raise ValueError("--stop-price is required for STOP_MARKET orders.")
    try:
        sp = float(stop_price)
    except (TypeError, ValueError):
        raise ValueError(f"Stop price must be a positive number. Got: '{stop_price}'.")
    if sp <= 0:
        raise ValueError(f"Stop price must be > 0. Got: {sp}.")
    return sp