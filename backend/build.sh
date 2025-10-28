#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./build.sh [-p python] [-v version]

Options:
  -p, --python   Python executable to use (default: python3)
  -v, --version  Version string used in the output name (default: 1.0.0)
  -h, --help     Show this help message
EOF
}

python_bin="python3"
version="1.0.0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -p|--python)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for $1" >&2
        usage
        exit 1
      fi
      python_bin="$2"
      shift 2
      ;;
    -v|--version)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for $1" >&2
        usage
        exit 1
      fi
      version="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if ! command -v "$python_bin" >/dev/null 2>&1; then
  echo "Python executable not found: $python_bin" >&2
  exit 1
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
frontend_dist="$script_dir/../frontend/dist/index.html"

if [[ ! -f "$frontend_dist" ]]; then
  echo "frontend/dist 未找到，请先在 frontend 目录执行 npm run build" >&2
  exit 1
fi

platform_label="macos"
output_name="ShotPilot-${version}-${platform_label}"

echo "Packaging as $output_name"

"$python_bin" -m pip install -r "$script_dir/requirements.txt"

pyinstaller_args=(
  "app.py"
  "--name" "$output_name"
  "--onefile"
  "--windowed"
  "--add-data" "../frontend/dist:frontend/dist"
)

icon_path="$script_dir/favicon.ico"
if [[ -f "$icon_path" ]]; then
  pyinstaller_args+=("--icon" "$icon_path")
fi

(
  cd "$script_dir"
  "$python_bin" -m PyInstaller "${pyinstaller_args[@]}"
)

echo "Build finished: backend/dist/${output_name}"
