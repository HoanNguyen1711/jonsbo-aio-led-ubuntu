#!/bin/sh
# Launcher: chạy package rgbctl nằm cạnh script này (kể cả khi gọi qua symlink)
DIR="$(dirname "$(readlink -f "$0")")"
PYTHONPATH="$DIR${PYTHONPATH:+:$PYTHONPATH}" exec python3 -m rgbctl "$@"
