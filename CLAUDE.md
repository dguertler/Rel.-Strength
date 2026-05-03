# Claude Code – Projektregeln

## Branch-Strategie

**Alle Änderungen direkt auf `main` committen und pushen.**

Kein Feature-Branching. Der `main`-Branch ist der einzige aktive Branch.

## Repository-Übersicht

- `rs_colab.py` – NASDAQ/QQQ-Daten (yfinance → rs_full.json)
- `dax_colab.py` – DAX-Daten (yfinance → rs_dax.json)
- `check_alerts.py` – Breakout-Alert-Engine (GWS-Analyse + E-Mail)
- `alerts_state.json` – Alert-Zustandsdatei (von GitHub Actions verwaltet)
- `index.html` – QQQ/NASDAQ-Dashboard (React)
- `dax.html` – DAX-Dashboard (React)
- `.github/workflows/` – GitHub Actions Workflows

## Automatische Workflows

| Workflow | Zeitplan | Zweck |
|---|---|---|
| `update_rs.yml` | Mo–Fr 21:00, 04:00, 08:30 UTC | NASDAQ-Daten aktualisieren |
| `update_dax.yml` | Mo–Fr 17:00 + 17:30 UTC | DAX-Daten aktualisieren |
| `stock_alerts.yml` | Di–Sa 02:00 UTC (03:00 MEZ) | Breakout-Alarm prüfen + E-Mail |

Die Datendateien (`rs_full.json`, `rs_dax.json`, `alerts_state.json`) werden ausschließlich von GitHub Actions geschrieben – nie manuell ändern.

## Änderungsprotokoll

Nach jeder Änderung den Git-Commit-Hash explizit nennen, z. B.:

> Änderung committed: `bd675b4`

So kann der Stand vor einer Änderung jederzeit wiederhergestellt werden:
```bash
git checkout <hash-davor> -- <datei>
```
