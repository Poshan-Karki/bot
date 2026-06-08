

from __future__ import annotations
import os
from dotenv import load_dotenv
load_dotenv()

import hashlib
import hmac
import logging
import time
from typing import Any
from urllib.parse import urlencode

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger("trading_bot.client")

BASE_URL = "https://testnet.binancefuture.com"


# ── Custom exceptions ─────────────────────────────────────────────────────────

class BinanceAPIError(Exception):
    """Raised when the Binance API returns a non-2xx status or error payload."""

    def __init__(self, code: int, message: str, status_code: int = 0):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(f"[HTTP {status_code}] Binance error {code}: {message}")


class NetworkError(Exception):
    """Raised on connection / timeout failures."""


# ── Client ────────────────────────────────────────────────────────────────────

class BinanceFuturesClient:
  

    def __init__(self, api_key: str, api_secret: str, timeout: int = 10):
        if not api_key or not api_secret:
            raise ValueError("api_key and api_secret must not be empty.")
        self._api_key = os.getenv('api_key')
        self._api_secret = os.getenv('secret_key')
        self._timeout = timeout
        self._session = self._build_session()
        logger.debug("BinanceFuturesClient initialised (testnet).")

    # ── Session setup ─────────────────────────────────────────────────────────

    @staticmethod
    def _build_session() -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist={500, 502, 503, 504},
            allowed_methods={"GET", "POST", "DELETE"},
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        return session

    # ── Signing ───────────────────────────────────────────────────────────────

    def _sign(self, params: dict) -> dict:
        params["timestamp"] = int(time.time() * 1000)
        query = urlencode(params)
        sig = hmac.new(
    self._api_secret.encode(),   # 👈 FIX HERE
    query.encode(),
    hashlib.sha256
).hexdigest()
        params["signature"] = sig
        return params

    # ── Raw HTTP helpers ──────────────────────────────────────────────────────

    def _request(
        self, method: str, path: str, params: dict | None = None, signed: bool = True
    ) -> Any:
        params = params or {}
        if signed:
            params = self._sign(params)

        url = BASE_URL + path
        headers = {"X-MBX-APIKEY": self._api_key}

        logger.debug("→ %s %s | params: %s", method.upper(), url, {
            k: v for k, v in params.items() if k not in ("signature", "timestamp")
        })

        try:
            if method.upper() == "GET":
                resp = self._session.get(
                    url, params=params, headers=headers, timeout=self._timeout
                )
            elif method.upper() == "POST":
                resp = self._session.post(
                    url, params=params, headers=headers, timeout=self._timeout
                )
            elif method.upper() == "DELETE":
                resp = self._session.delete(
                    url, params=params, headers=headers, timeout=self._timeout
                )
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
        except requests.exceptions.ConnectionError as exc:
            logger.error("Network connection error: %s", exc)
            raise NetworkError(f"Connection failed: {exc}") from exc
        except requests.exceptions.Timeout as exc:
            logger.error("Request timed out: %s", exc)
            raise NetworkError(f"Request timed out: {exc}") from exc
        except requests.exceptions.RequestException as exc:
            logger.error("Unexpected request error: %s", exc)
            raise NetworkError(f"Request error: {exc}") from exc

        logger.debug("← HTTP %s | body: %s", resp.status_code, resp.text[:500])

        # Attempt JSON parse
        try:
            data = resp.json()
        except ValueError:
            resp.raise_for_status()
            return resp.text

        # Binance error payload: {"code": <negative int>, "msg": "..."}
        if isinstance(data, dict) and "code" in data and data["code"] != 200:
            raise BinanceAPIError(
                code=data["code"],
                message=data.get("msg", "Unknown error"),
                status_code=resp.status_code,
            )

        if not resp.ok:
            raise BinanceAPIError(
                code=resp.status_code,
                message=resp.text,
                status_code=resp.status_code,
            )

        return data

    # ── Public API methods ────────────────────────────────────────────────────

    def get_exchange_info(self) -> dict:
        """Fetch exchange trading rules (public, no signing needed)."""
        return self._request("GET", "/fapi/v1/exchangeInfo", signed=False)

    def get_account(self) -> dict:
        """Fetch futures account information."""
        return self._request("GET", "/fapi/v2/account")

    def get_position_risk(self, symbol: str | None = None) -> list[dict]:
        """Fetch current position risk (all symbols or filtered)."""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/fapi/v2/positionRisk", params=params)

    def place_order(self, **params) -> dict:
        """
        POST /fapi/v1/order

        Required params vary by order type; caller is responsible for providing
        the correct subset.  See orders.py for the assembler.
        """
        return self._request("POST", "/fapi/v1/order", params=dict(params))

    def cancel_order(self, symbol: str, order_id: int) -> dict:
        """Cancel an open order by orderId."""
        return self._request(
            "DELETE", "/fapi/v1/order", params={"symbol": symbol, "orderId": order_id}
        )

    def get_open_orders(self, symbol: str | None = None) -> list[dict]:
        """List all open orders, optionally filtered by symbol."""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/fapi/v1/openOrders", params=params)