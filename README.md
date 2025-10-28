# ShotPilot

English | [简体中文](README.zh-CN.md)

## Overview

ShotPilot is a desktop utility that captures repeated screenshots from a selected window or monitor. It can optionally compile the captured frames into an MP4 preview when the session stops.

## Development Setup

```bash
# Create and activate the Python virtual environment
python -m venv .venv
source .venv/bin/activate      # macOS/Linux
# .venv\Scripts\activate       # Windows

# Install backend dependencies
python -m pip install -r backend/requirements.txt

# Install frontend dependencies and build static assets
cd frontend
npm install
npm run build
```

## Local Development

```bash
cd backend
python app.py
```

- The frontend UI is embedded through PyWebView.
- Assets produced by `npm run build` are stored in `frontend/dist`.

## Packaging

ShotPilot ships with a PowerShell helper that uses PyInstaller to build the desktop bundle:

```bash
pwsh ./backend/build.ps1 -Version 1.2.0
```

The script will:

1. Verify that `frontend/dist` exists.
2. Install dependencies listed in `backend/requirements.txt`.
3. Invoke PyInstaller to create a one-file executable under `backend/dist`.

The generated file is named `ShotPilot-<version>-windows.exe`, and the icon is located at `backend/favicon.ico`.

## Features

- Enumerate available windows and capture PNG snapshots on an interval.
- Customize the save directory and capture interval (minimum 0.01s).
- Optionally stitch the capture into an MP4 (requires `moviepy`).
- Default save path is the desktop with a timestamped folder.
- Provides a refreshed, modern capture icon.

## Notes

- FFmpeg is required to produce MP4 output (moviepy will prompt if missing).
- Re-run `npm run build` before packaging to ship the latest frontend assets.
