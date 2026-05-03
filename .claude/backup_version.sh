#!/bin/bash
# Versioned backup before file edits. Max 5 versions per file, oldest deleted automatically.

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

# Skip backing up files inside .versions/ itself
if [[ "$FILE_PATH" == *"/.versions/"* ]]; then
    exit 0
fi

REPO_DIR="/home/user/Rel.-Strength"
BACKUP_DIR="$REPO_DIR/.versions"
mkdir -p "$BACKUP_DIR"

FILENAME=$(basename "$FILE_PATH")
# Split name and extension
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
VERSION_FILE="${BACKUP_DIR}/${BASENAME}_v$(printf '%03d' $NEXT_VER)_${TIMESTAMP}${EXT_DOT}"

cp "$FILE_PATH" "$VERSION_FILE"

# Keep only 5 most recent versions – delete oldest
VERSIONS=($(ls $PATTERN 2>/dev/null | sort))
TOTAL=${#VERSIONS[@]}
if [ "$TOTAL" -gt 5 ]; then
    DELETE_COUNT=$((TOTAL - 5))
    for i in $(seq 0 $((DELETE_COUNT - 1))); do
        rm "${VERSIONS[$i]}"
        echo "Alte Version gelöscht: $(basename ${VERSIONS[$i]})"
    done
fi

echo "Version gespeichert: $(basename $VERSION_FILE)"
exit 0
