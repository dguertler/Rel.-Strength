# Claude Code – Projektregeln

## Branch-Strategie

**Entwicklungs-Workflow mit CodeRabbit-Review:**

1. Änderungen auf einem Feature-Branch entwickeln und pushen
2. Pull Request gegen `main` erstellen
3. Auf CodeRabbit-Review warten und Feedback umsetzen
4. Erst mergen wenn **alle** dieser Bedingungen erfüllt sind:
   - CodeRabbit-Status = Approved (kein "Request Changes")
   - Alle erforderlichen CI-Checks grün
   - Ggf. erforderliche Human-Approvals vorhanden

**CodeRabbit ist immer der letzte Schritt vor "fertig".**

**CodeRabbit-Fallback:** Falls CodeRabbit nach 2 Stunden keinen Review geliefert hat:
- Review manuell neu triggern mit `@coderabbitai review`
- Falls weiterhin nicht verfügbar: bestehende CI-Checks + manuelle Code-Review als Ersatz nutzen und explizit im PR dokumentieren

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
