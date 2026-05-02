"""
Einmaliger Backfill: Extrahiert die Top-20-Historie für QQQ, SPX und DAX
aus dem gesamten Git-Verlauf der jeweiligen JSON-Dateien.

Ergebnis: rs_top20_history.json
{
  "QQQ": [{"date": "YYYY-MM-DD", "top20": [...]}, ...],
  "SPX": [...],
  "DAX": [...]
}
"""
import subprocess
import json
import sys

SOURCES = [
    ("QQQ", "rs_full.json"),
    ("SPX", "rs_sp500.json"),
    ("DAX", "rs_dax.json"),
]
OUT_FILE = "rs_top20_history.json"


def git_commits_for_file(filepath):
    result = subprocess.run(
        ["git", "log", "--pretty=format:%H %ci", "--", filepath],
        capture_output=True, text=True
    )
    commits = []
    for line in result.stdout.strip().splitlines():
        if not line:
            continue
        parts = line.split(" ", 2)
        commit_hash = parts[0]
        commit_date = parts[1] if len(parts) > 1 else ""
        commits.append((commit_hash, commit_date[:10]))
    return commits


def get_file_at_commit(commit_hash, filepath):
    result = subprocess.run(
        ["git", "show", f"{commit_hash}:{filepath}"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except Exception:
        return None


def build_history():
    # Vorhandene Datei laden falls vorhanden
    try:
        with open(OUT_FILE) as f:
            history = json.load(f)
    except FileNotFoundError:
        history = {}

    for index_key, filepath in SOURCES:
        print(f"\n{index_key} ({filepath})")
        commits = git_commits_for_file(filepath)
        print(f"  {len(commits)} Commits gefunden")

        existing_dates = {e["date"] for e in history.get(index_key, [])}
        entries = list(history.get(index_key, []))

        new_count = 0
        for commit_hash, commit_date in commits:
            data = get_file_at_commit(commit_hash, filepath)
            if not data or "top20" not in data:
                continue
            # Datum aus dem Timestamp im JSON bevorzugen
            ts = data.get("timestamp", "")
            date_str = ts[:10] if ts else commit_date
            if not date_str:
                continue
            if date_str in existing_dates:
                continue
            entries.append({"date": date_str, "top20": data["top20"]})
            existing_dates.add(date_str)
            new_count += 1

        entries.sort(key=lambda x: x["date"])
        history[index_key] = entries
        print(f"  {new_count} neue Einträge  |  {len(entries)} gesamt")

    # Fehlende Keys mit leerer Liste initialisieren
    for key, _ in SOURCES:
        history.setdefault(key, [])

    with open(OUT_FILE, "w") as f:
        json.dump(history, f, indent=2)

    print(f"\nGespeichert: {OUT_FILE}")
    for key, _ in SOURCES:
        entries = history.get(key, [])
        if entries:
            print(f"  {key}: {len(entries)} Snapshots  "
                  f"({entries[0]['date']} – {entries[-1]['date']})")


if __name__ == "__main__":
    build_history()
