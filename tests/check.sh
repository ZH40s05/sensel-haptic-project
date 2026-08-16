#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later

set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_DIR}"

shell_files=(
    install-sensel-haptic-gui.sh
    install-sensel-gnome-settings.sh
    scripts/sensel-haptic-set
    tools/sensel-pkg-config
)

for file in "${shell_files[@]}"; do
    bash -n "${file}"
done

python3 - <<'PY'
from pathlib import Path

python_files = [
    Path("scripts/sensel-haptic-daemon"),
    Path("tools/sensel-hid-pipe.py"),
    Path("tools/sensel_haptic_gui.py"),
]

for path in python_files:
    compile(path.read_text(encoding="utf-8"), str(path), "exec")
PY

if command -v msgfmt >/dev/null 2>&1; then
    while IFS= read -r -d '' po_file; do
        msgfmt --check --check-format -o /dev/null "${po_file}"
    done < <(find locale -type f -name '*.po' -print0)
else
    echo "warning: msgfmt not installed; translation checks skipped" >&2
fi

if command -v desktop-file-validate >/dev/null 2>&1; then
    desktop-file-validate tools/sensel-haptic-control.desktop
else
    echo "warning: desktop-file-validate not installed; desktop check skipped" >&2
fi

echo "Static checks passed."
