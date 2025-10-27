# 自动截图器

桌面端工具，用于轮询截取指定窗口截图，可选自动合成 MP4 预览。

## 开发环境

```bash
# 克隆仓库后，安装 Python 依赖
python -m venv .venv
.venv\Scripts\activate
#source .venv/bin/activate
python -m pip install -r backend/requirements.txt

# 安装前端依赖并构建静态资源
cd frontend
npm install
npm run build
```

开发时可直接运行：

```bash
cd backend
python app.py
```

前端界面通过 PyWebView 内嵌，`npm run build` 后的资源位于 `frontend/dist`。

## 打包发行

后台使用 PyInstaller 打包，提供了 PowerShell 脚本：

```bash
pwsh ./backend/build.ps1 -Version 1.2.0
```

脚本会：

1. 检查 `frontend/dist` 是否存在；
2. 安装 `backend/requirements.txt` 依赖；
3. 调用 PyInstaller 生成一体化 exe，输出在 `backend/dist`。

生成文件命名为 `ScreenCapture_版本号_日期.exe`，图标位于 `backend/favicon.ico`。

## 功能简介

- 列出当前可用窗口，并持续截屏保存 PNG；
- 支持自定义保存目录、截图间隔（最小 0.01s）；
- 可选勾选生成 MP4（依赖 moviepy）；
- 默认保存到桌面（以窗口名+时间建立子目录）；
- 提供新的科技感截图图标。

## 注意

- 生成 MP4 需安装 ffmpeg（moviepy 会自动提示）；
- 打包前务必重新执行 `npm run build` 确保前端资源最新。
