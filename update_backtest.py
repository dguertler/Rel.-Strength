"""
Aktualisiert backtest_*.json für alle Ticker in den Top-20 von QQQ, SPX und DAX.

Erster Lauf (Datei fehlt):  vollständige Historie laden  (Bootstrap)
Folgende Läufe:              nur die letzten 14 Tage    (Delta)

Merge-Logik: neue Kerzen überschreiben per Datum-Key – Kursrevisionen werden
damit automatisch korrigiert.
"""
import os, json, math, sys, time
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

# ── Hilfsfunktionen ──────────────────────────────────────────────────────────

def sanitize(obj):
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):  return {k: sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):  return [sanitize(v) for v in obj]
    return obj

def df_to_ohlcv(df, fmt="%Y-%m-%d"):
    if df is None or df.empty:
        return []
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    rows = []
    for dt, row in df.iterrows():
        try:
            c = float(row["Close"])
            if pd.isna(c): continue
            rows.append({
                "d": dt.strftime(fmt),
                "o": round(float(row["Open"]), 2),
                "h": round(float(row["High"]),  2),
                "l": round(float(row["Low"]),   2),
                "c": round(c, 2),
            })
        except Exception:
            continue
    return rows

def agg_1h_to_4h(raw_1h):
    if raw_1h is None or raw_1h.empty:
        return []
    if isinstance(raw_1h.columns, pd.MultiIndex):
        raw_1h.columns = raw_1h.columns.get_level_values(0)
    raw_1h = raw_1h[["Open", "High", "Low", "Close"]].dropna()
    raw_1h.index = pd.to_datetime(raw_1h.index)
    raw_4h = raw_1h.resample("4h", offset="1h30min").agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last"}
    ).dropna()
    return df_to_ohlcv(raw_4h, fmt="%Y-%m-%d %H:%M")

def merge(existing, new_candles, key="d"):
    """Merge neue Kerzen in bestehende Liste; gleicher Key → überschreiben."""
    if not new_candles:
        return existing
    m = {c[key]: c for c in existing}
    for c in new_candles:
        m[c[key]] = c
    return sorted(m.values(), key=lambda x: x[key])

def download(ticker, **kwargs):
    """yfinance-Download mit kurzem Retry."""
    for attempt in range(1, 4):
        try:
            df = yf.download(ticker, auto_adjust=True, progress=False, **kwargs)
            if df is not None and not df.empty:
                return df
        except Exception as e:
            print(f"    Versuch {attempt} fehlgeschlagen: {e}")
        if attempt < 3:
            time.sleep(30)
    return pd.DataFrame()

# ── Top-20 Ticker aus allen drei Universen ───────────────────────────────────

def top20_from(fname):
    if not os.path.exists(fname):
        return []
    with open(fname) as f:
        return json.load(f).get("top20", [])

tickers = list(dict.fromkeys(
    top20_from("rs_full.json") +
    top20_from("rs_sp500.json") +
    top20_from("rs_dax.json")
))

if not tickers:
    print("Keine Top-20-Daten gefunden – Abbruch.")
    sys.exit(1)

print(f"Backtest-Update für {len(tickers)} Ticker: {', '.join(tickers)}")

# ── Pro Ticker laden und speichern ───────────────────────────────────────────

updated, skipped = 0, 0

for ticker in tickers:
    fname = f"backtest_{ticker.lower().replace('.', '_')}.json"
    existing = None

    if os.path.exists(fname):
        with open(fname) as f:
            existing = json.load(f)

    is_bootstrap = existing is None
    mode = "BOOTSTRAP" if is_bootstrap else "UPDATE"
    print(f"\n[{mode}] {ticker}  →  {fname}")

    try:
        if is_bootstrap:
            # Vollständige Historie ──────────────────────────────────────────
            raw_w = download(ticker, period="max", interval="1wk")
            ohlcv_w = df_to_ohlcv(raw_w)

            if not ohlcv_w:
                print("  Keine Weekly-Daten – übersprungen.")
                skipped += 1
                continue

            first_week  = datetime.strptime(ohlcv_w[0]["d"], "%Y-%m-%d")
            daily_start = (first_week - timedelta(days=90)).strftime("%Y-%m-%d")
            raw_d   = download(ticker, start=daily_start, interval="1d")
            ohlcv_d = df_to_ohlcv(raw_d)

            start_1h = (datetime.now() - timedelta(days=729)).strftime("%Y-%m-%d")
            raw_1h   = download(ticker, start=start_1h, interval="1h")
            ohlcv_4h = agg_1h_to_4h(raw_1h)

        else:
            # Inkrementell: letzte 14 Tage Daily / 3 Wochen Weekly / 10 Tage 4H
            raw_w   = download(ticker, period="21d",  interval="1wk")
            ohlcv_w = merge(existing.get("ohlcv_w", []), df_to_ohlcv(raw_w))

            raw_d   = download(ticker, period="14d",  interval="1d")
            ohlcv_d = merge(existing.get("ohlcv_d", []), df_to_ohlcv(raw_d))

            raw_1h  = download(ticker, period="10d",  interval="1h")
            ohlcv_4h = merge(existing.get("ohlcv_4h", []), agg_1h_to_4h(raw_1h))

        # Guard: mindestens 10 Kerzen pro Timeframe
        if len(ohlcv_w) < 10 or len(ohlcv_d) < 10:
            print(f"  Zu wenige Daten (W:{len(ohlcv_w)} D:{len(ohlcv_d)}) – übersprungen.")
            skipped += 1
            continue

        output = {
            "ticker":    ticker,
            "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "ohlcv_w":   ohlcv_w,
            "ohlcv_d":   ohlcv_d,
            "ohlcv_4h":  ohlcv_4h,
        }
        with open(fname, "w") as f:
            json.dump(sanitize(output), f)

        print(f"  ✓  W:{len(ohlcv_w)}  D:{len(ohlcv_d)}  4H:{len(ohlcv_4h)}"
              f"  ({ohlcv_d[-1]['d'] if ohlcv_d else '?'})")
        updated += 1

    except Exception as e:
        print(f"  Fehler: {e}")
        skipped += 1

print(f"\nFertig: {updated} aktualisiert, {skipped} übersprungen.")
if skipped == len(tickers):
    sys.exit(1)
