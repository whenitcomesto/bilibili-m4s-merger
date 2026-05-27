"""Build bilibili-m4s-merger.exe via PyInstaller, bundling ffmpeg essentials.

Run on Windows:
    pip install pyinstaller PyQt6
    python build.py

Produces:
    dist/bilibili-m4s-merger.exe   (single-file, ~200MB)

Downloads gyan.dev's ffmpeg essentials build into ./vendor/ on first run
(skipped if already present).
"""
from __future__ import annotations

import io
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENDOR = ROOT / "vendor"
DIST = ROOT / "dist"
BUILD = ROOT / "build"
APP_NAME = "bilibili-m4s-merger"

FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"


def ensure_ffmpeg() -> tuple[Path, Path]:
    ffmpeg = VENDOR / "ffmpeg.exe"
    ffprobe = VENDOR / "ffprobe.exe"
    if ffmpeg.exists() and ffprobe.exists():
        print(f"[skip] ffmpeg already in {VENDOR}")
        return ffmpeg, ffprobe

    VENDOR.mkdir(parents=True, exist_ok=True)
    print(f"[download] {FFMPEG_URL}")
    with urllib.request.urlopen(FFMPEG_URL) as resp:
        data = resp.read()
    print(f"[download] got {len(data) / 1024 / 1024:.1f} MB")

    print("[extract] ffmpeg.exe and ffprobe.exe")
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for name in zf.namelist():
            base = Path(name).name
            if base in ("ffmpeg.exe", "ffprobe.exe"):
                with zf.open(name) as src, open(VENDOR / base, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                print(f"  → {base}")

    if not (ffmpeg.exists() and ffprobe.exists()):
        sys.exit("[error] failed to extract ffmpeg.exe / ffprobe.exe from zip")
    return ffmpeg, ffprobe


def run_pyinstaller(ffmpeg: Path, ffprobe: Path) -> None:
    for path in (DIST, BUILD):
        if path.exists():
            shutil.rmtree(path)
    spec_file = ROOT / f"{APP_NAME}.spec"
    if spec_file.exists():
        spec_file.unlink()

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", APP_NAME,
        "--add-binary", f"{ffmpeg};.",
        "--add-binary", f"{ffprobe};.",
        "--noconfirm",
        str(ROOT / "main.py"),
    ]
    print("[build]", " ".join(cmd))
    subprocess.check_call(cmd)
    out = DIST / f"{APP_NAME}.exe"
    if not out.exists():
        sys.exit("[error] expected output not found")
    size_mb = out.stat().st_size / 1024 / 1024
    print(f"[ok] built {out}  ({size_mb:.1f} MB)")


def main() -> None:
    ffmpeg, ffprobe = ensure_ffmpeg()
    run_pyinstaller(ffmpeg, ffprobe)


if __name__ == "__main__":
    main()
