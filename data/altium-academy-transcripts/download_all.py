#!/usr/bin/env python3
"""Download transcripts for all Altium Academy videos (fast mode: captions only)."""
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
MANIFEST = SCRIPT_DIR / "manifest.tsv"
OUT_DIR = SCRIPT_DIR / "transcripts"
LOG = SCRIPT_DIR / "download.log"
ERRORS_FILE = SCRIPT_DIR / "errors.log"
JOBS = int(sys.argv[1]) if len(sys.argv) > 1 else 16
TIMEOUT = int(sys.argv[2]) if len(sys.argv) > 2 else 20

OUT_DIR.mkdir(exist_ok=True)


def download_transcript(video_id: str, title: str) -> tuple[str, str, str]:
    """Returns (status, video_id, title). Only uses yt-cli captions (fast)."""
    out_file = OUT_DIR / f"{video_id}.json"
    if out_file.exists() and out_file.stat().st_size > 100:
        return "SKIP", video_id, title

    try:
        result = subprocess.run(
            ["yt-cli", "transcript", "--video-id", video_id, "--json"],
            capture_output=True, text=True, timeout=TIMEOUT
        )
        data = json.loads(result.stdout)
        segments = data.get("segments", [])
        if segments:
            data["video_id"] = video_id
            data["title"] = title
            out_file.write_text(json.dumps(data, ensure_ascii=False))
            return "OK", video_id, title
        else:
            return "NO_CAPTIONS", video_id, title
    except subprocess.TimeoutExpired:
        return "TIMEOUT", video_id, title
    except Exception as e:
        return f"ERR:{e}", video_id, title


def main():
    videos = []
    with open(MANIFEST) as f:
        for line in f:
            parts = line.rstrip("\n").split("\t", 1)
            if len(parts) == 2:
                videos.append((parts[0].strip(), parts[1].strip()))

    pending = [(v, t) for v, t in videos
               if not (OUT_DIR / f"{v}.json").exists() or (OUT_DIR / f"{v}.json").stat().st_size <= 100]
    already = len(videos) - len(pending)

    total = len(pending)
    print(f"Total: {len(videos)} | Already done: {already} | Pending: {total}")
    print(f"Workers: {JOBS} | Timeout: {TIMEOUT}s | Output: {OUT_DIR}")

    counters = {"OK": 0, "NO_CAPTIONS": 0, "TIMEOUT": 0, "ERR": 0}
    done = 0

    with open(LOG, "a", buffering=1) as log, open(ERRORS_FILE, "a", buffering=1) as errlog:
        log.write(f"=== Run started, {total} pending ===\n")
        with ThreadPoolExecutor(max_workers=JOBS) as executor:
            futures = {
                executor.submit(download_transcript, vid, title): (vid, title)
                for vid, title in pending
            }
            for future in as_completed(futures):
                status, vid, title = future.result()
                done += 1

                key = status if status in counters else "ERR"
                counters[key] += 1

                msg = f"[{done+already}/{len(videos)}] {status} {vid}: {title[:60]}"
                print(msg, flush=True)
                log.write(msg + "\n")

                if status not in ("OK", "NO_CAPTIONS"):
                    errlog.write(f"{status}\t{vid}\t{title}\n")

                if done % 100 == 0:
                    summary = " | ".join(f"{k}={v}" for k, v in counters.items() if v)
                    print(f"  --- {summary} ---", flush=True)

    ok_total = len(list(OUT_DIR.glob("*.json")))
    print(f"\nDone! Transcripts saved: {ok_total}/{len(videos)}")
    print(" | ".join(f"{k}={v}" for k, v in counters.items() if v))


if __name__ == "__main__":
    main()
