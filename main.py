"""bilibili-m4s-merger — GUI to scan, group, and mux B站 m4s files into MP4."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core import (
    Stream,
    VideoGroup,
    find_ffmpeg,
    find_ffprobe,
    mux,
    sanitize_filename,
    scan_folder,
)


@dataclass
class MuxJob:
    title: str
    video: Path
    audio: Path
    output: Path


class ScanWorker(QThread):
    finished_with = pyqtSignal(list, list, str)

    def __init__(self, folder: Path, ffprobe: str) -> None:
        super().__init__()
        self._folder = folder
        self._ffprobe = ffprobe

    def run(self) -> None:
        try:
            groups, unmatched = scan_folder(self._folder, self._ffprobe)
            self.finished_with.emit(groups, unmatched, "")
        except Exception as exc:  # noqa: BLE001
            self.finished_with.emit([], [], f"{exc}")


class MuxWorker(QThread):
    progress = pyqtSignal(int, int, str)
    job_done = pyqtSignal(int, bool, str)
    all_done = pyqtSignal()

    def __init__(self, ffmpeg: str, jobs: list[MuxJob], overwrite: bool) -> None:
        super().__init__()
        self._ffmpeg = ffmpeg
        self._jobs = jobs
        self._overwrite = overwrite
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        total = len(self._jobs)
        for i, job in enumerate(self._jobs):
            if self._cancel:
                self.progress.emit(i, total, "Cancelled")
                break
            self.progress.emit(i, total, f"Muxing: {job.title}")
            ok, msg = mux(self._ffmpeg, job.video, job.audio, job.output, overwrite=self._overwrite)
            self.job_done.emit(i, ok, msg)
        self.all_done.emit()


class GroupWidget(QWidget):
    def __init__(self, group: VideoGroup, index: int) -> None:
        super().__init__()
        self.group = group
        self.index = index
        self.enabled_checkbox = QCheckBox()
        self.video_buttons = QButtonGroup(self)
        self.audio_buttons = QButtonGroup(self)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 10)

        header = QHBoxLayout()
        title_label = QLabel(self.group.title)
        title_font = title_label.font()
        title_font.setBold(True)
        title_font.setPointSize(title_font.pointSize() + 1)
        title_label.setFont(title_font)
        title_label.setWordWrap(True)
        header.addWidget(title_label, stretch=1)

        if self.group.is_complete:
            self.enabled_checkbox.setText("待混流")
            self.enabled_checkbox.setChecked(True)
        else:
            self.enabled_checkbox.setText("缺少配对流")
            self.enabled_checkbox.setEnabled(False)
            title_label.setStyleSheet("color: #b00020;")
        header.addWidget(self.enabled_checkbox)
        layout.addLayout(header)

        if self.group.video_streams:
            layout.addWidget(QLabel("视频流："))
            default = self.group.default_video()
            for s in self.group.video_streams:
                radio = self._make_radio(s, default=s is default)
                self.video_buttons.addButton(radio)
                layout.addWidget(radio)
        else:
            layout.addWidget(self._warning("⚠ 未找到视频流"))

        if self.group.audio_streams:
            layout.addWidget(QLabel("音频流："))
            default = self.group.default_audio()
            for s in self.group.audio_streams:
                radio = self._make_radio(s, default=s is default)
                self.audio_buttons.addButton(radio)
                layout.addWidget(radio)
        else:
            layout.addWidget(self._warning("⚠ 未找到音频流"))

        if self.group.unknown_streams:
            layout.addWidget(self._warning("⚠ 无法识别类型的流（已忽略）："))
            for s in self.group.unknown_streams:
                err = f" — {s.probe_error}" if s.probe_error else ""
                layout.addWidget(QLabel(f"  · {s.path.name}{err}"))

        self.setStyleSheet("GroupWidget { border: 1px solid #d0d0d0; border-radius: 6px; background: #fafafa; }")

    def _make_radio(self, s: Stream, default: bool) -> QRadioButton:
        parts = [s.path.name, s.size_mb]
        if s.codec_name:
            parts.append(s.codec_name)
        if s.is_video and s.resolution != "-":
            parts.append(s.resolution)
        if s.bitrate_kbps != "-":
            parts.append(s.bitrate_kbps)
        label = "   ".join(parts)
        radio = QRadioButton(label)
        radio.setProperty("stream_path", str(s.path))
        if default:
            radio.setChecked(True)
        return radio

    def _warning(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #b00020;")
        return lbl

    def is_enabled(self) -> bool:
        return self.enabled_checkbox.isChecked() and self.enabled_checkbox.isEnabled()

    def set_enabled(self, value: bool) -> None:
        if self.enabled_checkbox.isEnabled():
            self.enabled_checkbox.setChecked(value)

    def selected_video(self) -> Path | None:
        btn = self.video_buttons.checkedButton()
        if btn is None:
            return None
        return Path(btn.property("stream_path"))

    def selected_audio(self) -> Path | None:
        btn = self.audio_buttons.checkedButton()
        if btn is None:
            return None
        return Path(btn.property("stream_path"))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("bilibili-m4s-merger")
        self.resize(900, 700)

        self.input_folder: Path | None = None
        self.output_folder: Path | None = None
        self.group_widgets: list[GroupWidget] = []
        self.scan_worker: ScanWorker | None = None
        self.mux_worker: MuxWorker | None = None

        self.ffmpeg_path = find_ffmpeg()
        self.ffprobe_path = find_ffprobe()

        self._build_ui()
        self._check_dependencies()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        in_row = QHBoxLayout()
        self.input_label = QLabel("输入文件夹：未选择")
        btn_in = QPushButton("选择输入文件夹")
        btn_in.clicked.connect(self._choose_input)
        in_row.addWidget(btn_in)
        in_row.addWidget(self.input_label, stretch=1)
        root.addLayout(in_row)

        out_row = QHBoxLayout()
        self.output_label = QLabel("输出文件夹：未选择")
        btn_out = QPushButton("选择输出文件夹")
        btn_out.clicked.connect(self._choose_output)
        out_row.addWidget(btn_out)
        out_row.addWidget(self.output_label, stretch=1)
        root.addLayout(out_row)

        action_row = QHBoxLayout()
        self.scan_btn = QPushButton("扫描并识别")
        self.scan_btn.clicked.connect(self._start_scan)
        action_row.addWidget(self.scan_btn)

        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.clicked.connect(lambda: self._set_all(True))
        action_row.addWidget(self.select_all_btn)

        self.select_none_btn = QPushButton("全不选")
        self.select_none_btn.clicked.connect(lambda: self._set_all(False))
        action_row.addWidget(self.select_none_btn)

        self.overwrite_checkbox = QCheckBox("覆盖已存在的输出文件")
        action_row.addWidget(self.overwrite_checkbox)

        action_row.addStretch(1)

        self.mux_btn = QPushButton("开始批量混流")
        self.mux_btn.clicked.connect(self._start_mux)
        font = QFont(self.mux_btn.font())
        font.setBold(True)
        self.mux_btn.setFont(font)
        action_row.addWidget(self.mux_btn)
        root.addLayout(action_row)

        self.groups_container = QWidget()
        self.groups_layout = QVBoxLayout(self.groups_container)
        self.groups_layout.setSpacing(8)
        self.groups_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidget(self.groups_container)
        scroll.setWidgetResizable(True)
        root.addWidget(scroll, stretch=2)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        self.status_label = QLabel("就绪")
        root.addWidget(self.status_label)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(160)
        root.addWidget(self.log)

    def _check_dependencies(self) -> None:
        if not self.ffmpeg_path or not self.ffprobe_path:
            self._log("❌ 未在系统 PATH 中找到 ffmpeg 或 ffprobe。请安装 ffmpeg 并将其加入 PATH 后重启本程序。")
            self._log("   下载地址：https://www.gyan.dev/ffmpeg/builds/  （选择 release essentials build）")
            self.scan_btn.setEnabled(False)
            self.mux_btn.setEnabled(False)
            QMessageBox.critical(
                self,
                "缺少依赖",
                "未找到 ffmpeg / ffprobe。\n\n请先安装 ffmpeg 并将其加入系统 PATH，然后重启本程序。",
            )
        else:
            self._log(f"✓ ffmpeg: {self.ffmpeg_path}")
            self._log(f"✓ ffprobe: {self.ffprobe_path}")

    def _choose_input(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择包含 m4s 文件的输入文件夹")
        if folder:
            self.input_folder = Path(folder)
            self.input_label.setText(f"输入文件夹：{folder}")

    def _choose_output(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择 MP4 输出文件夹")
        if folder:
            self.output_folder = Path(folder)
            self.output_label.setText(f"输出文件夹：{folder}")

    def _clear_groups(self) -> None:
        for w in self.group_widgets:
            w.setParent(None)
            w.deleteLater()
        self.group_widgets.clear()

    def _start_scan(self) -> None:
        if not self.input_folder:
            QMessageBox.warning(self, "提示", "请先选择输入文件夹。")
            return
        if not self.ffprobe_path:
            QMessageBox.warning(self, "提示", "未找到 ffprobe，无法扫描。")
            return
        self._clear_groups()
        self.scan_btn.setEnabled(False)
        self.status_label.setText("正在扫描并探测 m4s 文件……")
        self._log(f"扫描 {self.input_folder}")

        self.scan_worker = ScanWorker(self.input_folder, self.ffprobe_path)
        self.scan_worker.finished_with.connect(self._on_scan_done)
        self.scan_worker.start()

    def _on_scan_done(self, groups: list[VideoGroup], unmatched: list[Stream], error: str) -> None:
        self.scan_btn.setEnabled(True)
        if error:
            self.status_label.setText("扫描失败")
            self._log(f"❌ 扫描错误：{error}")
            QMessageBox.critical(self, "扫描失败", error)
            return

        if not groups and not unmatched:
            self.status_label.setText("未找到 m4s 文件")
            self._log("未找到 m4s 文件。")
            return

        insert_at = self.groups_layout.count() - 1
        for i, g in enumerate(groups):
            widget = GroupWidget(g, i)
            self.groups_layout.insertWidget(insert_at, widget)
            insert_at += 1
            self.group_widgets.append(widget)

        self.status_label.setText(
            f"识别到 {len(groups)} 个视频"
            + (f"，{len(unmatched)} 个文件未匹配命名规则" if unmatched else "")
        )
        self._log(f"分组完成：{len(groups)} 组，{sum(len(g.streams) for g in groups)} 个 m4s 流。")
        if unmatched:
            self._log(f"未匹配 _<数字> 命名规则的文件：{len(unmatched)}")
            for s in unmatched:
                self._log(f"  · {s.path.name}")

    def _set_all(self, value: bool) -> None:
        for w in self.group_widgets:
            w.set_enabled(value)

    def _start_mux(self) -> None:
        if not self.ffmpeg_path:
            QMessageBox.warning(self, "提示", "未找到 ffmpeg。")
            return
        if not self.output_folder:
            QMessageBox.warning(self, "提示", "请先选择输出文件夹。")
            return
        if not self.group_widgets:
            QMessageBox.warning(self, "提示", "请先扫描。")
            return

        jobs: list[MuxJob] = []
        skipped_existing: list[str] = []
        overwrite = self.overwrite_checkbox.isChecked()

        for w in self.group_widgets:
            if not w.is_enabled():
                continue
            v = w.selected_video()
            a = w.selected_audio()
            if not v or not a:
                continue
            out = self.output_folder / f"{sanitize_filename(w.group.title)}.mp4"
            if out.exists() and not overwrite:
                skipped_existing.append(out.name)
                continue
            jobs.append(MuxJob(title=w.group.title, video=v, audio=a, output=out))

        if skipped_existing:
            msg = "以下输出文件已存在，将被跳过（如需覆盖请勾选「覆盖已存在的输出文件」）：\n\n"
            msg += "\n".join(skipped_existing[:10])
            if len(skipped_existing) > 10:
                msg += f"\n…（共 {len(skipped_existing)} 个）"
            QMessageBox.information(self, "已跳过", msg)

        if not jobs:
            QMessageBox.information(self, "提示", "没有可混流的任务。")
            return

        confirm = QMessageBox.question(
            self,
            "确认",
            f"即将混流 {len(jobs)} 个视频到\n{self.output_folder}\n\n继续？",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self.mux_btn.setEnabled(False)
        self.scan_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, len(jobs))
        self.progress.setValue(0)
        self.status_label.setText(f"开始混流 {len(jobs)} 个任务……")
        self._log(f"=== 开始混流 {len(jobs)} 个任务 ===")

        self.mux_worker = MuxWorker(self.ffmpeg_path, jobs, overwrite=overwrite)
        self.mux_worker.progress.connect(self._on_mux_progress)
        self.mux_worker.job_done.connect(self._on_mux_job_done)
        self.mux_worker.all_done.connect(self._on_mux_all_done)
        self.mux_worker.start()

    def _on_mux_progress(self, current: int, total: int, message: str) -> None:
        self.progress.setValue(current)
        shown = current + 1 if current < total else current
        self.status_label.setText(f"[{shown}/{total}] {message}")

    def _on_mux_job_done(self, index: int, success: bool, message: str) -> None:
        prefix = "✓" if success else "✗"
        self._log(f"{prefix} {message}")
        self.progress.setValue(index + 1)

    def _on_mux_all_done(self) -> None:
        self.mux_btn.setEnabled(True)
        self.scan_btn.setEnabled(True)
        self.status_label.setText("混流完成")
        self._log("=== 全部任务结束 ===")
        QMessageBox.information(self, "完成", "批量混流已结束，详情见日志。")

    def _log(self, text: str) -> None:
        self.log.append(text)


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
