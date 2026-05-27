# bilibili-m4s-merger

一个面向非技术用户的 **B 站 m4s 批量混流工具**，带图形界面。

从 IDM（或其他下载器）下载 B 站视频后，会得到一堆分离的 `视频标题_1.m4s`、`视频标题_2.m4s`... 文件。本工具自动：

1. **扫描**一个文件夹下所有 m4s
2. **按文件名分组**（`标题_数字.m4s` → 按"标题"归组）
3. **用 ffprobe 自动识别**每个 m4s 是视频流还是音频流（不依赖文件大小猜测）
4. **默认勾选最大码率/分辨率的视频 + 最大的音频**，你可手动改选
5. **一键批量调用 ffmpeg 无损封装**为 MP4（`-c copy`，零转码，几秒一个）

---

## 📥 下载使用（普通用户）

到 [Releases 页面](https://github.com/whenitcomesto/bilibili-m4s-merger/releases) 下载最新版的 `bilibili-m4s-merger.exe`，**双击运行即可**。

- ✅ 不需要装 Python、不需要装 ffmpeg —— 全都已经打包在 .exe 里
- ✅ 不需要安装，下载即用，绿色软件
- ✅ 文件大小约 200MB（因为内含 ffmpeg）

### ⚠ 首次运行可能弹出 Windows 安全警告

因为本程序没有花钱购买代码签名证书，Windows 会弹出 **"Windows protected your PC"** 的蓝色提示。处理方法：

1. 点击 **"More info"**（更多信息）
2. 点击 **"Run anyway"**（仍要运行）

之后再次运行就不会再弹这个警告了。这是所有未签名开源软件的通病，本程序源码完全公开，可放心使用。

### 使用步骤

1. 双击 `.exe` 启动程序
2. 点击「选择输入文件夹」，选中含有 m4s 文件的目录
3. 点击「选择输出文件夹」，选 MP4 输出位置
4. 点击「扫描并识别」，等待几秒
5. 检查每组默认勾选的视频/音频是否符合预期，可手动改选
6. 点击「开始批量混流」，等待完成

---

## 特点

- ✅ 纯 Python + PyQt6，源码不到 500 行，便于阅读和修改
- ✅ 用 `ffprobe` 探测流类型，比"按大小猜"更可靠
- ✅ 无损封装：调用 `ffmpeg -c copy`，画质音质不动一根毫毛
- ✅ 批量处理：识别完一次确认，全部混流
- ✅ 安全：默认保留原始 m4s 文件，不会自动删除

## 文件名约定

本工具按 `(.+)_(\d+)\.m4s$` 正则分组：

- ✅ `漫长的季节EP01_1.m4s` 和 `漫长的季节EP01_2.m4s` → 同组 "漫长的季节EP01"
- ✅ `视频A_1.m4s`、`视频A_2.m4s`、`视频B_1.m4s` → 两组
- ⚠ 不符合该模式的文件会被列入"未匹配"区，需手动处理

如果你的下载器使用其他命名方式，可修改 `core.py` 顶部的 `GROUP_PATTERN`。

---

## 🛠 从源码运行（开发者）

需要 Python 3.10+：

```bash
git clone https://github.com/whenitcomesto/bilibili-m4s-merger.git
cd bilibili-m4s-merger
pip install -r requirements.txt
python main.py
```

源码运行模式下需要系统已安装 ffmpeg。Windows 推荐：

```powershell
winget install --id Gyan.FFmpeg
```

或手动下载 <https://www.gyan.dev/ffmpeg/builds/>，把 `bin` 目录加入系统 PATH。

## 🔨 自己构建 .exe

```bash
pip install pyinstaller PyQt6
python build.py
```

`build.py` 会自动：
1. 下载 ffmpeg essentials build（首次运行，缓存到 `vendor/`）
2. 用 PyInstaller `--onefile --windowed` 打包
3. 输出到 `dist/bilibili-m4s-merger.exe`

---

## 技术说明

- m4s 本身就是 fragmented MP4 容器，ffmpeg 可以直接 `-c copy` 封装成标准 MP4
- 添加 `-movflags +faststart` 让 MP4 适合网络播放（moov atom 移到文件头）
- 每个 m4s 用 ffprobe 探测 `codec_type` 字段判断 video / audio，准确率 100%
- GUI 使用 QThread 后台执行扫描和混流，不阻塞界面
- PyInstaller `--onefile` 模式：ffmpeg/ffprobe 被嵌入 .exe，启动时解压到临时目录由 `core.py:_bundled()` 找到并调用

## 项目结构

```
bilibili-m4s-merger/
├── core.py            # 扫描、分组、探测、混流核心逻辑（无 GUI 依赖）
├── main.py            # PyQt6 图形界面
├── build.py           # 构建 .exe 的脚本（下载 ffmpeg + PyInstaller）
├── requirements.txt
├── LICENSE
└── README.md
```

`core.py` 不依赖 PyQt6，可单独用于 CLI 脚本或测试。

## 贡献

欢迎 PR 和 issue。可考虑的改进方向：

- [ ] 支持自定义文件名正则
- [ ] 支持其他下载器的命名（如 yt-dlp、annie、BiliBili-Evolved）
- [ ] 自定义应用图标
- [ ] 进度条显示当前文件的混流进度（解析 ffmpeg stderr）
- [ ] 国际化（英文界面）
- [ ] macOS / Linux 构建

## License

[MIT](LICENSE) © whenitcomesto

ffmpeg 二进制采用 LGPL/GPL 授权，详见 <https://ffmpeg.org/legal.html>。本项目仅在打包发布时引用 gyan.dev 的 essentials build，不修改其源码。
