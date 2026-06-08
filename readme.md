# 📈 Binance Futures Testnet Trading Bot

A clean, production-grade Python CLI trading bot for **Binance USDT-M Futures Testnet** with structured logging, input validation, and an integrated EMA + volume trend strategy.

---

## Project Structure

```
trading_bot/
├── bot/
│   ├── __init__.py
│   ├── client.py          # Binance REST client (HMAC auth, retry, error handling)
│   ├── orders.py          # Order placement logic + strategy integration
│   ├── validators.py      # Input validation helpers
│   ├── strategy.py        # EMA-50/200 + volume strategy with SL/TP
│   └── logging_config.py  # Rotating file + console logging
├── logs/
│   └── trading_bot.log    # Auto-created; includes sample MARKET & LIMIT runs
├── cli.py                 # CLI entry point (argparse)
├── requirements.txt
└── README.md
```

---

## Setup

### 1. Get Testnet Credentials

1. Visit [https://testnet.binancefuture.com](https://testnet.binancefuture.com)
2. Log in with your GitHub account
3. Navigate to **API Management → Create API Key**
4. Copy your **API Key** and **Secret**

### 2. Install Dependencies

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Set Credentials

```bash
# macOS / Linux
export BINANCE_API_KEY="your_api_key_here"
export BINANCE_API_SECRET="your_api_secret_here"

# Windows (PowerShell)
$env:BINANCE_API_KEY="your_api_key_here"
$env:BINANCE_API_SECRET="your_api_secret_here"
```

> Alternatively, pass `--api-key` and `--api-secret` flags directly (less secure).

---

## Usage

### Market Order

```bash
# BUY 0.001 BTC at market
python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001

# SELL 0.01 ETH at market
python cli.py --symbol ETHUSDT --side SELL --type MARKET --quantity 0.01
```

### Limit Order

```bash
# Sell ETH at $3,500
python cli.py --symbol ETHUSDT --side SELL --type LIMIT --quantity 0.01 --price 3500

# Buy BTC at $60,000
python cli.py --symbol BTCUSDT --side BUY --type LIMIT --quantity 0.001 --price 60000
```

### Stop-Market Order *(Bonus order type)*

```bash
# Trigger a BUY when BTC hits $65,000
python cli.py --symbol BTCUSDT --side BUY --type STOP_MARKET --quantity 0.001 --stop-price 65000
```

### Strategy Mode

Fetches the last 250 × 1-hour candles from testnet, runs the EMA+Volume strategy, and places an order only when a signal fires:

```bash
python cli.py --symbol BTCUSDT --quantity 0.001 --strategy
```

### Dry Run (validate without sending)

```bash
python cli.py --symbol BTCUSDT --side BUY --type LIMIT --quantity 0.001 --price 60000 --dry-run
```

---

## CLI Reference

| Flag | Required | Description |
|------|----------|-------------|
| `--symbol` | ✅ | Trading pair e.g. `BTCUSDT` |
| `--side` | ✅ (non-strategy) | `BUY` or `SELL` |
| `--type` | ❌ | `MARKET` (default), `LIMIT`, `STOP_MARKET` |
| `--quantity` | ✅ | Contract quantity e.g. `0.001` |
| `--price` | LIMIT only | Limit price |
| `--stop-price` | STOP_MARKET only | Stop trigger price |
| `--api-key` | ❌ | Override env var |
| `--api-secret` | ❌ | Override env var |
| `--dry-run` | ❌ | Validate only, no exchange call |
| `--strategy` | ❌ | Run EMA strategy before placing |

---

## Strategy Logic

Located in `bot/strategy.py`. Entry/exit rules:

| Condition | Action |
|-----------|--------|
| `volume > vol_avg` AND `EMA-50 > EMA-200` AND flat | **BUY signal** (`signal = 1`) |
| In position AND `price ≤ entry × (1 − 0.02)` | **SELL signal** — stop-loss |
| In position AND `price ≥ entry × (1 + 0.04)` | **SELL signal** — take-profit |
| Otherwise | **Hold** (`signal = 0`) |

Parameters: `vol_window=20`, `ema_short=50`, `ema_long=200`, `stop_loss_pct=0.02`, `take_profit_pct=0.04`

---

## Sample Output

```
────────────────────────────────────────────────────────
  📋  ORDER REQUEST SUMMARY
────────────────────────────────────────────────────────
  Symbol     : BTCUSDT
  Side       : BUY
  Type       : MARKET
  Quantity   : 0.001
────────────────────────────────────────────────────────

────────────────────────────────────────────────────────
  ✅  ORDER ACCEPTED
────────────────────────────────────────────────────────
  Order ID   : 3891745021
  Symbol     : BTCUSDT
  Side       : BUY
  Type       : MARKET
  Status     : FILLED
  Exec Qty   : 0.001
  Avg Price  : 67245.1
────────────────────────────────────────────────────────
```

---

## Logging

All activity is logged to `logs/trading_bot.log` (rotating, max 5 MB × 3 backups):

- **DEBUG** – full request/response bodies
- **INFO** – order placement, results
- **ERROR** – API errors, network failures, validation errors

Console shows INFO and above only (clean output).

---

## Assumptions

1. **Testnet only** – base URL is hardcoded to `https://testnet.binancefuture.com`; swap `BASE_URL` in `bot/client.py` for production.
2. **Long-only strategy** – the EMA+volume strategy generates BUY entries only; SELL signals are exits (no shorting).
3. **LIMIT orders use GTC** (Good Till Cancel) time-in-force by default.
4. **Quantities** must respect Binance's minimum notional and step-size filters for each symbol (not validated client-side).
5. Strategy candle data is fetched from the public `/fapi/v1/klines` endpoint (no auth needed).
