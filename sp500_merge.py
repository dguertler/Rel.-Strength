"""
Führt rs_sp500_1.json und rs_sp500_2.json zusammen,
sortiert nach RS-Score und schreibt rs_sp500.json.
"""
import json
import math
import os

def sanitize_nan(obj):
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: sanitize_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_nan(v) for v in obj]
    return obj

parts = ["rs_sp500_1.json", "rs_sp500_2.json"]
all_data         = []
benchmark_ohlcv_w = []
benchmark_ohlcv   = []
timestamps        = []

for path in parts:
    if not os.path.exists(path):
        print(f"WARNUNG: {path} nicht gefunden – übersprungen")
        continue
    with open(path) as f:
        part = json.load(f)
    all_data.extend(part.get("data", []))
    timestamps.append(part.get("timestamp", ""))
    if not benchmark_ohlcv_w:
        benchmark_ohlcv_w = part.get("benchmark_ohlcv_w", [])
    if not benchmark_ohlcv:
        benchmark_ohlcv   = part.get("benchmark_ohlcv", [])

all_data.sort(key=lambda x: x.get("score", 0), reverse=True)
top20 = [d["ticker"] for d in all_data[:20]]

output = {
    "timestamp":        max(timestamps) if timestamps else "–",
    "benchmark":        "SPX",
    "top20":            top20,
    "data":             all_data,
    "benchmark_ohlcv_w": benchmark_ohlcv_w,
    "benchmark_ohlcv":   benchmark_ohlcv,
}

with open("rs_sp500.json", "w") as f:
    json.dump(sanitize_nan(output), f)

print(f"✅ Merge abgeschlossen: {len(all_data)} Ticker total")
print(f"   Top 5: {', '.join(top20[:5])}")
print(f"   Timestamp: {output['timestamp']}")
