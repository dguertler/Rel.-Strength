#!/bin/bash
# Versioned backup before file edits. Saves to .versions/, commits and pushes to GitHub.
# Max 5 versions per file, oldest deleted automatically.
# Large data files (>200KB) are skipped to avoid bloating the repo.

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    inp = d.get('tool_input', {})
    print(inp.get('file_path', ''))
except:
    print('')
" 2>/dev/null)

# Nothing to back up if no path or file doesn't exist yet
if [ -z "$FILE_PATH" ] || [ ! -f "$FILE_PATH" ]; then
    exit 0
fi

# Skip files inside .versions/ itself
if [[ "$FILE_PATH" == *"/.versions/"* ]]; then
    exit 0
fi

# Skip large data files (>200KB) – managed by GitHub Actions, not manually edited
FILE_SIZE=$(stat -c%s "$FILE_PATH" 2>/dev/null || echo 0)
if [ "$FILE_SIZE" -gt 204800 ]; then
    exit 0
fi

REPO_DIR="/home/user/Rel.-Strength"
BACKUP_DIR="$REPO_DIR/.versions"
mkdir -p "$BACKUP_DIR"

FILENAME=$(basename "$FILE_PATH")
if [[ "$FILENAME" == *.* ]]; then
    BASENAME="${FILENAME%.*}"
    EXT_DOT=".${FILENAME##*.}"
else
    BASENAME="$FILENAME"
    EXT_DOT=""
fi

PATTERN="${BACKUP_DIR}/${BASENAME}_v???_*${EXT_DOT}"

# Find the highest existing version number
LAST_VER=0
for f in $PATTERN; do
    [ -f "$f" ] || continue
    VER=$(basename "$f" | grep -oP '(?<=_v)\d+(?=_)' | head -1)
    [ -n "$VER" ] && [ "$((10#$VER))" -gt "$LAST_VER" ] && LAST_VER=$((10#$VER))
done

NEXT_VER=$((LAST_VER + 1))
TIMESTAMP=$(date -u '+%Y-%m-%d_%H-%M')
VERSION_BASENAME="${BASENAME}_v$(printf '%03d' $NEXT_VER)_${TIMESTAMP}${EXT_DOT}"
VERSION_FILE="${BACKUP_DIR}/${VERSION_BASENAME}"

cp "$FILE_PATH" "$VERSION_FILE"

# Keep only 5 most recent versions – delete oldest from disk and git
DELETED_VERSIONS=()
VERSIONS=($(ls $PATTERN 2>/dev/null | sort))
TOTAL=${#VERSIONS[@]}
if [ "$TOTAL" -gt 5 ]; then
    DELETE_COUNT=$((TOTAL - 5))
    for i in $(seq 0 $((DELETE_COUNT - 1))); do
        DELETED_VERSIONS+=("$(basename ${VERSIONS[$i]})")
        git -C "$REPO_DIR" rm --cached "${VERSIONS[$i]}" 2>/dev/null || true
        rm "${VERSIONS[$i]}"
    done
fi

# Commit and push the new version (and any deletions)
CURRENT_BRANCH=$(git -C "$REPO_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")
git -C "$REPO_DIR" add "$VERSION_FILE" 2>/dev/null
for del in "${DELETED_VERSIONS[@]}"; do
    git -C "$REPO_DIR" add -u "${BACKUP_DIR}/${del}" 2>/dev/null || true
done

git -C "$REPO_DIR" commit -m "Backup: ${VERSION_BASENAME}" --no-verify 2>/dev/null
git -C "$REPO_DIR" push origin "$CURRENT_BRANCH" 2>/dev/null

# Report to Claude's output
if [ ${#DELETED_VERSIONS[@]} -gt 0 ]; then
    for del in "${DELETED_VERSIONS[@]}"; do
        echo "Alte Version gelöscht: ${del}"
    done
fi
echo "Version gespeichert: ${VERSION_BASENAME} (auf GitHub gepusht, Branch: ${CURRENT_BRANCH})"
exit 0
