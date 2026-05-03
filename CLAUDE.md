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

## Versions-Backup-System

Vor jedem `Edit` oder `Write` läuft automatisch `.claude/backup_version.sh` (PreToolUse-Hook).

- Sicherungskopien landen in `.versions/` mit dem Format `dateiname_v001_2026-05-03_09-20.ext`
- Jede Version wird sofort committed und auf GitHub gepusht
- Pro Datei werden max. 5 Versionen behalten – die älteste wird automatisch gelöscht
- Dateien >200KB werden übersprungen (Datendateien von GitHub Actions)
- **Nach jedem Backup immer melden, welche Version gespeichert wurde**

Wiederherstellen einer Version:
```bash
cp .versions/dateiname_v003_2026-05-03_10-15.ext dateiname.ext
```
