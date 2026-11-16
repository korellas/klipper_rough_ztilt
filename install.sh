#!/bin/sh
set -eu
klipper_dir=${1:-"$HOME/klipper"}
source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
target="$klipper_dir/klippy/extras/rough_z_tilt.py"
test -d "$klipper_dir/klippy/extras" || { echo 'Klipper extras directory missing' >&2; exit 1; }
if [ -e "$target" ] && [ ! -L "$target" ]; then
    echo 'Refusing to replace an existing regular file' >&2
    exit 1
fi
ln -sfn "$source_dir/rough_z_tilt.py" "$target"
echo 'Installed. Add [rough_z_tilt] and restart Klipper while idle.'
