# v0.1.1 — UI Redesign + Custom Filenames

## 中文

### ✨ 本次更新

- **全新 UI**：浅色卡片化设计，每个视频独立卡片展示
- **自定义输出文件名**：每张卡片都有可编辑的文件名输入框，默认填自动识别的标题，你可以随意修改
  - 自动检测重名冲突，弹窗提示
  - 自动清理 Windows 不允许的特殊字符
- **状态指示更清晰**：绿色 "✓ 就绪" / 红色 "缺少配对流" 标签一目了然
- **更清晰的流信息展示**：每个 m4s 显示编码（h264/aac）、分辨率、码率、文件大小
- 主操作按钮"开始批量混流"突出蓝色，次要按钮统一白底
- 字体层级、留白、圆角全面优化

### 📦 下载
**`bilibili-m4s-merger.exe`** ← Windows 用户下载这个，双击即可运行。

### ⚠ 首次运行 Windows 安全警告
未签名 .exe 会被 SmartScreen 拦截，弹出 "Windows protected your PC"：
1. 点击 **"More info"**（更多信息）
2. 点击 **"Run anyway"**（仍要运行）

### 📝 使用步骤
1. 双击 .exe 启动
2. 选择含有 m4s 文件的输入文件夹
3. 选择 MP4 输出文件夹
4. 点「扫描并识别」
5. 每张卡片可改输出文件名、选不同清晰度的视频/音频流
6. 点「开始批量混流」

---

## English

### ✨ What's New

- **Redesigned UI**: light theme with card-based layout for each video
- **Custom output filenames**: every card has an editable filename field, pre-filled with the auto-detected title
  - Duplicate-name conflict detection with warning dialog
  - Auto-sanitizes invalid Windows characters
- **Clearer status indicators**: green "✓ Ready" / red "Missing stream" pills
- **Richer stream info**: each m4s shows codec (h264/aac), resolution, bitrate, file size
- Primary mux button is now prominent blue; secondary buttons unified white
- Improved typography hierarchy, spacing, and rounded corners throughout

### 📦 Download
**`bilibili-m4s-merger.exe`** — Windows users, double-click to run.

### ⚠ First-Run SmartScreen Warning
Because the .exe is unsigned, Windows will show "Windows protected your PC":
1. Click **"More info"**
2. Click **"Run anyway"**
