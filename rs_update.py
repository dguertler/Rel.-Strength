import subprocess
subprocess.run(["pip", "install", "yfinance", "pandas", "-q"])

import yfinance as yf
import pandas as pd
import json
from datetime import datetime

# ── Ticker-Universum ──────────────────────────────────────────────────────
tickers = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG", "TSLA", "AVGO", "COST",
    "NFLX", "AMD", "ADBE", "QCOM", "PEP", "INTU", "CSCO", "AMAT", "TXN", "HON",
    "AMGN", "SBUX", "BKNG", "ISRG", "GILD", "ADI", "LRCX", "REGN", "MU", "VRTX",
    "PANW", "KLAC", "SNPS", "CDNS", "MRVL", "ORLY", "CTAS", "ASML", "FTNT", "MDLZ",
    "ABNB", "MNST", "PYPL", "MELI", "NXPI", "WDAY", "CPRT", "ROST", "KDP", "AEP",
    "PCAR", "DDOG", "IDXX", "ODFL", "FAST", "BIIB", "TEAM", "EA", "ZS", "SIRI",
    "VRSK", "GEHC", "ON", "ANSS", "CTSH", "DLTR", "XEL", "FANG", "CRWD", "TTWO",
    "ILMN", "MRNA", "SMCI", "ARM", "MCHP", "ADSK", "CHTR", "PAYX", "DXCM", "CEG",
    "CCEP", "COIN", "APP", "AXON", "WELL", "HUBS", "TTD", "OKTA", "SNDK", "MSTR",
    "PLTR", "RXRX", "GFS", "LULU", "EBAY", "CSGP", "FSLR", "DASH"
]
tickers = list(set(tickers))

benchmark  = "QQQ"
rs_windows = {"5T": 5, "10T": 10, "20T": 20, "50T": 50, "6M": 126, "12M": 252}
timestamp  = datetime.now().strftime("%Y-%m-%d %H:%M")

# ── Schritt 1: RS-Scores ──────────────────────────────────────────────────
print(f"Schritt 1: RS-Berechnung für {len(tickers)} Aktien vs. QQQ...")
raw   = yf.download(tickers + [benchmark], period="1y", auto_adjust=True, progress=False)
close = raw["Close"]
qqq   = close[benchmark]

all_results = []
for ticker in tickers:
    if ticker not in close.columns:
        continue
    s = close[ticker].dropna()
    if len(s) < 50:
        continue
    windows_result = {}
    for label, days in rs_windows.items():
        try:
            windows_result[label] = round(
                float((s.iloc[-1]/s.iloc[-days]-1)*100 - (qqq.iloc[-1]/qqq.iloc[-days]-1)*100), 2
            )
        except:
            windows_result[label] = None
    score = round(sum(v for v in windows_result.values() if v is not None), 2)
    all_results.append({"ticker": ticker, "score": score, "windows": windows_result})

all_results.sort(key=lambda x: x["score"], reverse=True)
top20 = [r["ticker"] for r in all_results[:20]]
print(f"Top 20: {', '.join(top20)}")

# ── Schritt 2: OHLCV für Top 20 ──────────────────────────────────────────
print("\nSchritt 2: OHLCV für Top 20...")
raw_top = yf.download(top20, period="1y", auto_adjust=True, progress=False)

ohlcv_map = {}
for ticker in top20:
    try:
        c = raw_top["Close"][ticker].dropna()
        h = raw_top["High"][ticker].reindex(c.index)
        l = raw_top["Low"][ticker].reindex(c.index)
        o = raw_top["Open"][ticker].reindex(c.index)
        candles = []
        for date, ov, hv, lv, cv in zip(c.index, o, h, l, c):
            if pd.isna(cv):
                continue
            candles.append({
                "d": date.strftime("%Y-%m-%d"),
                "o": round(float(ov), 2),
                "h": round(float(hv), 2),
                "l": round(float(lv), 2),
                "c": round(float(cv), 2)
            })
        ohlcv_map[ticker] = candles
        print(f"  {ticker}: {len(candles)} Kerzen")
    except Exception as e:
        print(f"  Fehler {ticker}: {e}")

# ── Schritt 3: RS_DATA aufbereiten ───────────────────────────────────────
rs_data = []
for r in all_results:
    rs_data.append({
        "t": r["ticker"],
        "s": int(round(r["score"])),
        "w": {k: (int(round(v)) if v is not None else None) for k, v in r["windows"].items()}
    })

# ── Schritt 4: data.json schreiben ───────────────────────────────────────
print("\nSchritt 4: data.json generieren...")

output = {
    "timestamp": timestamp,
    "top20": top20,
    "rs_data": rs_data,
    "ohlcv_map": ohlcv_map
}

with open("data.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, separators=(",", ":"))

size_kb = len(json.dumps(output)) / 1024
print(f"\n✅ Fertig!")
print(f"   Datei:    data.json")
print(f"   Größe:    {size_kb:.0f} KB")
print(f"   Ticker:   {len(rs_data)}")
print(f"   Top 20:   {', '.join(top20)}")
print(f"   Charts:   {len(ohlcv_map)} Ticker mit OHLCV-Daten")
print(f"\n→ Nur data.json auf GitHub hochladen – index.html bleibt unverändert")
