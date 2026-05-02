"""
Täglicher Ticker-Check: Holt aktuelle Index-Mitglieder und aktualisiert tickers_config.json.

Quellen (in Reihenfolge der Priorität):
  QQQ  → Wikipedia HTML  →  Fallback: bestehende Liste
  SPX  → GitHub-CSV (datasets/s-and-p-500-companies)  →  Fallback: bestehende Liste
  DAX  → Wikipedia HTML  →  Fallback: hardcodierte DAX-40-Liste
"""
import subprocess
subprocess.run(["pip", "install", "pandas", "lxml", "html5lib", "requests", "-q"])

import json
import os
import time
from datetime import datetime
from io import StringIO

import pandas as pd
import requests

CONFIG_FILE = "tickers_config.json"

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
})

# Hardcodierte DAX-40-Fallback-Liste (Stand 2025 – ändert sich selten)
DAX40_FALLBACK = [
    "ADS.DE", "AIR.DE", "ALV.DE", "BAS.DE", "BAYN.DE", "BEI.DE",
    "BMW.DE", "BNR.DE", "CBK.DE", "CON.DE", "1COV.DE", "DTG.DE",
    "DBK.DE", "DB1.DE", "DHL.DE", "DTE.DE", "EOAN.DE", "FRE.DE",
    "FME.DE", "HNR1.DE", "HEIG.DE", "HEN3.DE", "IFX.DE", "MRK.DE",
    "MBG.DE", "MTX.DE", "MUV2.DE", "P911.DE", "PAH3.DE", "QIA.DE",
    "RHM.DE", "RWE.DE", "SAP.DE", "SRT3.DE", "SIE.DE", "ENR.DE",
    "SHL.DE", "SY1.DE", "VOW3.DE", "VNA.DE",
]


# ── Fetch-Funktionen ─────────────────────────────────────────────────────────

def _find_ticker_col(df):
    for col in df.columns:
        if str(col).lower().strip() in ("ticker", "symbol", "ticker symbol"):
            return col
    return None


def _wikipedia_tickers(page_title, min_count, suffix=""):
    """
    Liest Wikipedia-Seite per HTML und extrahiert Ticker aus der
    ersten Tabelle mit einer Ticker/Symbol-Spalte.
    """
    url = f"https://en.wikipedia.org/wiki/{page_title}"
    try:
        resp = SESSION.get(url, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        raise ValueError(f"HTTP-Fehler für {url}: {e}")

    tables = pd.read_html(StringIO(resp.text), header=0)
    for t in tables:
        col = _find_ticker_col(t)
        if col is None:
            continue
        tickers = (
            t[col].dropna().astype(str).str.strip()
            .tolist()
        )
        tickers = [tk for tk in tickers if tk and tk != str(col) and 1 < len(tk) <= 12]
        if len(tickers) < min_count:
            continue
        if suffix:
            result = []
            for tk in tickers:
                # Falls Ticker bereits einen Börsenplatz-Suffix hat (z.B. AIR.PA),
                # diesen entfernen und durch .DE ersetzen
                if suffix == ".DE" and "." in tk and not tk.endswith(".DE"):
                    tk = tk.split(".")[0] + ".DE"
                elif not tk.endswith(suffix):
                    tk = tk + suffix
                result.append(tk)
            tickers = result
        return sorted(set(tickers))

    raise ValueError("Keine geeignete Ticker-Tabelle gefunden")


def fetch_nasdaq100():
    return _wikipedia_tickers("Nasdaq-100", min_count=90)


def fetch_sp500():
    """S&P 500 via gepflegtes GitHub-Repository (zuverlässig, ~503 Ticker)."""
    url = (
        "https://raw.githubusercontent.com/datasets/"
        "s-and-p-500-companies/master/data/constituents.csv"
    )
    try:
        resp = SESSION.get(url, timeout=20)
        resp.raise_for_status()
        df = pd.read_csv(StringIO(resp.text))
        col = _find_ticker_col(df)
        if col is None:
            col = df.columns[0]           # erste Spalte = Symbol
        tickers = (
            df[col].dropna().astype(str).str.strip()
            # yfinance: BRK.B → BRK-B
            .str.replace(".", "-", regex=False)
            .tolist()
        )
        tickers = [tk for tk in tickers if tk and len(tk) <= 8]
        if len(tickers) < 490:
            raise ValueError(f"Nur {len(tickers)} Ticker – Datei prüfen")
        return sorted(set(tickers))
    except Exception as e:
        raise ValueError(f"GitHub-CSV fehlgeschlagen: {e}")


def fetch_dax():
    try:
        return _wikipedia_tickers("DAX", min_count=30, suffix=".DE")
    except Exception:
        # Fallback: hardcodierte Liste
        print("  Wikipedia fehlgeschlagen – nutze hardcodierte DAX-40-Liste")
        return sorted(DAX40_FALLBACK)


# ── Hauptlogik ────────────────────────────────────────────────────────────────

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}


def save_config(cfg):
    cfg["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


def report_diff(label, old, new):
    old_s, new_s = set(old), set(new)
    added   = sorted(new_s - old_s)
    removed = sorted(old_s - new_s)
    if added:
        print(f"  + neu:      {', '.join(added)}")
    if removed:
        print(f"  - entfernt: {', '.join(removed)}")
    if not added and not removed:
        print("  keine Änderungen")
    return bool(added or removed)


def main():
    cfg     = load_config()
    changed = False

    fetchers = [
        ("QQQ", fetch_nasdaq100, "NASDAQ-100"),
        ("SPX", fetch_sp500,     "S&P 500"),
        ("DAX", fetch_dax,       "DAX 40"),
    ]

    for key, fetcher, label in fetchers:
        print(f"\n{label} ({key})...")
        try:
            new_tickers = fetcher()
            print(f"  {len(new_tickers)} Ticker geladen")
            old_tickers = cfg.get(key, [])
            diff = report_diff(key, old_tickers, new_tickers)
            cfg[key] = new_tickers
            if diff:
                changed = True
        except Exception as e:
            print(f"  FEHLER: {e} – behalte bisherige Liste ({len(cfg.get(key,[]))} Ticker)")

    save_config(cfg)
    print(f"\nGespeichert: {CONFIG_FILE}")
    for key, _, label in fetchers:
        n = len(cfg.get(key, []))
        print(f"  {key}: {n} Ticker")

    if not changed:
        print("\nKeine Ticker-Änderungen.")


if __name__ == "__main__":
    main()
