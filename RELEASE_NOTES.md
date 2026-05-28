# v0.1.2 — Smarter Grouping + Manual Matching

## 中文

### 🐛 修复
- **IDM 首份文件正确识别**：之前 IDM 下载的"第一份"无 `_N` 后缀文件（如 `视频.m4s`，配合后续 `视频_2.m4s`、`视频_3.m4s`）会被误判为未匹配，现在能正确归入对应组

### ✨ 新功能：未匹配文件手动归组
- 自动归组失败的文件不再被忽略，而是显示在 **黄色"未匹配文件"卡片** 中
- 每个未匹配文件可通过 **「加入组 ▾」** 下拉直接归入任意已有组
- 勾选多个未匹配文件后点 **「用选中文件新建分组」** 创建全新分组
- 已识别组内每个流旁边新增 **「移出」** 按钮，支持把误归的文件踢回未匹配区
- 状态栏同步显示"已识别 X 个视频、Y 个就绪、Z 个待手动归组"

### 🔧 内部
- 改用两遍扫描算法（第 1 遍按 `_N` 建组、第 2 遍把无后缀文件按 stem 匹配进组）
- UI 增加状态管理 + `refresh_display()`，所有归组/移出操作即时反映

### 📦 下载
**`bilibili-m4s-merger.exe`** ← Windows 用户下载这个，双击运行。

### ⚠ 首次运行 Windows 安全警告
SmartScreen 会弹 "Windows protected your PC"：点 **"More info" → "Run anyway"**。

---

## English

### 🐛 Fixes
- **Recognize IDM "first copy" files**: previously, files without a `_N` suffix (e.g. `video.m4s` alongside `video_2.m4s`, `video_3.m4s`) were misclassified as unmatched. They now correctly join their sibling group.

### ✨ New: Manual Grouping for Unmatched Files
- Files that can't be auto-grouped now appear in a **yellow "Unmatched files" card** instead of being ignored
- Each unmatched file has an **"Add to group ▾"** dropdown to merge it into any existing group
- Select multiple unmatched files and click **"Create new group from selection"** to make a fresh group
- Group cards now show a **"Remove"** button next to each stream, letting you eject mistakes back to the unmatched pile
- Status bar shows live count: "X videos identified, Y ready, Z files pending manual grouping"

### 🔧 Internal
- Two-pass scan algorithm (pass 1 builds groups from `_N`-suffixed files; pass 2 matches no-suffix files by stem)
- UI now has explicit state + `refresh_display()` for instant updates after any grouping action

### 📦 Download
**`bilibili-m4s-merger.exe`** — Windows users, double-click to run.
