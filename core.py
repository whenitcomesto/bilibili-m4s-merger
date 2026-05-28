"""Core logic: scan a folder for B站 m4s files, group them by title, probe stream type, mux to MP4."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

GROUP_PATTERN = re.compile(r"^(.*)_(\d+)$")

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


@dataclass
class Stream:
    path: Path
    size: int
    codec_type: str = ""
    codec_name: str = ""
    bitrate: int = 0
    width: int = 0
    height: int = 0
    duration: float = 0.0
    probe_error: str = ""

    @property
    def is_video(self) -> bool:
        return self.codec_type == "video"

    @property
    def is_audio(self) -> bool:
        return self.codec_type == "audio"

    @property
    def resolution(self) -> str:
        if self.width and self.height:
            return f"{self.width}x{self.height}"
        return "-"

    @property
    def bitrate_kbps(self) -> str:
        if self.bitrate > 0:
            return f"{self.bitrate // 1000} kbps"
        return "-"

    @property
    def size_mb(self) -> str:
        return f"{self.size / (1024 * 1024):.1f} MB"


@dataclass
class VideoGroup:
    title: str
    streams: list[Stream] = field(default_factory=list)

    @property
    def video_streams(self) -> list[Stream]:
        return [s for s in self.streams if s.is_video]

    @property
    def audio_streams(self) -> list[Stream]:
        return [s for s in self.streams if s.is_audio]

    @property
    def unknown_streams(self) -> list[Stream]:
        return [s for s in self.streams if not s.is_video and not s.is_audio]

    @property
    def is_complete(self) -> bool:
        return bool(self.video_streams) and bool(self.audio_streams)

    def default_video(self) -> Stream | None:
        if not self.video_streams:
            return None
        return max(self.video_streams, key=lambda s: s.size)

    def default_audio(self) -> Stream | None:
        if not self.audio_streams:
            return None
        return max(self.audio_streams, key=lambda s: s.size)


def _bundled(name: str) -> str | None:
    """If running as a PyInstaller --onefile bundle, look inside the extracted
    temp dir (sys._MEIPASS) for a bundled binary."""
    base = getattr(sys, "_MEIPASS", None)
    if not base:
        return None
    exe_name = f"{name}.exe" if sys.platform == "win32" else name
    candidate = Path(base) / exe_name
    return str(candidate) if candidate.is_file() else None


def find_ffmpeg() -> str | None:
    return _bundled("ffmpeg") or shutil.which("ffmpeg")


def find_ffprobe() -> str | None:
    return _bundled("ffprobe") or shutil.which("ffprobe")


def probe_stream(ffprobe: str, path: Path) -> Stream:
    stream = Stream(path=path, size=path.stat().st_size)
    cmd = [
        ffprobe,
        "-v", "error",
        "-show_streams",
        "-show_format",
        "-of", "json",
        str(path),
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=CREATE_NO_WINDOW,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        stream.probe_error = f"ffprobe failed: {exc}"
        return stream

    if result.returncode != 0:
        stream.probe_error = result.stderr.strip() or "ffprobe non-zero exit"
        return stream

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        stream.probe_error = f"json decode: {exc}"
        return stream

    streams = data.get("streams") or []
    if not streams:
        stream.probe_error = "no streams in file"
        return stream

    # Take the first stream — m4s files from B站 contain one elementary stream.
    s = streams[0]
    stream.codec_type = s.get("codec_type", "")
    stream.codec_name = s.get("codec_name", "")
    stream.width = int(s.get("width") or 0)
    stream.height = int(s.get("height") or 0)

    fmt = data.get("format") or {}
    try:
        stream.duration = float(fmt.get("duration") or 0.0)
    except (TypeError, ValueError):
        stream.duration = 0.0
    try:
        stream.bitrate = int(s.get("bit_rate") or fmt.get("bit_rate") or 0)
    except (TypeError, ValueError):
        stream.bitrate = 0

    return stream


def scan_folder(folder: Path, ffprobe: str) -> tuple[list[VideoGroup], list[Stream]]:
    """Scan folder for .m4s files, probe each, group by filename prefix.

    Two-pass algorithm:
      1. Files matching `(.+)_(\\d+)\\.m4s` define group titles and join them.
      2. Files without a `_<num>` suffix are added to a group if their stem
         matches a known title from pass 1; otherwise they go to unmatched.

    This handles the common IDM pattern where the first downloaded copy keeps
    the original name (`title.m4s`) and duplicates get `_2`, `_3`, ... suffixes.

    Returns (groups, unmatched).
    """
    files = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".m4s")
    streams: list[tuple[Path, Stream]] = [(p, probe_stream(ffprobe, p)) for p in files]

    groups: dict[str, VideoGroup] = {}

    # Pass 1: files with _N suffix establish group titles
    leftovers: list[Stream] = []
    for path, stream in streams:
        match = GROUP_PATTERN.match(path.stem)
        if match:
            title = match.group(1)
            groups.setdefault(title, VideoGroup(title=title)).streams.append(stream)
        else:
            leftovers.append(stream)

    # Pass 2: files without _N suffix — join existing group if stem matches its title
    unmatched: list[Stream] = []
    for stream in leftovers:
        title = stream.path.stem
        if title in groups:
            groups[title].streams.append(stream)
        else:
            unmatched.append(stream)

    return list(groups.values()), unmatched


def build_mux_command(
    ffmpeg: str,
    video: Path,
    audio: Path,
    output: Path,
    overwrite: bool = False,
) -> list[str]:
    return [
        ffmpeg,
        "-y" if overwrite else "-n",
        "-i", str(video),
        "-i", str(audio),
        "-c", "copy",
        "-movflags", "+faststart",
        str(output),
    ]


def mux(
    ffmpeg: str,
    video: Path,
    audio: Path,
    output: Path,
    overwrite: bool = False,
) -> tuple[bool, str]:
    """Run ffmpeg to mux a video + audio m4s pair into an MP4. Returns (success, message)."""
    cmd = build_mux_command(ffmpeg, video, audio, output, overwrite=overwrite)
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=CREATE_NO_WINDOW,
        )
    except OSError as exc:
        return False, f"ffmpeg failed to start: {exc}"

    if result.returncode == 0:
        return True, f"OK -> {output}"
    return False, (result.stderr.strip() or f"ffmpeg exit {result.returncode}")


def sanitize_filename(name: str) -> str:
    # Windows reserved characters: < > : " / \ | ? *
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip()
    return cleaned or "output"
