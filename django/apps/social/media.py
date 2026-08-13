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
_MAX_IMAGE_EDGE = 2048
_JPEG_QUALITY = 85
# Video files stream to disk above FILE_UPLOAD_MAX_MEMORY_SIZE; hard cap below.
VIDEO_MAX_BYTES = 32 * 1024 * 1024


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
