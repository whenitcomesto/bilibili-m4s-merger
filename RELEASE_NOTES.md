# v0.1.0 — First Release / 首次发布

## 中文

### ✨ 主要功能
- 一键扫描文件夹，按文件名自动将 m4s 文件分组（`视频标题_数字.m4s` 模式）
- 用 ffprobe 准确识别视频流和音频流，不依赖文件大小猜测
- 默认勾选每组中最大码率的视频 + 最大的音频，可手动改选
- 调用 ffmpeg `-c copy` **无损封装**为 MP4，零转码、几秒一个
- 批量混流，带进度条和实时日志
- **内含 ffmpeg/ffprobe，下载即用**，不需要单独安装

### 📦 下载
**`bilibili-m4s-merger.exe`** ← Windows 用户下载这个，双击即可运行。

### ⚠ 首次运行 Windows 安全警告
未签名 .exe 会被 SmartScreen 拦截，弹出 "Windows protected your PC"：
1. 点击 **"More info"**（更多信息）
2. 点击 **"Run anyway"**（仍要运行）

这是所有未签名开源软件的通病。本项目源码完全公开，可放心使用。

### 📝 使用步骤
1. 双击 .exe 启动
2. 选择含有 m4s 文件的输入文件夹
3. 选择 MP4 输出文件夹
4. 点「扫描并识别」
5. 检查每组默认选项，必要时手动改选
6. 点「开始批量混流」

---

## English

### ✨ Features
- One-click folder scan with automatic m4s grouping by filename (`title_<n>.m4s` pattern)
- Accurate video/audio stream detection via ffprobe — no size guessing
- Default selection picks highest-bitrate video + audio in each group, user can override
- **Lossless** MP4 muxing via `ffmpeg -c copy` — zero re-encoding, seconds per file
- Batch processing with progress bar and live log
- **ffmpeg/ffprobe bundled** — just download and run, no separate install needed

### 📦 Download
**`bilibili-m4s-merger.exe`** — Windows users, double-click to run.

### ⚠ First-Run SmartScreen Warning
Because the .exe is unsigned, Windows will show "Windows protected your PC":
1. Click **"More info"**
2. Click **"Run anyway"**

Common for unsigned open-source software. Full source is in this repo.
