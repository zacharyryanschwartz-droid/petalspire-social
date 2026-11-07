#!/usr/bin/env python3
"""Regression checks for versioned Petalspire social assets.

Checks durations, non-black first frames, 1080x1920, H.264 + real AAC audio,
faststart, public relative asset and cover paths, legacy-file immutability,
and that each selectable soundtrack follows theme A from 0.000 seconds.

Correlation identifies the music mapping. It does not identify singing.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "videos" / "index.json"
HTML_PATH = ROOT / "index.html"
REPORT_PATH = ROOT / "videos" / "v2026-11-07-theme-a-r1" / "media-validation.json"
BASE = "https://zacharyryanschwartz-droid.github.io/petalspire-social/"
VERSION = "v2026-11-07-theme-a-r1"
SONG = ROOT / "audio" / "petalspire-theme-a.mp3"
SONG_SHA256 = "b1a8db25bd6ba3eb01ebe136221d72ea7ba1d8db985dc5c1da599bb8f5805570"
MIN_YAVG = 80.0
MIN_THEME_CORRELATION = 0.90
MAX_LEGACY_CORRELATION = 0.50
MAX_BYTES = 25 * 1024 * 1024

EXPECTED_DURATION = {
    "reel-card-pack-reveal.mp4": 6.0,
    "reel-gameplay-montage-30s.mp4": 30.0,
    "reel-growing.mp4": 6.0,
    "reel-harvest.mp4": 6.0,
    "reel-hook-moonflower-4s.mp4": 4.0,
    "reel-hook-rare-card-4s.mp4": 4.0,
    "reel-market-stall.mp4": 6.0,
    "reel-moonflower-garden.mp4": 6.0,
    "reel-tin-open.mp4": 6.0,
    "reel-trading-friends.mp4": 6.0,
    "reel-hook-promo-4s.mp4": 4.0,
    "reel-promo-30s-framed.mp4": 30.0,
    "reel-promo-30s.mp4": 30.0,
}

# SHA-256 of the files already published at videos/*.mp4. New assets must not replace them.
LEGACY_SHA256 = {
    "reel-card-pack-reveal.mp4": "166719a33aa9ceb712c0df4f367433058956fbf9bb8525de6a1774f49f7e28f5",
    "reel-gameplay-montage-30s.mp4": "b4921e4c744765bf85572e7bdde1edd0ab8aa4fd6f6195e42766406059bf84f4",
    "reel-growing.mp4": "a2accbe8df88173e4aaf84030e5a500241ef12a89e483a105c5e83c41aa53c47",
    "reel-harvest.mp4": "2025a81ccada92542acb457e1537176fdef4295d993733465c41435aa2901c65",
    "reel-hook-moonflower-4s.mp4": "18c8dea2cba818eddceaaaaa3cd7b391e259e698607116358c3aa90f5aba9a2c",
    "reel-hook-promo-4s.mp4": "fe38d1b339d117f54cc1f299ec6c3c8391043599e0f581ca13baa1f503f478e5",
    "reel-hook-rare-card-4s.mp4": "9fe086c3972286f0015ded027530f56dc7c1398bff7b0931c3f8676285d7aaf9",
    "reel-market-stall.mp4": "10739e75efb4a87991b26651eab55e70ed41c749a78761debc19081b0988a876",
    "reel-moonflower-garden.mp4": "987380fe285b4da219809972525f56450a00291fa057e4eafd2716e8c5c5f115",
    "reel-promo-30s-framed.mp4": "fb74c8ad0e74bce57300c4c9d8f166506fcda999ae2ac7b9994dccb091c1d601",
    "reel-promo-30s.mp4": "e722eb56563e39b16fb4f583704baa40981440b0b6ed8a8fabd78977a3346dca",
    "reel-tin-open.mp4": "3a7fa274ac5fd938817a42a9b70f1dcdef15ad1890f971315c81be203227c476",
    "reel-trading-friends.mp4": "452edd02778f5ad537fd1214e84027811cd9aa0200efe9cda5ddbfef2bb02750",
}


class Failure(Exception):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise Failure(message)


def sha256(path: Path) -> str:
    return subprocess.check_output(["sha256sum", str(path)], text=True).split()[0]


def ffprobe(path: Path) -> dict:
    raw = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,size:stream=index,codec_type,codec_name,profile,width,height,avg_frame_rate,sample_rate,channels,pix_fmt,nb_frames,duration,bit_rate",
            "-of",
            "json",
            str(path),
        ],
        text=True,
    )
    return json.loads(raw)


def yavg_at(path: Path, seconds: float) -> float:
    cmd = [
        "ffmpeg",
        "-v",
        "info",
        "-ss",
        str(seconds),
        "-i",
        str(path),
        "-frames:v",
        "1",
        "-vf",
        "signalstats,metadata=print",
        "-f",
        "null",
        "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    values = []
    for line in proc.stderr.splitlines():
        if "lavfi.signalstats.YAVG=" in line:
            values.append(float(line.rsplit("=", 1)[-1]))
    check(bool(values), f"no YAVG at {seconds}s for {path}")
    return values[0]


def yavg(path: Path, first_video_frame: bool = False) -> float:
    cmd = ["ffmpeg", "-v", "info", "-i", str(path)]
    if first_video_frame:
        cmd += ["-frames:v", "1"]
    cmd += ["-vf", "signalstats,metadata=print", "-f", "null", "-"]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    values = []
    for line in proc.stderr.splitlines():
        if "lavfi.signalstats.YAVG=" in line:
            values.append(float(line.rsplit("=", 1)[-1]))
    check(bool(values), f"no YAVG for {path}")
    return values[0]


def moov_before_mdat(path: Path) -> bool:
    order = []
    size = path.stat().st_size
    pos = 0
    with path.open("rb") as handle:
        while pos + 8 <= size and len(order) < 8:
            handle.seek(pos)
            header = handle.read(8)
            if len(header) < 8:
                break
            atom_size = int.from_bytes(header[:4], "big")
            atom_type = header[4:8]
            header_len = 8
            if atom_size == 1:
                atom_size = int.from_bytes(handle.read(8), "big")
                header_len = 16
            if atom_size < header_len:
                break
            order.append(atom_type)
            pos += atom_size
    check(b"moov" in order and b"mdat" in order, f"missing moov/mdat in {path}")
    return order.index(b"moov") < order.index(b"mdat")


def decode_mono(path: Path, af: str | None = None) -> np.ndarray:
    cmd = ["ffmpeg", "-v", "error", "-i", str(path)]
    if af:
        cmd += ["-af", af]
    cmd += ["-ac", "1", "-ar", "16000", "-f", "f32le", "-"]
    raw = subprocess.check_output(cmd)
    count = len(raw) // 4
    if count == 0:
        return np.zeros(0, dtype=np.float32)
    return np.frombuffer(raw[: count * 4], dtype="<f4")


def best_correlation(left: np.ndarray, right: np.ndarray, max_lag_16k: int = 4000) -> tuple[float, int]:
    """Best Pearson correlation within max_lag_16k samples at 16 kHz (default 0.25 s)."""
    if left.size < 1000 or right.size < 1000:
        return 0.0, 0
    left = left[::4].astype(np.float64)
    right = right[::4].astype(np.float64)
    max_lag = max(1, max_lag_16k // 4)
    best = -1.0
    best_lag = 0
    for lag in range(-max_lag, max_lag + 1, 2):
        if lag >= 0:
            aa = left[lag:]
            bb = right[: aa.size]
        else:
            bb = right[-lag:]
            aa = left[: bb.size]
        n = min(aa.size, bb.size)
        if n < 1000:
            continue
        aa = aa[:n]
        bb = bb[:n]
        aa = aa - aa.mean()
        bb = bb - bb.mean()
        denom = math.sqrt(float(aa.dot(aa) * bb.dot(bb)))
        if denom <= 0:
            continue
        value = float(aa.dot(bb) / denom)
        if value > best:
            best = value
            best_lag = lag * 4
    return best, best_lag


def decode_aac_stats(path: Path) -> dict:
    raw = subprocess.check_output(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-vn",
            "-ac",
            "2",
            "-ar",
            "48000",
            "-f",
            "s16le",
            "-",
        ]
    )
    sample_count = len(raw) // 2
    check(sample_count > 0, f"AAC decode produced no samples: {path}")
    pcm = np.frombuffer(raw[: sample_count * 2], dtype="<i2").astype(np.float64)
    rms = math.sqrt(float(np.mean(pcm * pcm)))
    duration = sample_count / 2 / 48000
    return {"decoded_seconds": duration, "rms_s16": rms, "interleaved_samples": sample_count}


def relative_public_path(value: str, kind: str) -> None:
    check(isinstance(value, str) and value, f"{kind} path missing")
    check(not value.startswith("/"), f"{kind} path is absolute: {value}")
    check("://" not in value, f"{kind} path is a URL: {value}")
    check("\\" not in value and ".." not in value.split("/"), f"{kind} path is not public-relative: {value}")
    check(value.startswith(f"videos/{VERSION}/"), f"{kind} path is not versioned: {value}")
    check((ROOT / value).is_file(), f"{kind} file missing: {value}")


def validate_selectable(item: dict, report: dict) -> None:
    name = item["file"]
    duration = EXPECTED_DURATION[name]
    path = item["path"]
    cover_path = item["cover_path"]
    relative_public_path(path, name)
    relative_public_path(cover_path, f"{name} cover")
    check(item["url"] == BASE + path, f"{name} url is not the public path")
    check(item["cover_url"] == BASE + cover_path, f"{name} cover_url is not the public path")
    check(item["future_posting"] == "use", f"{name} is not selectable")
    check("promo" not in name, f"{name} is a promo and cannot be selectable")
    check(item["legacy_path"] == f"videos/{name}", f"{name} legacy_path changed")
    check(item["legacy_url"] == BASE + f"videos/{name}", f"{name} legacy_url changed")
    check(item["thumbnail_offset_ms"] == 0, f"{name} thumbnail offset is not 0")
    audio = item["audio"]
    check(audio["source_file"] == "audio/petalspire-theme-a.mp3", f"{name} audio source path")
    check(audio["source_sha256"] == SONG_SHA256, f"{name} audio source checksum metadata")
    check(audio["song_start_s"] == 0.0, f"{name} song start is not 0")
    check(audio["vocal_excerpt_reviewed"] is False, f"{name} falsely marks the vocal excerpt reviewed")
    check(audio["sample_rate_hz"] == 48000 and audio["channels"] == 2, f"{name} audio metadata")
    check("lyrical excerpt not reviewed" in item["description"], f"{name} description claims a reviewed excerpt")

    media_path = ROOT / path
    cover = ROOT / cover_path
    check(media_path.stat().st_size == item["size_bytes"], f"{name} size_bytes mismatch")
    check(media_path.stat().st_size < MAX_BYTES, f"{name} is over 25 MB")
    check(cover.read_bytes().startswith(b"\xff\xd8"), f"{name} cover is not a JPEG")

    probed = ffprobe(media_path)
    streams = probed["streams"]
    video = next(stream for stream in streams if stream["codec_type"] == "video")
    audio_stream = next(stream for stream in streams if stream["codec_type"] == "audio")
    format_duration = float(probed["format"]["duration"])
    check(abs(format_duration - duration) <= 0.08, f"{name} duration {format_duration} != {duration}")
    check(video["codec_name"] == "h264", f"{name} video codec {video['codec_name']}")
    check(video["width"] == 1080 and video["height"] == 1920, f"{name} dimensions")
    check(video["pix_fmt"] == "yuv420p", f"{name} pix_fmt")
    check(video["avg_frame_rate"] == "30/1", f"{name} fps {video['avg_frame_rate']}")
    frames = int(video.get("nb_frames") or 0)
    check(abs(frames - round(duration * 30)) <= 2, f"{name} frame count {frames}")
    check(audio_stream["codec_name"] == "aac", f"{name} audio codec tag is {audio_stream['codec_name']}")
    check(audio_stream["profile"] == "LC", f"{name} AAC profile {audio_stream.get('profile')}")
    check(audio_stream["sample_rate"] == "48000", f"{name} sample rate")
    check(audio_stream["channels"] == 2, f"{name} channels")
    check(moov_before_mdat(media_path), f"{name} moov atom is not before mdat")

    decoded = decode_aac_stats(media_path)
    check(decoded["rms_s16"] > 200, f"{name} decoded AAC is silent ({decoded['rms_s16']})")
    check(abs(decoded["decoded_seconds"] - duration) <= 0.15, f"{name} decoded AAC duration {decoded}")

    first = yavg(media_path, first_video_frame=True)
    cover_y = yavg(cover)
    opening = {stamp: yavg_at(media_path, stamp) for stamp in (0.25, 0.51)}
    check(first >= MIN_YAVG, f"{name} first frame is dark ({first})")
    check(cover_y >= MIN_YAVG, f"{name} cover is dark ({cover_y})")
    for stamp, value in opening.items():
        check(value >= MIN_YAVG, f"{name} frame at {stamp}s is dark ({value})")
    cover_probe = ffprobe(cover)
    cover_video = cover_probe["streams"][0]
    check(cover_video["width"] == 1080 and cover_video["height"] == 1920, f"{name} cover dimensions")

    fade_start = duration - 0.35
    theme_af = f"loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=out:st={fade_start}:d=0.35,atrim=duration={duration}"
    theme_pcm = decode_mono(SONG, theme_af)
    clip_pcm = decode_mono(media_path)
    theme_corr, theme_lag = best_correlation(clip_pcm, theme_pcm)
    legacy_pcm = decode_mono(ROOT / "videos" / name)
    legacy_corr, legacy_lag = best_correlation(clip_pcm, legacy_pcm)
    check(theme_corr >= MIN_THEME_CORRELATION, f"{name} audio does not match theme A ({theme_corr:.4f})")
    check(legacy_corr <= MAX_LEGACY_CORRELATION, f"{name} audio still matches the legacy track ({legacy_corr:.4f})")
    check(theme_corr > legacy_corr + 0.4, f"{name} theme mapping is not clearly above the legacy track")

    report[name] = {
        "path": path,
        "cover_path": cover_path,
        "duration_s": format_duration,
        "expected_duration_s": duration,
        "size_bytes": media_path.stat().st_size,
        "width": video["width"],
        "height": video["height"],
        "video_codec": video["codec_name"],
        "pix_fmt": video["pix_fmt"],
        "fps": video["avg_frame_rate"],
        "frames": frames,
        "audio_codec": audio_stream["codec_name"],
        "audio_profile": audio_stream["profile"],
        "sample_rate": int(audio_stream["sample_rate"]),
        "channels": audio_stream["channels"],
        "decoded_audio_seconds": round(decoded["decoded_seconds"], 4),
        "decoded_audio_rms_s16": round(decoded["rms_s16"], 2),
        "faststart": True,
        "first_frame_yavg": round(first, 3),
        "opening_yavg": {str(stamp): round(value, 3) for stamp, value in opening.items()},
        "cover_yavg": round(cover_y, 3),
        "theme_a_correlation": round(theme_corr, 4),
        "theme_a_lag_samples_16k": theme_lag,
        "legacy_audio_correlation": round(legacy_corr, 4),
        "legacy_audio_lag_samples_16k": legacy_lag,
        "song_start_s": 0.0,
        "source_sha256": SONG_SHA256,
        "vocal_excerpt_reviewed": False,
        "visual_video_reviewed": False,
        "visual_review_scope": (
            "A local preparation copy of this filename was reviewed for picture only. This hosted file was not that review, and audio was not heard."
            if name == "reel-tin-open.mp4"
            else "Not visually reviewed."
        ),
    }


def validate_excluded(item: dict) -> None:
    name = item["file"]
    check(item["future_posting"] == "excluded", f"{name} should be excluded")
    check(item.get("url") is None, f"{name} still has a selectable url")
    check(item.get("path") is None, f"{name} still has a selectable path")
    check(item.get("audio_replaced") is False, f"{name} claims audio was replaced")
    check(item.get("vocal_excerpt_reviewed") is False, f"{name} claims a reviewed vocal edit")
    check("not a corrected" in item["description"], f"{name} description calls the promo fixed")
    check("narration" in item["exclusion_reason"].lower(), f"{name} exclusion reason missing")
    check(item["legacy_path"] == f"videos/{name}", f"{name} legacy path")
    check(item["legacy_url"] == BASE + item["legacy_path"], f"{name} legacy url")
    versioned = ROOT / "videos" / VERSION / name
    check(not versioned.exists(), f"excluded promo was rendered into the version directory: {name}")


def main() -> int:
    failures: list[str] = []
    report: dict = {
        "asset_version": VERSION,
        "vocal_excerpt_reviewed": False,
        "transcription_tool": None,
        "audio_mapping_method": (
            "Decoded AAC compared with theme A after the same loudnorm, fade, and duration trim. "
            "Best Pearson correlation within 0.2 seconds of lag. This checks source mapping, not lyrics or singing."
        ),
        "clips": {},
    }
    try:
        check(sha256(SONG) == SONG_SHA256, "theme A file checksum mismatch")
        manifest = json.loads(INDEX_PATH.read_text())
        check(manifest["song"]["sha256"] == SONG_SHA256, "manifest song checksum")
        check(manifest["song"]["file"] == "audio/petalspire-theme-a.mp3", "manifest song path")
        check(manifest["song"]["vocal_excerpt_reviewed"] is False, "manifest claims the excerpt was reviewed")
        check(manifest["asset_version"] == VERSION, "asset version")
        by_file = {item["file"]: item for item in manifest["videos"]}
        check(set(by_file) == set(EXPECTED_DURATION), f"manifest file set {sorted(by_file)} != expected")
        html = HTML_PATH.read_text()
        for name, digest in LEGACY_SHA256.items():
            legacy = ROOT / "videos" / name
            check(legacy.is_file(), f"legacy file missing: {name}")
            check(sha256(legacy) == digest, f"legacy file changed: {name}")
        selectable = [item for item in manifest["videos"] if item["future_posting"] == "use"]
        excluded = [item for item in manifest["videos"] if item["future_posting"] == "excluded"]
        check(
            sorted(item["file"] for item in selectable) == sorted(name for name in EXPECTED_DURATION if "promo" not in name),
            "selectable set",
        )
        check(
            sorted(item["file"] for item in excluded) == sorted(name for name in EXPECTED_DURATION if "promo" in name),
            "excluded set",
        )
        for item in selectable:
            validate_selectable(item, report["clips"])
            check(item["path"] in html, f"index.html missing {item['path']}")
            check(item["cover_path"] in html, f"index.html missing {item['cover_path']}")
            check(f'href="videos/{item["file"]}"' not in html, f"index.html still posts legacy {item['file']} as a primary link")
        for item in excluded:
            validate_excluded(item)
            check(f"videos/{VERSION}/{item['file']}" not in html, f"index.html links excluded {item['file']}")
        check("future_posting" in manifest["selection_rule"], "selection rule missing")
        check(all(item["vocal_excerpt_reviewed"] is False for item in report["clips"].values()), "report marked vocals reviewed")
    except Failure as exc:
        failures.append(str(exc))
    except Exception as exc:  # noqa: BLE001 — surface probe/decode problems as test failures
        failures.append(f"{type(exc).__name__}: {exc}")

    report["passed"] = not failures
    report["failures"] = failures
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n")
    if failures:
        print("FAILED")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"PASSED {len(report['clips'])} selectable clips")
    for name, clip in report["clips"].items():
        print(
            f"{name} dur={clip['duration_s']:.3f} yavg={clip['first_frame_yavg']} "
            f"aac_rms={clip['decoded_audio_rms_s16']} theme_r={clip['theme_a_correlation']} "
            f"legacy_r={clip['legacy_audio_correlation']}"
        )
    print(f"report {REPORT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
