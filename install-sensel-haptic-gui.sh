#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later

set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
GUI_FILE="${PROJECT_DIR}/tools/sensel_haptic_gui.py"
GUI_DESKTOP_FILE="${PROJECT_DIR}/tools/sensel-haptic-control.desktop"
TRANSLATION_DIR="${PROJECT_DIR}/locale"
TRANSLATION_DOMAIN="sensel-haptic-control"
HELPER_FILE="${PROJECT_DIR}/scripts/sensel-haptic-set"
DAEMON_FILE="${PROJECT_DIR}/scripts/sensel-haptic-daemon"
POLKIT_RULE_FILE="${PROJECT_DIR}/scripts/sensel-haptic-polkit.rules"

for file in "${GUI_FILE}" "${GUI_DESKTOP_FILE}" "${HELPER_FILE}" "${DAEMON_FILE}" "${POLKIT_RULE_FILE}"; do
    [ -f "${file}" ] || { echo "错误：找不到 ${file}" >&2; exit 1; }
done
[ -d "${TRANSLATION_DIR}" ] || { echo "错误：找不到翻译目录 ${TRANSLATION_DIR}" >&2; exit 1; }

command -v sudo >/dev/null || { echo "错误：找不到 sudo" >&2; exit 1; }
command -v msgfmt >/dev/null || { echo "错误：找不到 msgfmt" >&2; exit 1; }
command -v pkexec >/dev/null || echo "警告：未找到 pkexec，GUI 启动后无法获得设备权限。" >&2

install_translations() {
    local po_file language
    while IFS= read -r -d '' po_file; do
        language="$(basename "$(dirname "$(dirname "${po_file}")")")"
        sudo install -d -m 0755 "/usr/share/locale/${language}/LC_MESSAGES"
        sudo msgfmt --check --check-format \
            -o "/usr/share/locale/${language}/LC_MESSAGES/${TRANSLATION_DOMAIN}.mo" \
            "${po_file}"
    done < <(find "${TRANSLATION_DIR}" -type f \
        -path "*/LC_MESSAGES/${TRANSLATION_DOMAIN}.po" -print0)
}

sudo install -d -m 0755 /usr/local/bin /usr/local/libexec /usr/share/applications /etc/polkit-1/rules.d
sudo install -o root -g root -m 0755 "${GUI_FILE}" /usr/local/bin/sensel-haptic-control
sudo install -o root -g root -m 0755 "${HELPER_FILE}" /usr/local/libexec/sensel-haptic-set
sudo install -o root -g root -m 0755 "${DAEMON_FILE}" /usr/local/libexec/sensel-haptic-daemon
sudo install -o root -g root -m 0644 "${POLKIT_RULE_FILE}" /etc/polkit-1/rules.d/49-sensel-haptic.rules
sudo install -o root -g root -m 0644 "${GUI_DESKTOP_FILE}" /usr/share/applications/sensel-haptic-control.desktop
install_translations
sudo update-desktop-database /usr/share/applications 2>/dev/null || true

echo "独立 Sensel Haptic Touchpad 控制面板已安装。"
echo "启动命令：sensel-haptic-control"
