"""
Täglicher Ticker-Check: Holt aktuelle Index-Mitglieder von Wikipedia
und aktualisiert tickers_config.json.

Indizes:
  QQQ  → NASDAQ-100  (100 Aktien)
  SPX  → S&P 500     (~503 Aktien)
  DAX  → DAX 40      (40 Aktien, Ticker mit .DE-Suffix)
"""
import subprocess
subprocess.run(["pip", "install", "yfinance", "pandas", "lxml", "html5lib", "-q"])

import json
import os
from datetime import datetime

import pandas as pd

CONFIG_FILE = "tickers_config.json"


# ── Hilfsfunktionen ──────────────────────────────────────────────────────────

def _find_ticker_col(df):
    """Findet die Spalte mit Ticker-Symbolen (Ticker, Symbol, o.Ä.)."""
    for col in df.columns:
        low = str(col).lower()
        if low in ("ticker", "symbol", "ticker symbol"):
            return col
    return None


def fetch_nasdaq100():
    url = "https://en.wikipedia.org/wiki/Nasdaq-100"
    tables = pd.read_html(url, header=0)
    for t in tables:
        col = _find_ticker_col(t)
        if col is None:
            continue
        tickers = (
            t[col].dropna().astype(str)
            .str.strip()
            .tolist()
        )
        tickers = [tk for tk in tickers if tk and tk != col and len(tk) <= 6]
        if len(tickers) >= 90:
            return sorted(set(tickers))
    raise ValueError("NASDAQ-100-Tabelle nicht gefunden")


def fetch_sp500():
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    tables = pd.read_html(url, header=0)
    df = tables[0]
    col = _find_ticker_col(df)
    if col is None:
        raise ValueError("S&P-500-Tabelle: Ticker-Spalte nicht gefunden")
    tickers = (
        df[col].dropna().astype(str)
        .str.strip()
        # yfinance erwartet '-' statt '.' (z.B. BRK-B statt BRK.B)
        .str.replace(".", "-", regex=False)
        .tolist()
    )
    tickers = [tk for tk in tickers if tk and len(tk) <= 8]
    if len(tickers) < 490:
        raise ValueError(f"S&P 500: nur {len(tickers)} Ticker – prüfe Tabellenformat")
    return sorted(set(tickers))


def fetch_dax():
    url = "https://en.wikipedia.org/wiki/DAX"
    tables = pd.read_html(url, header=0)
    for t in tables:
        col = _find_ticker_col(t)
        if col is None:
            continue
        tickers = (
            t[col].dropna().astype(str)
            .str.strip()
            .tolist()
        )
        tickers = [tk for tk in tickers if tk and tk != col and len(tk) <= 12]
        if len(tickers) < 30:
            continue
        # .DE-Suffix ergänzen falls nötig
        result = []
        for tk in tickers:
            if not tk.endswith(".DE"):
                tk = tk + ".DE"
            result.append(tk)
        return sorted(set(result))
    raise ValueError("DAX-Tabelle nicht gefunden")


# ── Hauptlogik ───────────────────────────────────────────────────────────────

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
        print(f"  + neu:     {', '.join(added)}")
    if removed:
        print(f"  - entfernt: {', '.join(removed)}")
    if not added and not removed:
        print("  keine Änderungen")
    return bool(added or removed)


def main():
    cfg = load_config()
    changed = False

    fetchers = [
        ("QQQ",  fetch_nasdaq100, "NASDAQ-100"),
        ("SPX",  fetch_sp500,     "S&P 500"),
        ("DAX",  fetch_dax,       "DAX 40"),
    ]

    for key, fetcher, label in fetchers:
        print(f"\n{label} ({key})...")
        try:
            new_tickers = fetcher()
            print(f"  {len(new_tickers)} Ticker von Wikipedia")
            old_tickers = cfg.get(key, [])
            diff = report_diff(key, old_tickers, new_tickers)
            cfg[key] = new_tickers
            if diff:
                changed = True
        except Exception as e:
            print(f"  FEHLER: {e} – behalte bisherige Liste")

    save_config(cfg)
    print(f"\nGespeichert: {CONFIG_FILE}")
    for key, _, label in fetchers:
        n = len(cfg.get(key, []))
        print(f"  {key}: {n} Ticker")

    if not changed:
        print("\nKeine Ticker-Änderungen seit letztem Lauf.")


if __name__ == "__main__":
    main()
