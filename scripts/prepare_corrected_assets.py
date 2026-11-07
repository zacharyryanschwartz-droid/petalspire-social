#!/usr/bin/env python3
"""Build versioned Petalspire social clips for future posts.

Replaces the procedural music on the ten non-narrated reels with the approved
vocal theme file audio/petalspire-theme-a.mp3, starting at 0.000 seconds.
Holds each legacy clip's 1.000-second frame for the first 0.500 seconds so the
opening frame is not the black fade.

No local transcription or listening tool is used. Song start 0 is the local
draft slice. It is not a selected lyrical excerpt. Narrated promo files are
left byte-for-byte alone.
"""

from __future__ import annotations

import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY_DIR = ROOT / "videos"
SONG = ROOT / "audio" / "petalspire-theme-a.mp3"
VERSION = "v2026-11-07-theme-a-r1"
OUT_DIR = LEGACY_DIR / VERSION
COVER_DIR = OUT_DIR / "covers"
INDEX_PATH = LEGACY_DIR / "index.json"
BASE = "https://zacharyryanschwartz-droid.github.io/petalspire-social/"
SONG_SHA256 = "b1a8db25bd6ba3eb01ebe136221d72ea7ba1d8db985dc5c1da599bb8f5805570"

SELECTABLE = [
    "reel-card-pack-reveal.mp4",
    "reel-gameplay-montage-30s.mp4",
    "reel-growing.mp4",
    "reel-harvest.mp4",
    "reel-hook-moonflower-4s.mp4",
    "reel-hook-rare-card-4s.mp4",
    "reel-market-stall.mp4",
    "reel-moonflower-garden.mp4",
    "reel-tin-open.mp4",
    "reel-trading-friends.mp4",
]

EXCLUDED = [
    "reel-hook-promo-4s.mp4",
    "reel-promo-30s-framed.mp4",
    "reel-promo-30s.mp4",
]

AUDIO_MARKER = " Audio for future posts:"
EXCLUSION_MARKER = " Future posting:"


def sha256(path: Path) -> str:
    return subprocess.check_output(["sha256sum", str(path)], text=True).split()[0]


def render_one(name: str) -> None:
    source = LEGACY_DIR / name
    if not source.is_file():
        raise SystemExit(f"missing legacy video: {source}")
    stem = name[:-4]
    cover = COVER_DIR / f"{stem}.jpg"
    output = OUT_DIR / name
    if output.resolve().parent != OUT_DIR.resolve():
        raise SystemExit(f"refusing to write outside {OUT_DIR}")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-ss",
            "1",
            "-i",
            str(source),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(cover),
        ],
        check=True,
    )
    duration = float(
        subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "csv=p=0",
                str(source),
            ],
            text=True,
        ).strip()
    )
    fade_start = duration - 0.35
    filt = (
        "[0:v]trim=start=0.5,setpts=PTS-STARTPTS[v];"
        "[1:v]trim=duration=0.5,setpts=PTS-STARTPTS[c];"
        "[c][v]concat=n=2:v=1:a=0,format=yuv420p[video];"
        f"[2:a]loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=out:st={fade_start}:d=0.35[audio]"
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(source),
            "-loop",
            "1",
            "-i",
            str(cover),
            "-i",
            str(SONG),
            "-filter_complex",
            filt,
            "-map",
            "[video]",
            "-map",
            "[audio]",
            "-t",
            str(duration),
            "-r",
            "30",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "20",
            "-threads",
            "2",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-movflags",
            "+faststart",
            str(output),
        ],
        check=True,
    )
    print(f"DONE {name} duration={duration:.3f} fade_start={fade_start:.2f}", flush=True)


def scene_text(description: str, marker: str) -> str:
    return description.split(marker, 1)[0].rstrip()


def update_manifest() -> None:
    manifest = json.loads(INDEX_PATH.read_text())
    by_file = {item["file"]: item for item in manifest["videos"]}
    missing = [name for name in SELECTABLE + EXCLUDED if name not in by_file]
    if missing:
        raise SystemExit(f"manifest missing entries: {missing}")

    manifest["generated"] = "2026-11-07"
    manifest["format_notes"] = (
        "Selectable files are 1080x1920 (9:16), H.264 High + AAC LC 48 kHz stereo, "
        "30 fps, moov atom at front (faststart), under 25 MB. "
        "Original videos/*.mp4 files remain in place so previously published URLs stay unchanged."
    )
    manifest["audio_notes"] = (
        "Selectable clips replace the old procedural music with the approved vocal "
        "theme audio/petalspire-theme-a.mp3 (SHA-256 "
        f"{SONG_SHA256}), from 0.000 seconds for the full clip duration. "
        "Loudnorm is single-pass I=-16, TP=-1.5, LRA=11, with a 0.35-second fade-out and no fade-in. "
        "No transcription or listening tool was available, so this start offset is not a reviewed lyrical excerpt. "
        "Silence detection was not treated as evidence of singing. "
        "Narrated promo files are excluded: replacing their audio would erase narration, and layering this vocal may compete with speech."
    )
    manifest["selection_rule"] = (
        'Future posts must use only videos whose future_posting is "use" and must take url, path, cover_url, and cover_path from those entries. '
        'Entries with future_posting "excluded" are not corrected assets. Do not post legacy_url values.'
    )
    manifest["asset_version"] = VERSION
    manifest["song"] = {
        "file": "audio/petalspire-theme-a.mp3",
        "sha256": SONG_SHA256,
        "song_start_s": 0.0,
        "vocal_excerpt_reviewed": False,
        "role": "Approved vocal theme A for these social clips only. Not in-game music.",
        "provenance": (
            "File attached for this change. SHA-256 matches the saved October 27, 2026 profile copy named petalspire-theme-a.mp3. "
            "No Suno share URL was included with the file, and none is stated here."
        ),
    }
    manifest["review_limits"] = {
        "visual": (
            "An independent review of a local preparation copy of reel-tin-open.mp4, built with this same opening-frame recipe, "
            "reported a bright closed sage-tin first frame, a clean opening transition, and no black flashes. "
            "The other nine corrected files have not been visually reviewed. This hosted encode is a recreation, not a claim that those reviewed bytes were rechecked."
        ),
        "audio": (
            "Audio was not heard. No local transcription tool was available. "
            "vocal_excerpt_reviewed is false. Do not describe these clips as containing a confirmed lyrical section."
        ),
    }

    for name in SELECTABLE:
        item = by_file[name]
        stem = name[:-4]
        path = f"videos/{VERSION}/{name}"
        cover_path = f"videos/{VERSION}/covers/{stem}.jpg"
        output = ROOT / path
        item["future_posting"] = "use"
        item["legacy_url"] = item.get("legacy_url") or f"{BASE}videos/{name}"
        item["legacy_path"] = f"videos/{name}"
        item["path"] = path
        item["url"] = BASE + path
        item["cover_path"] = cover_path
        item["cover_url"] = BASE + cover_path
        item["thumbnail_offset_ms"] = 0
        item["size_bytes"] = output.stat().st_size
        item["width"] = 1080
        item["height"] = 1920
        item["fps"] = 30
        item["video_codec"] = "h264"
        item["audio_codec"] = "aac"
        item["audio"] = {
            "source_file": "audio/petalspire-theme-a.mp3",
            "source_sha256": SONG_SHA256,
            "song_start_s": 0.0,
            "vocal_excerpt_reviewed": False,
            "channels": 2,
            "sample_rate_hz": 48000,
            "bitrate_bps": 192000,
            "loudnorm": "I=-16:TP=-1.5:LRA=11",
            "fade_out_s": 0.35,
            "fade_in_s": 0.0,
        }
        item["cover"] = {
            "source": "JPEG from the legacy video at 1.000 seconds, quality q:v 2",
            "held_s": 0.5,
            "path": cover_path,
            "purpose": (
                "The legacy clips open on a black fade, which platforms used as the Reel cover. "
                "The first half-second of the new file is this still, so thumbnail offset 0 is a visible frame. "
                "Facebook does not take a separate thumbnail URL; the bright opening frame is the fallback."
            ),
        }
        item["description"] = (
            scene_text(item["description"], AUDIO_MARKER)
            + AUDIO_MARKER
            + " theme A from 0.000 seconds of audio/petalspire-theme-a.mp3 for the full duration "
            "(lyrical excerpt not reviewed). Cover still and opening half-second are the legacy frame at 1.000 seconds."
        )

    for name in EXCLUDED:
        item = by_file[name]
        item["future_posting"] = "excluded"
        item["audio_replaced"] = False
        item["vocal_excerpt_reviewed"] = False
        item["legacy_path"] = f"videos/{name}"
        if not str(item.get("legacy_url") or "").endswith(f"videos/{name}"):
            previous = item.get("url")
            if isinstance(previous, str) and previous.endswith(f"videos/{name}"):
                item["legacy_url"] = previous
            else:
                item["legacy_url"] = f"{BASE}videos/{name}"
        item["url"] = None
        item["path"] = None
        item["exclusion_reason"] = (
            "Narrated promo. Replacing the soundtrack would erase the narration, and mixing in the vocal theme may compete with speech. "
            "Pending a suitable edit. This entry is not a corrected asset and must not be posted as one."
        )
        item["description"] = (
            scene_text(item["description"], EXCLUSION_MARKER)
            + EXCLUSION_MARKER
            + " excluded pending a narration-safe edit. The narrated mix is unchanged. This is not a corrected theme-song asset."
        )

    INDEX_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


def main() -> None:
    if sha256(SONG) != SONG_SHA256:
        raise SystemExit(f"theme A checksum mismatch: {SONG}")
    COVER_DIR.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(render_one, SELECTABLE))
    update_manifest()
    print(f"manifest updated: {INDEX_PATH}")


if __name__ == "__main__":
    main()
