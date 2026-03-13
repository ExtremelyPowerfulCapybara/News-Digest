# ─────────────────────────────────────────────
#  market_data.py  —  Tickers, FX, Weatherssss
# ─────────────────────────────────────────────

import os
import requests
from config import (
    TICKER_SYMBOLS, CURRENCY_PAIRS, CURRENCY_BASES,
    WEATHER_LAT, WEATHER_LON, WEATHER_CITY
)


# ── Tickers ───────────────────────────────────

def fetch_tickers() -> list[dict]:
    """
    Fetches market data for each ticker in config using Yahoo Finance.
    Returns list of dicts with label, value, change, direction.
    """
    results = []
    for label, symbol in TICKER_SYMBOLS:
        if symbol is None:
            results.append({"label": label, "value": "—", "change": "", "direction": "flat"})
            continue
        try:
            url  = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d"
            headers = {"User-Agent": "Mozilla/5.0"}
            data = requests.get(url, headers=headers, timeout=8).json()
            meta = data["chart"]["result"][0]["meta"]

            price     = meta.get("regularMarketPrice", 0)
            prev      = meta.get("chartPreviousClose", price)
            pct_chg   = ((price - prev) / prev * 100) if prev else 0
            direction = "up" if pct_chg >= 0 else "down"

            if "IBEX" in label or "DAX" in label or "Stoxx" in label:
                val_str = f"{price:,.2f}"
            elif label == "S&P 500":
                val_str = f"{price:,.0f}"
            else:
                val_str = f"{price:.4f}"

            chg_str = f"{'▲' if direction == 'up' else '▼'} {abs(pct_chg):.1f}%"

            results.append({
                "label":     label,
                "value":     val_str,
                "change":    chg_str,
                "direction": direction,
            })
        except Exception as e:
            print(f"  [market] Failed {label}: {e}")
            results.append({
                "label":     label,
                "value":     "—",
                "change":    "",
                "direction": "flat",
            })

    return results


# ── Currency table ────────────────────────────

def _fetch_yahoo_rate(symbol: str) -> tuple[float, float, float] | None:
    """
    Returns (current_rate, prev_day, prev_week) for a Yahoo Finance symbol.
    Returns None on failure.
    """
    try:
        url     = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d"
        headers = {"User-Agent": "Mozilla/5.0"}
        data    = requests.get(url, headers=headers, timeout=8).json()
        result  = data["chart"]["result"][0]
        meta    = result["meta"]
        closes  = result["indicators"]["quote"][0]["close"]
        closes  = [c for c in closes if c is not None]

        rate      = meta.get("regularMarketPrice", 0)
        prev_day  = closes[-2] if len(closes) >= 2 else rate
        prev_week = closes[0]  if len(closes) >= 5 else rate
        return rate, prev_day, prev_week
    except Exception as e:
        print(f"  [currency] Yahoo fetch failed for {symbol}: {e}")
        return None


# Yahoo Finance symbols for each currency vs USD
_USD_SYMBOLS = {
    "USD": None,       # base, always 1.0
    "MXN": "MXN=X",   # MXN per USD
    "BRL": "BRL=X",
    "EUR": "EURUSD=X", # EUR per USD (inverted)
    "CNY": "USDCNY=X",
    "CAD": "CAD=X",
    "GBP": "GBPUSD=X", # GBP per USD (inverted)
    "JPY": "JPY=X",
}
# Currencies where Yahoo returns units-per-USD (i.e. not inverted)
_DIRECT = {"MXN", "BRL", "CNY", "CAD", "JPY"}
# Currencies where Yahoo returns USD-per-unit (inverted, multiply to get units-per-USD)
_INVERTED = {"EUR", "GBP"}


def _fetch_usd_rates() -> dict[str, tuple[float, float, float]]:
    """
    Returns a dict of currency -> (rate_vs_usd, prev_day_vs_usd, prev_week_vs_usd)
    where rate_vs_usd = units of that currency per 1 USD.
    USD itself is always (1.0, 1.0, 1.0).
    """
    rates = {"USD": (1.0, 1.0, 1.0)}
    for currency, symbol in _USD_SYMBOLS.items():
        if symbol is None:
            continue
        result = _fetch_yahoo_rate(symbol)
        if result is None:
            print(f"  [currency] Could not fetch {currency}")
            continue
        rate, prev_day, prev_week = result
        if currency in _INVERTED:
            # Yahoo gives USD-per-unit; invert to get units-per-USD
            rate      = 1.0 / rate      if rate      else 0
            prev_day  = 1.0 / prev_day  if prev_day  else 0
            prev_week = 1.0 / prev_week if prev_week else 0
        rates[currency] = (rate, prev_day, prev_week)
    return rates


def fetch_currency_table() -> dict:
    """
    Returns a dict with:
      - 'bases': list of base currency codes (for toggle buttons)
      - 'matrix': dict of base -> list of row dicts for the table
    Each row: { pair, rate, chg_1d, chg_1w }
    The default base shown first is MXN.
    """
    def fmt_chg(val):
        arrow = "▲" if val >= 0 else "▼"
        cls   = "chg-up" if val >= 0 else "chg-down"
        return {"text": f"{arrow} {abs(val):.2f}%", "cls": cls}

    def fmt_rate(rate, quote):
        # Format based on typical magnitude
        if quote in ("JPY",):
            return f"{rate:.2f}"
        if quote in ("BRL", "MXN", "CNY", "CAD"):
            return f"{rate:.4f}"
        return f"{rate:.5f}"

    usd_rates = _fetch_usd_rates()
    matrix    = {}

    for base in CURRENCY_BASES:
        if base not in usd_rates:
            continue
        base_rate, base_prev, base_week = usd_rates[base]
        rows = []
        for quote in CURRENCY_PAIRS:
            if quote == base:
                continue
            if quote not in usd_rates:
                rows.append({
                    "pair":   f"{base} / {quote}",
                    "rate":   "—",
                    "chg_1d": {"text": "—", "cls": "chg-flat"},
                    "chg_1w": {"text": "—", "cls": "chg-flat"},
                })
                continue
            try:
                q_rate, q_prev, q_week = usd_rates[quote]
                # cross rate: quote units per 1 base
                # base -> USD -> quote
                # 1 base = (1/base_rate) USD = (1/base_rate) * q_rate quote
                rate      = q_rate / base_rate      if base_rate      else 0
                prev_day  = q_prev / base_prev      if base_prev      else 0
                prev_week = q_week / base_week      if base_week      else 0

                chg_1d = ((rate - prev_day)  / prev_day  * 100) if prev_day  else 0
                chg_1w = ((rate - prev_week) / prev_week * 100) if prev_week else 0

                rows.append({
                    "pair":   f"{base} / {quote}",
                    "rate":   fmt_rate(rate, quote),
                    "chg_1d": fmt_chg(chg_1d),
                    "chg_1w": fmt_chg(chg_1w),
                })
            except Exception as e:
                print(f"  [currency] Failed cross {base}/{quote}: {e}")
                rows.append({
                    "pair":   f"{base} / {quote}",
                    "rate":   "—",
                    "chg_1d": {"text": "—", "cls": "chg-flat"},
                    "chg_1w": {"text": "—", "cls": "chg-flat"},
                })
        matrix[base] = rows

    return {"bases": CURRENCY_BASES, "matrix": matrix}


# ── Weather ───────────────────────────────────

def fetch_weather() -> dict:
    """
    Fetches current weather from Open-Meteo (no API key needed).
    """
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={WEATHER_LAT}&longitude={WEATHER_LON}"
            f"&current=temperature_2m,relative_humidity_2m,weather_code"
            f"&daily=temperature_2m_max,temperature_2m_min"
            f"&timezone=Europe/Madrid&forecast_days=1"
        )
        data    = requests.get(url, timeout=8).json()
        current = data["current"]
        daily   = data["daily"]

        temp     = round(current["temperature_2m"])
        humidity = current["relative_humidity_2m"]
        code     = current["weather_code"]
        temp_max = round(daily["temperature_2m_max"][0])
        temp_min = round(daily["temperature_2m_min"][0])
        desc     = _weather_description(code)

        return {
            "city":     WEATHER_CITY,
            "temp":     f"{temp}°C",
            "high_low": f"{temp_max}°C / {temp_min}°C",
            "humidity": f"Humedad {humidity}%",
            "desc":     desc,
        }
    except Exception as e:
        print(f"  [weather] Failed: {e}")
        return {
            "city":     WEATHER_CITY,
            "temp":     "—",
            "high_low": "—",
            "humidity": "—",
            "desc":     "Weather unavailable",
        }


def _weather_description(code: int) -> str:
    if code == 0:               return "Cielo despejado"
    if code in (1, 2, 3):       return "Parcialmente nublado"
    if code in (45, 48):        return "Niebla"
    if code in (51, 53, 55):    return "Llovizna"
    if code in (61, 63, 65):    return "Lluvia"
    if code in (71, 73, 75):    return "Nieve"
    if code in (80, 81, 82):    return "Chubascos"
    if code in (95, 96, 99):    return "Tormenta"
    return "Condiciones variables"
