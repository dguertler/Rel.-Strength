# RS Update

Löst das RS-Daten-Update aus: pusht `.trigger` auf `main`, was den GitHub Actions Workflow startet. Der Workflow liest den Python-Code aus dem Secret `RS_SCRIPT`, führt ihn aus und committed `rs_full.json` zurück nach `main`.

## Schritte

1. Wechsle auf Branch `main` im Repo `/home/user/Rel.-Strength`
2. Schreibe das aktuelle Datum/Uhrzeit in `.trigger`:
   ```
   echo "$(date -u '+%Y-%m-%d %H:%M UTC')" > .trigger
   ```
3. Committe und pushe `.trigger`:
   ```
   git add .trigger
   git commit -m "RS Update ausgelöst"
   git push origin main
   ```
4. Informiere den User: "GitHub Actions Workflow gestartet. rs_full.json wird in ~5 Minuten aktualisiert."
