# ShotPilot

[English](README.md) | 简体中文

## 概述

ShotPilot 是一款桌面端工具，可按固定间隔截取选定窗口或显示器的截图，并可在任务结束时自动合成 MP4 预览。

## 开发环境

```bash
# 创建并激活 Python 虚拟环境
python -m venv .venv
source .venv/bin/activate      # macOS/Linux
# .venv\Scripts\activate       # Windows

# 安装后端依赖
python -m pip install -r backend/requirements.txt

# 安装前端依赖并构建静态资源
cd frontend
npm install
npm run build
```

## 本地调试

```bash
cd backend
python app.py
```

- 前端界面通过 PyWebView 内嵌展示。
- 执行 `npm run build` 后的静态资源位于 `frontend/dist`。

## 打包发行

项目提供 PowerShell 脚本，基于 PyInstaller 打包桌面应用：

```bash
pwsh ./backend/build.ps1 -Version 1.2.0
```

脚本会：

1. 检查 `frontend/dist` 是否存在；
2. 安装 `backend/requirements.txt` 中的依赖；
3. 调用 PyInstaller 生成一体化可执行文件，输出在 `backend/dist`。

生成文件命名为 `ShotPilot_版本号_日期.exe`，图标位于 `backend/favicon.ico`。

## 功能简介

- 列出当前可用窗口，并按设定间隔截屏保存 PNG；
- 支持自定义保存目录与截图间隔（最小 0.01 秒）；
- 可选在停止后合成 MP4（依赖 moviepy）；
- 默认保存到桌面（按窗口名和时间创建子目录）；
- 提供全新的科技感截图图标。

## 注意事项

- 若需合成 MP4，请安装 ffmpeg（moviepy 会自动提示）。
- 打包前请重新执行 `npm run build`，确保前端资源为最新版本。
