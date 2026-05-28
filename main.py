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
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
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


def _resource_base() -> Path:
    """Where to find bundled resources: PyInstaller _MEIPASS, else source dir."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base)
    return Path(__file__).resolve().parent


def load_stylesheet() -> str:
    """Load style.qss, rewriting relative asset URLs to absolute paths."""
    base = _resource_base()
    qss_path = base / "style.qss"
    if not qss_path.is_file():
        return ""
    qss = qss_path.read_text(encoding="utf-8")
    assets_dir = (base / "assets").as_posix()
    return qss.replace("url(assets/", f"url({assets_dir}/")


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
    def __init__(self, group: VideoGroup, index: int, on_remove_stream=None) -> None:
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.group = group
        self.index = index
        self.on_remove_stream = on_remove_stream  # callable(stream, group)
        self.enabled_checkbox = QCheckBox()
        self.video_buttons = QButtonGroup(self)
        self.audio_buttons = QButtonGroup(self)
        self._build_ui()

    def _build_ui(self) -> None:
        self.setObjectName("groupCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 18)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(12)
        title_label = QLabel(self.group.title)
        title_label.setObjectName(
            "groupTitle" if self.group.is_complete else "groupTitleIncomplete"
        )
        title_label.setWordWrap(True)
        header.addWidget(title_label, stretch=1)

        pill = QLabel("✓ 就绪" if self.group.is_complete else "缺少配对流")
        pill.setObjectName("pillReady" if self.group.is_complete else "pillMissing")
        pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(pill, alignment=Qt.AlignmentFlag.AlignVCenter)

        if self.group.is_complete:
            self.enabled_checkbox.setText("加入混流")
            self.enabled_checkbox.setChecked(True)
        else:
            self.enabled_checkbox.setText("不可用")
            self.enabled_checkbox.setEnabled(False)
        header.addWidget(self.enabled_checkbox, alignment=Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(header)

        # Output filename (editable)
        fn_label = QLabel("输出文件名")
        fn_label.setObjectName("streamSectionLabel")
        layout.addWidget(fn_label)

        fn_row = QHBoxLayout()
        fn_row.setSpacing(6)
        self.filename_edit = QLineEdit()
        self.filename_edit.setObjectName("filenameEdit")
        default_name = sanitize_filename(self.group.title)
        self.filename_edit.setText(default_name)
        self.filename_edit.setPlaceholderText(default_name)
        if not self.group.is_complete:
            self.filename_edit.setEnabled(False)
        fn_row.addWidget(self.filename_edit, stretch=1)
        fn_suffix = QLabel(".mp4")
        fn_suffix.setObjectName("filenameSuffix")
        fn_row.addWidget(fn_suffix, alignment=Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(fn_row)

        if self.group.video_streams:
            v_label = QLabel("视频流")
            v_label.setObjectName("streamSectionLabel")
            layout.addWidget(v_label)
            default = self.group.default_video()
            for s in self.group.video_streams:
                row = self._make_stream_row(s, default=s is default, button_group=self.video_buttons)
                layout.addWidget(row)
        else:
            layout.addWidget(self._warning("⚠ 未找到视频流"))

        if self.group.audio_streams:
            a_label = QLabel("音频流")
            a_label.setObjectName("streamSectionLabel")
            layout.addWidget(a_label)
            default = self.group.default_audio()
            for s in self.group.audio_streams:
                row = self._make_stream_row(s, default=s is default, button_group=self.audio_buttons)
                layout.addWidget(row)
        else:
            layout.addWidget(self._warning("⚠ 未找到音频流"))

        if self.group.unknown_streams:
            layout.addWidget(self._warning("⚠ 无法识别类型的流（已忽略）："))
            for s in self.group.unknown_streams:
                err = f" — {s.probe_error}" if s.probe_error else ""
                lbl = QLabel(f"  · {s.path.name}{err}")
                lbl.setStyleSheet("color: #92400E;")
                layout.addWidget(lbl)

    def _make_stream_row(self, s: Stream, default: bool, button_group: QButtonGroup) -> QWidget:
        parts = [s.path.name, s.size_mb]
        if s.codec_name:
            parts.append(s.codec_name)
        if s.is_video and s.resolution != "-":
            parts.append(s.resolution)
        if s.bitrate_kbps != "-":
            parts.append(s.bitrate_kbps)
        label = "   ·   ".join(parts)
        radio = QRadioButton(label)
        radio.setProperty("stream_path", str(s.path))
        if default:
            radio.setChecked(True)
        button_group.addButton(radio)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        row_layout.addWidget(radio, stretch=1)

        remove_btn = QPushButton("移出")
        remove_btn.setObjectName("smallActionBtn")
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn.clicked.connect(lambda _, s=s: self._handle_remove(s))
        row_layout.addWidget(remove_btn, alignment=Qt.AlignmentFlag.AlignVCenter)
        return row

    def _handle_remove(self, stream: Stream) -> None:
        if self.on_remove_stream:
            self.on_remove_stream(stream, self.group)

    def _warning(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #B91C1C; font-size: 12px;")
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

    def output_filename(self) -> str:
        raw = self.filename_edit.text().strip() or self.group.title
        return f"{sanitize_filename(raw)}.mp4"


class UnmatchedSection(QWidget):
    """Card listing unmatched m4s files with manual grouping controls."""

    def __init__(
        self,
        streams: list[Stream],
        group_titles: list[str],
        on_add_to_group,        # callable(stream, group_title)
        on_create_new_group,    # callable(streams, new_title)
    ) -> None:
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("unmatchedCard")
        self.streams = streams
        self.group_titles = group_titles
        self.on_add_to_group = on_add_to_group
        self.on_create_new_group = on_create_new_group
        self.checkboxes: list[tuple[QCheckBox, Stream]] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 18)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(12)
        title = QLabel(f"未匹配文件 ({len(self.streams)})")
        title.setObjectName("groupTitle")
        header.addWidget(title, stretch=1)
        pill = QLabel("待手动归组")
        pill.setObjectName("pillWarning")
        pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(pill, alignment=Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(header)

        desc = QLabel("以下文件不符合 标题_数字.m4s 命名规则。可单个加入现有组，或勾选多个后新建组。")
        desc.setObjectName("unmatchedDesc")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        for s in self.streams:
            row = QWidget()
            r = QHBoxLayout(row)
            r.setContentsMargins(0, 0, 0, 0)
            r.setSpacing(10)

            cb = QCheckBox()
            self.checkboxes.append((cb, s))
            r.addWidget(cb)

            info_parts = [s.path.name, s.size_mb]
            kind = "视频" if s.is_video else "音频" if s.is_audio else "未知"
            info_parts.append(kind)
            if s.codec_name:
                info_parts.append(s.codec_name)
            if s.is_video and s.resolution != "-":
                info_parts.append(s.resolution)
            if s.bitrate_kbps != "-":
                info_parts.append(s.bitrate_kbps)
            info_label = QLabel("   ·   ".join(info_parts))
            info_label.setObjectName("unmatchedInfo")
            r.addWidget(info_label, stretch=1)

            add_btn = QPushButton("加入组 ▾")
            add_btn.setObjectName("smallActionBtn")
            add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if self.group_titles:
                menu = QMenu(add_btn)
                for t in self.group_titles:
                    act = menu.addAction(t)
                    act.triggered.connect(
                        lambda checked=False, stream=s, title=t: self.on_add_to_group(stream, title)
                    )
                add_btn.setMenu(menu)
            else:
                add_btn.setEnabled(False)
                add_btn.setToolTip("当前没有可加入的组——先用「新建分组」创建一个")
            r.addWidget(add_btn)

            layout.addWidget(row)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        select_all = QPushButton("全选")
        select_all.clicked.connect(lambda: self._set_all_checked(True))
        actions.addWidget(select_all)
        select_none = QPushButton("全不选")
        select_none.clicked.connect(lambda: self._set_all_checked(False))
        actions.addWidget(select_none)
        actions.addStretch(1)
        new_group = QPushButton("用选中文件新建分组")
        new_group.clicked.connect(self._handle_new_group)
        actions.addWidget(new_group)
        layout.addLayout(actions)

    def _set_all_checked(self, value: bool) -> None:
        for cb, _ in self.checkboxes:
            cb.setChecked(value)

    def _handle_new_group(self) -> None:
        selected = [s for cb, s in self.checkboxes if cb.isChecked()]
        if not selected:
            QMessageBox.information(self, "提示", "请先勾选要归入新组的文件。")
            return
        default_name = sanitize_filename(selected[0].path.stem) or "新分组"
        name, ok = QInputDialog.getText(
            self,
            "新建分组",
            "请输入分组名（同时作为默认输出文件名）：",
            text=default_name,
        )
        if not ok:
            return
        name = name.strip()
        if not name:
            QMessageBox.warning(self, "提示", "分组名不能为空。")
            return
        self.on_create_new_group(selected, name)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("bilibili-m4s-merger")
        self.resize(900, 700)

        self.input_folder: Path | None = None
        self.output_folder: Path | None = None
        self.video_groups: list[VideoGroup] = []
        self.unmatched_streams: list[Stream] = []
        self.group_widgets: list[GroupWidget] = []
        self.unmatched_widget: UnmatchedSection | None = None
        self.scan_worker: ScanWorker | None = None
        self.mux_worker: MuxWorker | None = None

        self.ffmpeg_path = find_ffmpeg()
        self.ffprobe_path = find_ffprobe()

        self._build_ui()
        self._check_dependencies()

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(32, 28, 32, 24)
        root.setSpacing(18)

        # Header
        title = QLabel("Bilibili m4s 混流工具")
        title.setObjectName("appTitle")
        subtitle = QLabel("识别文件夹中的 m4s 文件，按文件名分组后无损封装为 MP4")
        subtitle.setObjectName("appSubtitle")
        root.addWidget(title)
        root.addWidget(subtitle)
        root.addSpacing(4)

        # Folder pickers section
        folders_label = QLabel("文件夹")
        folders_label.setObjectName("sectionLabel")
        root.addWidget(folders_label)

        in_row = QHBoxLayout()
        in_row.setSpacing(12)
        btn_in = QPushButton("选择输入文件夹")
        btn_in.clicked.connect(self._choose_input)
        self.input_label = QLabel("未选择")
        self.input_label.setObjectName("pathLabel")
        in_row.addWidget(btn_in)
        in_row.addWidget(self.input_label, stretch=1)
        root.addLayout(in_row)

        out_row = QHBoxLayout()
        out_row.setSpacing(12)
        btn_out = QPushButton("选择输出文件夹")
        btn_out.clicked.connect(self._choose_output)
        self.output_label = QLabel("未选择")
        self.output_label.setObjectName("pathLabel")
        out_row.addWidget(btn_out)
        out_row.addWidget(self.output_label, stretch=1)
        root.addLayout(out_row)

        root.addSpacing(6)

        # Action row
        action_row = QHBoxLayout()
        action_row.setSpacing(10)
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
        self.mux_btn.setObjectName("primary")
        self.mux_btn.clicked.connect(self._start_mux)
        action_row.addWidget(self.mux_btn)
        root.addLayout(action_row)

        # Groups list
        self.groups_container = QWidget()
        self.groups_container.setObjectName("groupsContainer")
        self.groups_layout = QVBoxLayout(self.groups_container)
        self.groups_layout.setSpacing(12)
        self.groups_layout.setContentsMargins(0, 0, 0, 0)
        self.groups_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidget(self.groups_container)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        root.addWidget(scroll, stretch=2)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setTextVisible(False)
        root.addWidget(self.progress)

        self.status_label = QLabel("就绪")
        self.status_label.setObjectName("statusBar")
        root.addWidget(self.status_label)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(140)
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
        if self.unmatched_widget is not None:
            self.unmatched_widget.setParent(None)
            self.unmatched_widget.deleteLater()
            self.unmatched_widget = None

    def refresh_display(self) -> None:
        """Rebuild groups + unmatched widgets from current self.video_groups / unmatched_streams state."""
        self._clear_groups()
        insert_at = self.groups_layout.count() - 1  # before the stretch

        # Unmatched section first (if any), so user sees it at the top
        if self.unmatched_streams:
            self.unmatched_widget = UnmatchedSection(
                streams=self.unmatched_streams,
                group_titles=[g.title for g in self.video_groups],
                on_add_to_group=self.move_to_group,
                on_create_new_group=self.move_to_new_group,
            )
            self.groups_layout.insertWidget(insert_at, self.unmatched_widget)
            insert_at += 1

        for i, g in enumerate(self.video_groups):
            widget = GroupWidget(g, i, on_remove_stream=self.remove_from_group)
            self.groups_layout.insertWidget(insert_at, widget)
            insert_at += 1
            self.group_widgets.append(widget)

        total = len(self.video_groups)
        ready = sum(1 for g in self.video_groups if g.is_complete)
        parts = [f"识别到 {total} 个视频"]
        if total:
            parts.append(f"{ready} 个就绪")
        if self.unmatched_streams:
            parts.append(f"{len(self.unmatched_streams)} 个文件待手动归组")
        self.status_label.setText("，".join(parts) if total or self.unmatched_streams else "未找到 m4s 文件")

    def move_to_group(self, stream: Stream, target_title: str) -> None:
        target = next((g for g in self.video_groups if g.title == target_title), None)
        if target is None or stream not in self.unmatched_streams:
            return
        self.unmatched_streams.remove(stream)
        target.streams.append(stream)
        self._log(f"→ {stream.path.name} 加入组「{target_title}」")
        self.refresh_display()

    def move_to_new_group(self, streams: list[Stream], title: str) -> None:
        if any(g.title == title for g in self.video_groups):
            QMessageBox.warning(self, "提示", f"已存在同名组「{title}」，请换一个名字。")
            return
        for s in streams:
            if s in self.unmatched_streams:
                self.unmatched_streams.remove(s)
        new_group = VideoGroup(title=title, streams=list(streams))
        self.video_groups.append(new_group)
        self._log(f"→ 新建组「{title}」，含 {len(streams)} 个流")
        self.refresh_display()

    def remove_from_group(self, stream: Stream, source_group: VideoGroup) -> None:
        if stream not in source_group.streams:
            return
        source_group.streams.remove(stream)
        self.unmatched_streams.append(stream)
        if not source_group.streams:
            if source_group in self.video_groups:
                self.video_groups.remove(source_group)
            self._log(f"← {stream.path.name} 移出组「{source_group.title}」（组已删除，无剩余流）")
        else:
            self._log(f"← {stream.path.name} 移出组「{source_group.title}」")
        self.refresh_display()

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

        self.video_groups = list(groups)
        self.unmatched_streams = list(unmatched)

        if not groups and not unmatched:
            self.status_label.setText("未找到 m4s 文件")
            self._log("未找到 m4s 文件。")
            return

        total_streams = sum(len(g.streams) for g in groups) + len(unmatched)
        self._log(
            f"分组完成：{len(groups)} 组、{total_streams} 个 m4s 流；"
            f"其中 {len(unmatched)} 个文件待手动归组。"
        )
        self.refresh_display()

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
        used_names: dict[str, str] = {}  # filename -> first group title
        overwrite = self.overwrite_checkbox.isChecked()

        for w in self.group_widgets:
            if not w.is_enabled():
                continue
            v = w.selected_video()
            a = w.selected_audio()
            if not v or not a:
                continue
            filename = w.output_filename()
            if filename in used_names:
                QMessageBox.warning(
                    self,
                    "文件名冲突",
                    f"以下两个分组的输出文件名相同，请修改其中一个：\n\n"
                    f"  · {used_names[filename]}\n"
                    f"  · {w.group.title}\n\n"
                    f"两者都想输出为：{filename}",
                )
                return
            used_names[filename] = w.group.title
            out = self.output_folder / filename
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
    qss = load_stylesheet()
    if qss:
        app.setStyleSheet(qss)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
