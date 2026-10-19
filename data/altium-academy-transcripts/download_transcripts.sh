#!/usr/bin/env bash
# Download transcripts for all Altium Academy videos
# Usage: bash download_transcripts.sh [parallel_jobs]

MANIFEST="$(dirname "$0")/manifest.tsv"
OUT_DIR="$(dirname "$0")/transcripts"
JOBS="${1:-8}"
LOG="$(dirname "$0")/download.log"
ERRORS="$(dirname "$0")/errors.log"

mkdir -p "$OUT_DIR"

download_one() {
    local video_id="$1"
    local title="$2"
    local out_file="$OUT_DIR/${video_id}.json"

    # Skip if already downloaded
    if [[ -f "$out_file" ]]; then
        echo "SKIP $video_id"
        return 0
    fi

    # Try yt-cli transcript first (uses YouTube captions)
    local result
    result=$(yt-cli transcript --video-id "$video_id" --json 2>/dev/null)

    if echo "$result" | jq -e '.segments | length > 0' >/dev/null 2>&1; then
        echo "$result" | jq --arg id "$video_id" --arg title "$title" \
            '. + {video_id: $id, title: $title}' > "$out_file"
        echo "OK $video_id: $title"
        return 0
    fi

    # Fall back: yt-dlp --write-auto-sub (auto-generated captions)
    local tmp_dir
    tmp_dir=$(mktemp -d)
    yt-dlp --cookies ~/.yt-sync/cookies.txt \
        --skip-download \
        --write-auto-sub \
        --sub-lang en \
        --sub-format json3 \
        --output "$tmp_dir/%(id)s" \
        "https://www.youtube.com/watch?v=$video_id" >/dev/null 2>&1

    local sub_file
    sub_file=$(find "$tmp_dir" -name "*.json3" 2>/dev/null | head -1)

    if [[ -n "$sub_file" ]]; then
        # Convert json3 to simple segments format
        jq --arg id "$video_id" --arg title "$title" '{
            video_id: $id,
            title: $title,
            source: "auto-sub",
            segments: [
                .events[]?
                | select(.segs? != null)
                | {
                    start: (.tStartMs / 1000),
                    duration: ((.dDurationMs // 0) / 1000),
                    text: ([.segs[]?.utf8 // ""] | join("") | gsub("\\n"; " ") | ltrimstr(" "))
                  }
                | select(.text != "")
            ]
        }' "$sub_file" > "$out_file"
        rm -rf "$tmp_dir"
        echo "AUTO $video_id: $title"
        return 0
    fi

    rm -rf "$tmp_dir"
    echo "FAIL $video_id: $title" >&2
    return 1
}

export -f download_one

echo "Downloading transcripts for $(wc -l < "$MANIFEST") videos with $JOBS parallel jobs..."
echo "Output: $OUT_DIR"
echo "Started: $(date)" | tee -a "$LOG"

# Use GNU parallel or xargs for parallelism
if command -v parallel >/dev/null 2>&1; then
    parallel --jobs "$JOBS" --colsep '\t' --progress \
        download_one {1} {2} \
        < "$MANIFEST" \
        >> "$LOG" 2>> "$ERRORS"
else
    # xargs fallback
    awk -F'\t' '{print $1 "\t" $2}' "$MANIFEST" | \
    xargs -P "$JOBS" -I{} bash -c 'download_one "$@"' _ {} \
        >> "$LOG" 2>> "$ERRORS"
fi

echo ""
echo "Done: $(date)"
echo "Transcripts: $(ls "$OUT_DIR"/*.json 2>/dev/null | wc -l) / $(wc -l < "$MANIFEST")"
echo "Errors: $(wc -l < "$ERRORS" 2>/dev/null || echo 0)"
