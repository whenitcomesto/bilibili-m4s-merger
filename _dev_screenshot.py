"""Generate a screenshot of the GUI with mock data for design review.
Not part of the shipped product — only for development."""
from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QApplication, QScrollArea

from main import GroupWidget, MainWindow, load_stylesheet
from core import Stream, VideoGroup


def mk(name: str, size_mb: float, kind: str, codec: str = "",
       w: int = 0, h: int = 0, br: int = 0) -> Stream:
    s = Stream(path=Path(f"D:/downloads/{name}"), size=int(size_mb * 1024 * 1024))
    s.codec_type = kind
    s.codec_name = codec
    s.width = w
    s.height = h
    s.bitrate = br
    return s


def main() -> int:
    app = QApplication(sys.argv)
    qss = load_stylesheet()
    if qss:
        app.setStyleSheet(qss)

    window = MainWindow()
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    window.resize(1080, 1380)
    window.show()

    window.input_folder = Path("D:/downloads/bilibili")
    window.input_label.setText("D:\\downloads\\bilibili")
    window.output_folder = Path("D:/videos")
    window.output_label.setText("D:\\videos")

    window.video_groups = [
        VideoGroup(title="该被世界记得._哔哩哔哩_bilibili", streams=[
            mk("该被世界记得._哔哩哔哩_bilibili.m4s", 12.8, "video", "h264", 640, 360, 800000),
            mk("该被世界记得._哔哩哔哩_bilibili_2.m4s", 69.6, "video", "h264", 1920, 1080, 4500000),
            mk("该被世界记得._哔哩哔哩_bilibili_3.m4s", 124.6, "audio", "aac", br=320000),
        ]),
        VideoGroup(title="下_哔哩哔哩_bilibili", streams=[
            mk("下_哔哩哔哩_bilibili.m4s", 12.6, "video", "h264", 640, 360, 800000),
            mk("下_哔哩哔哩_bilibili_2.m4s", 107.7, "video", "h264", 1920, 1080, 6234000),
            mk("下_哔哩哔哩_bilibili_3.m4s", 204.5, "audio", "aac", br=320000),
        ]),
    ]
    window.unmatched_streams = [
        mk("random_clip.m4s", 87.3, "video", "h264", 1280, 720, 2400000),
        mk("test_audio.m4s", 24.1, "audio", "aac", br=192000),
        mk("untitled_segment.m4s", 156.8, "video", "h264", 1920, 1080, 3800000),
    ]

    window.refresh_display()
    window.log.append("✓ ffmpeg / ffprobe 已就绪（内置）")
    window.log.append("扫描 D:\\downloads\\bilibili")
    window.log.append("分组完成：2 组、9 个 m4s 流；其中 3 个文件待手动归组。")

    def capture() -> None:
        # Expand scroll area so all cards are visible (no scrollbar)
        scroll = window.findChild(QScrollArea)
        if scroll is not None:
            inner_h = window.groups_container.sizeHint().height()
            scroll.setMinimumHeight(inner_h + 8)
        QApplication.processEvents()
        QTimer.singleShot(200, do_grab)

    def do_grab() -> None:
        pixmap = window.grab()
        out = Path(__file__).resolve().parent / "_screenshot.png"
        pixmap.save(str(out))
        print(f"Saved: {out}  ({pixmap.width()}x{pixmap.height()})")
        app.quit()

    QTimer.singleShot(800, capture)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
