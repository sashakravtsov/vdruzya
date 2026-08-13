"""Media helpers — process + save images/videos. One place for all uploads."""
from __future__ import annotations

import logging
import subprocess
import tempfile
import uuid
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

log = logging.getLogger(__name__)

_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
_VIDEO_EXT = {".mp4", ".webm", ".mov", ".m4v"}
_AUDIO_EXT = {".webm", ".ogg", ".oga", ".opus", ".mp3", ".m4a", ".aac", ".wav"}
_MAX_IMAGE_EDGE = 2048
_JPEG_QUALITY = 85
# Video files stream to disk above FILE_UPLOAD_MAX_MEMORY_SIZE; hard cap below.
VIDEO_MAX_BYTES = 32 * 1024 * 1024
AUDIO_MAX_BYTES = 8 * 1024 * 1024


def media_url(path: str | None) -> str | None:
    if not path:
        return None
    p = str(path).strip()
    if p.startswith(("http://", "https://")):
        return p
    if p.startswith("storage:"):
        p = p[len("storage:") :]
    if p.startswith("/storage/"):
        p = p[len("/storage/") :]
    elif p.startswith("/"):
        return p
    try:
        url = default_storage.url(p)
        if url.startswith("http"):
            return url
        base = (getattr(settings, "MEDIA_URL", "/storage/") or "/storage/").rstrip("/")
        return f"{base}/{p.lstrip('/')}"
    except Exception:
        base = (
            getattr(settings, "AWS_URL", None)
            or getattr(settings, "MEDIA_URL", "/storage/")
            or "/storage/"
        ).rstrip("/")
        return f"{base}/{p.lstrip('/')}"


def _read_upload(upload) -> bytes:
    upload.seek(0)
    data = upload.read()
    try:
        upload.seek(0)
    except Exception:
        pass
    return data


def process_image_bytes(data: bytes, *, filename: str = "") -> tuple[bytes, str]:
    """EXIF-orient, downscale, re-encode. Returns (bytes, ext including dot)."""
    from PIL import Image, ImageOps

    ext = Path(filename or "").suffix.lower()
    if ext not in _IMAGE_EXT:
        ext = ".jpg"
    try:
        im = Image.open(BytesIO(data))
        im = ImageOps.exif_transpose(im)
    except Exception:
        return data, (ext if ext in _IMAGE_EXT else ".jpg")

    if max(im.size) > _MAX_IMAGE_EDGE:
        im.thumbnail((_MAX_IMAGE_EDGE, _MAX_IMAGE_EDGE), Image.Resampling.LANCZOS)

    buf = BytesIO()
    fmt = (im.format or "").upper()
    if fmt == "GIF" or ext == ".gif":
        # Keep GIF as-is when possible (animation).
        return data, ".gif"
    if fmt == "PNG" or ext == ".png":
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGBA")
        im.save(buf, format="PNG", optimize=True)
        return buf.getvalue(), ".png"
    if im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    elif im.mode == "L":
        im = im.convert("RGB")
    im.save(buf, format="JPEG", quality=_JPEG_QUALITY, optimize=True)
    return buf.getvalue(), ".jpg"


def save_image(upload, folder: str) -> str:
    """Process then store under folder/. Returns storage path."""
    raw = _read_upload(upload)
    max_bytes = getattr(settings, "FILE_UPLOAD_MAX_MEMORY_SIZE", 3 * 1024 * 1024)
    if len(raw) > max_bytes * 4:
        # Allow slightly larger disk uploads after client selected big photos.
        pass
    if len(raw) > 12 * 1024 * 1024:
        raise ValueError("Файл слишком большой")
    data, ext = process_image_bytes(raw, filename=getattr(upload, "name", "") or "")
    name = f"{folder}/{uuid.uuid4().hex}{ext}"
    return default_storage.save(name, ContentFile(data))


def try_save_image(upload, folder: str) -> str | None:
    """Optional upload — None if missing or processing fails."""
    if not upload:
        return None
    try:
        return save_image(upload, folder)
    except Exception:
        return None


def save_video(upload, folder: str = "videos") -> tuple[str, str | None]:
    """Store video on the same media disk as photos; optional poster frame via ffmpeg.
    Returns (video_path, poster_path|None). Not a separate video CDN — same S3/local storage.
    """
    name = getattr(upload, "name", "") or "video.mp4"
    ext = Path(name).suffix.lower()
    if ext not in _VIDEO_EXT:
        ext = ".mp4"
    size = getattr(upload, "size", None) or 0
    if size and size > VIDEO_MAX_BYTES:
        raise ValueError(f"Видео больше {VIDEO_MAX_BYTES // (1024 * 1024)} МБ")

    raw = _read_upload(upload)
    if len(raw) > VIDEO_MAX_BYTES:
        raise ValueError(f"Видео больше {VIDEO_MAX_BYTES // (1024 * 1024)} МБ")

    vid_name = f"{folder}/{uuid.uuid4().hex}{ext}"
    video_path = default_storage.save(vid_name, ContentFile(raw))
    poster_path = None
    try:
        poster_path = _poster_from_bytes(raw, folder=folder)
    except Exception as exc:
        # Fake/corrupt uploads (smoke probes) often fail decode — not fatal.
        log.warning("video poster skipped for %s: %s", video_path, exc)
    return video_path, poster_path


WAVEFORM_BARS = 40
VOICE_MIN_MS = 200
VOICE_MAX_MS = 5 * 60 * 1000  # hard stop in recorder UI + server parse


def format_duration_ms(ms) -> str:
    try:
        ms = int(ms or 0)
    except (TypeError, ValueError):
        ms = 0
    if ms <= 0:
        return "0:00"
    sec = max(0, ms // 1000)
    return f"{sec // 60}:{sec % 60:02d}"


def voice_body(duration_ms=None) -> str:
    label = format_duration_ms(duration_ms)
    return f"[голосовое {label}]" if label != "0:00" else "[голосовое]"


def is_voice_body(text: str) -> bool:
    b = (text or "").strip()
    return b == "[голосовое]" or b.startswith("[голосовое ")


def scale_peaks(values: list[float], *, floor: int = 4) -> list[int]:
    peak = max(values) if values else 0.0
    if peak <= 0:
        return [floor] * len(values)
    return [max(floor, min(100, int(round((v / peak) * 100)))) for v in values]


def peaks_from_floats(samples, *, bars: int = WAVEFORM_BARS) -> list[int]:
    """Max-abs buckets → 4..100 (same shape as browser MediaRecorder path)."""
    n = len(samples)
    if n < 8:
        return []
    bucket = max(1, n // bars)
    out: list[float] = []
    for i in range(bars):
        start = i * bucket
        end = min(n, start + bucket)
        peak = 0.0
        for j in range(start, end):
            v = abs(float(samples[j]))
            if v > peak:
                peak = v
        out.append(peak)
    return scale_peaks(out)


def parse_waveform_peaks(raw, *, bars: int = WAVEFORM_BARS) -> list[int] | None:
    """Validate client/server peak CSV → list of 1..100 ints (fixed bar count)."""
    if not raw:
        return None
    parts = [p.strip() for p in str(raw).replace(";", ",").split(",") if p.strip()]
    if len(parts) < 8:
        return None
    vals: list[int] = []
    for p in parts[:96]:
        try:
            n = int(float(p))
        except (TypeError, ValueError):
            continue
        vals.append(max(1, min(100, n)))
    if len(vals) < 8:
        return None
    if len(vals) == bars:
        return vals
    out = []
    for i in range(bars):
        idx = int(i * (len(vals) - 1) / max(1, bars - 1))
        out.append(vals[idx])
    return out


def serialize_waveform_peaks(peaks: list[int] | None) -> str | None:
    clean = parse_waveform_peaks(",".join(str(int(x)) for x in (peaks or [])), bars=WAVEFORM_BARS)
    if not clean:
        return None
    return ",".join(str(x) for x in clean)


def parse_duration_ms(raw) -> int | None:
    try:
        ms = int(raw)
    except (TypeError, ValueError):
        return None
    if ms < VOICE_MIN_MS or ms > VOICE_MAX_MS:
        return None
    return ms


def waveform_from_bytes(raw: bytes, *, bars: int = WAVEFORM_BARS) -> tuple[str | None, int | None]:
    """ffmpeg decode → max-abs peaks + duration_ms (fallback when client peaks missing)."""
    if not raw or len(raw) < 64:
        return None, None
    ffmpeg = getattr(settings, "FFMPEG_BIN", "ffmpeg")
    try:
        import array
        with tempfile.TemporaryDirectory(prefix="vdvoice_") as tmp:
            src = Path(tmp) / "in.bin"
            src.write_bytes(raw)
            cmd = [
                ffmpeg, "-y", "-loglevel", "error",
                "-i", str(src),
                "-ac", "1", "-ar", "8000", "-f", "f32le",
                "pipe:1",
            ]
            proc = subprocess.run(cmd, check=True, timeout=45, capture_output=True)
        pcm = proc.stdout or b""
        if len(pcm) < 16:
            return None, None
        samples = array.array("f")
        samples.frombytes(pcm[: len(pcm) - (len(pcm) % 4)])
        duration_ms = int(len(samples) * 1000 / 8000)
        peaks = peaks_from_floats(samples, bars=bars)
        return (
            serialize_waveform_peaks(peaks),
            duration_ms if duration_ms >= VOICE_MIN_MS else None,
        )
    except Exception as exc:
        log.warning("voice waveform skipped: %s", exc)
        return None, None


def save_audio(upload, folder: str = "messages") -> tuple[str, bytes]:
    """Store classic Inbox voice note; return (path, raw bytes for waveform analysis)."""
    name = getattr(upload, "name", "") or "voice.webm"
    ext = Path(name).suffix.lower()
    ctype = (getattr(upload, "content_type", "") or "").lower()
    if ext not in _AUDIO_EXT:
        if "ogg" in ctype:
            ext = ".ogg"
        elif "mpeg" in ctype or "mp3" in ctype:
            ext = ".mp3"
        elif "mp4" in ctype or "m4a" in ctype or "aac" in ctype:
            ext = ".m4a"
        elif "wav" in ctype:
            ext = ".wav"
        else:
            ext = ".webm"
    size = getattr(upload, "size", None) or 0
    if size and size > AUDIO_MAX_BYTES:
        raise ValueError(f"Голосовое больше {AUDIO_MAX_BYTES // (1024 * 1024)} МБ")
    raw = _read_upload(upload)
    if len(raw) > AUDIO_MAX_BYTES:
        raise ValueError(f"Голосовое больше {AUDIO_MAX_BYTES // (1024 * 1024)} МБ")
    if len(raw) < 32:
        raise ValueError("Пустая запись")
    path = f"{folder}/{uuid.uuid4().hex}{ext}"
    return default_storage.save(path, ContentFile(raw)), raw


def _poster_from_bytes(raw: bytes, *, folder: str) -> str | None:
    ffmpeg = getattr(settings, "FFMPEG_BIN", "ffmpeg")
    with tempfile.TemporaryDirectory(prefix="vdvid_") as tmp:
        src = Path(tmp) / "in.bin"
        out = Path(tmp) / "poster.jpg"
        src.write_bytes(raw)
        cmd = [
            ffmpeg, "-y", "-loglevel", "error",
            "-ss", "00:00:01", "-i", str(src),
            "-frames:v", "1", "-q:v", "3", str(out),
        ]
        try:
            subprocess.run(cmd, check=True, timeout=60, capture_output=True)
        except FileNotFoundError:
            # retry without seek if file shorter than 1s
            return None
        except subprocess.CalledProcessError:
            cmd2 = [
                ffmpeg, "-y", "-loglevel", "error",
                "-i", str(src), "-frames:v", "1", "-q:v", "3", str(out),
            ]
            subprocess.run(cmd2, check=True, timeout=60, capture_output=True)
        if not out.exists() or out.stat().st_size < 32:
            return None
        data, ext = process_image_bytes(out.read_bytes(), filename="poster.jpg")
        return default_storage.save(f"{folder}/{uuid.uuid4().hex}{ext}", ContentFile(data))
