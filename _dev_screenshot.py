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

    groups = [
        VideoGroup(title="漫长的季节 EP01 凶手不止一个", streams=[
            mk("漫长的季节EP01_1.m4s", 856.4, "video", "h264", 1920, 1080, 6234000),
            mk("漫长的季节EP01_2.m4s", 45.2, "audio", "aac", br=320000),
        ]),
        VideoGroup(title="三体动画版 第8集 古筝行动", streams=[
            mk("三体动画版_1.m4s", 287.1, "video", "h264", 1280, 720, 2100000),
            mk("三体动画版_3.m4s", 587.6, "video", "h264", 1920, 1080, 4500000),
            mk("三体动画版_2.m4s", 38.5, "audio", "aac", br=192000),
        ]),
        VideoGroup(title="纪录片片段A（缺少音频）", streams=[
            mk("纪录片片段A_1.m4s", 124.3, "video", "h264", 1280, 720, 1800000),
        ]),
    ]

    insert_at = window.groups_layout.count() - 1
    for i, g in enumerate(groups):
        widget = GroupWidget(g, i)
        window.groups_layout.insertWidget(insert_at, widget)
        insert_at += 1
        window.group_widgets.append(widget)

    window.status_label.setText("识别到 3 个视频，其中 2 个就绪可混流")
    window.log.append("✓ ffmpeg / ffprobe 已就绪（内置）")
    window.log.append("扫描 D:\\downloads\\bilibili")
    window.log.append("分组完成：3 组，6 个 m4s 流。")

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
