#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later

set -euo pipefail

USER_HOME="$(getent passwd "$(id -un)" | cut -d: -f6)"
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
GNOME_VERSION="${SENSEL_GNOME_VERSION:-50.0}"
GNOME_SOURCE_DIR="${SENSEL_GNOME_SOURCE_DIR:-${PROJECT_DIR}/source/gnome-control-center-${GNOME_VERSION}}"
SOURCE_STAGE_ROOT="${SENSEL_GNOME_SOURCE_STAGE:-${PROJECT_DIR}/build/gnome-source}"
SOURCE_ARCHIVE_ROOT="${SENSEL_SOURCE_CACHE_DIR:-${XDG_CACHE_HOME:-${USER_HOME}/.cache}/sensel-haptic-control}"
SOURCE_ARCHIVE="${SENSEL_GNOME_SOURCE_ARCHIVE:-${SOURCE_ARCHIVE_ROOT}/gnome-control-center-${GNOME_VERSION}.tar.xz}"
GNOME_SOURCE_URL="${SENSEL_GNOME_SOURCE_URL:-https://download.gnome.org/sources/gnome-control-center/${GNOME_VERSION%.*}/gnome-control-center-${GNOME_VERSION}.tar.xz}"
if [ "${GNOME_VERSION}" = "50.0" ]; then
    GNOME_SOURCE_SHA256_DEFAULT="20e8d5b13b9f390581004cab34b74372c0ff4a16f9c11bffd93d8386fbcdeeb3"
else
    GNOME_SOURCE_SHA256_DEFAULT=
fi
GNOME_SOURCE_SHA256="${SENSEL_GNOME_SOURCE_SHA256-${GNOME_SOURCE_SHA256_DEFAULT}}"
SOURCE_DIR=
PATCH_FILE="${PROJECT_DIR}/patches/sensel-gnome-control-center.patch"
HELPER_FILE="${PROJECT_DIR}/scripts/sensel-haptic-set"
DAEMON_FILE="${PROJECT_DIR}/scripts/sensel-haptic-daemon"
POLKIT_RULE_FILE="${PROJECT_DIR}/scripts/sensel-haptic-polkit.rules"
GUI_FILE="${PROJECT_DIR}/tools/sensel_haptic_gui.py"
GUI_DESKTOP_FILE="${PROJECT_DIR}/tools/sensel-haptic-control.desktop"
TRANSLATION_DIR="${PROJECT_DIR}/locale"
TRANSLATION_DOMAIN="sensel-haptic-control"
BUILD_DIR="${SENSEL_GNOME_BUILD_DIR:-${PROJECT_DIR}/build/gnome-control-center-${GNOME_VERSION}}"
SOURCE_RPM="${SENSEL_SOURCE_RPM:-${PROJECT_DIR}/source/gnome-control-center-build/gnome-control-center-50.4-1.fc44.src.rpm}"

die() {
    echo "错误：$*" >&2
    exit 1
}

prepare_gnome_source() {
    if [ -f "${GNOME_SOURCE_DIR}/meson.build" ]; then
        SOURCE_DIR="${GNOME_SOURCE_DIR}"
        return
    fi

    command -v tar >/dev/null || die "找不到 tar，无法解压 GNOME 源码。"
    mkdir -p "${SOURCE_ARCHIVE_ROOT}" "${SOURCE_STAGE_ROOT}"

    if [ ! -f "${SOURCE_ARCHIVE}" ]; then
        source_part="${SOURCE_ARCHIVE}.part"
        if command -v curl >/dev/null 2>&1; then
            curl --fail --location --retry 3 \
                --output "${source_part}" "${GNOME_SOURCE_URL}"
        elif command -v wget >/dev/null 2>&1; then
            wget --quiet --tries=3 \
                --output-document="${source_part}" "${GNOME_SOURCE_URL}"
        else
            die "找不到 curl 或 wget，无法下载 GNOME 源码。"
        fi
        mv "${source_part}" "${SOURCE_ARCHIVE}"
    fi

    if [ -n "${GNOME_SOURCE_SHA256}" ]; then
        command -v sha256sum >/dev/null || die "找不到 sha256sum，无法校验 GNOME 源码。"
        if ! printf '%s  %s\n' "${GNOME_SOURCE_SHA256}" \
            "${SOURCE_ARCHIVE}" | sha256sum --check --status -; then
            die "GNOME 源码校验失败：${SOURCE_ARCHIVE}"
        fi
    fi

    SOURCE_DIR="${SOURCE_STAGE_ROOT}/gnome-control-center-${GNOME_VERSION}"
    if [ ! -f "${SOURCE_DIR}/meson.build" ]; then
        tar -xf "${SOURCE_ARCHIVE}" -C "${SOURCE_STAGE_ROOT}"
    fi
    [ -f "${SOURCE_DIR}/meson.build" ] ||
        die "GNOME 源码包内容不符合预期：${SOURCE_DIR}"
}

command -v sudo >/dev/null || die "找不到 sudo。请先安装 sudo，或以有管理员权限的用户运行。"
command -v dnf5 >/dev/null || die "此脚本面向 Fedora，需要 dnf5。"
prepare_gnome_source
[ -f "${PATCH_FILE}" ] || die "找不到补丁文件：${PATCH_FILE}"
[ -x "${HELPER_FILE}" ] || die "找不到特权 HID helper：${HELPER_FILE}"
[ -x "${DAEMON_FILE}" ] || die "找不到常驻 HID daemon：${DAEMON_FILE}"
[ -f "${POLKIT_RULE_FILE}" ] || die "找不到 Polkit 规则：${POLKIT_RULE_FILE}"
[ -f "${GUI_FILE}" ] || die "找不到独立 GUI：${GUI_FILE}"
[ -f "${GUI_DESKTOP_FILE}" ] || die "找不到独立 GUI 启动器：${GUI_DESKTOP_FILE}"
[ -d "${TRANSLATION_DIR}" ] || die "找不到 GUI 翻译目录：${TRANSLATION_DIR}"
command -v msgfmt >/dev/null || die "找不到 msgfmt，无法安装 GUI 翻译。"

export PATH="${USER_HOME}/.local/bin:${PATH}"

if ! command -v blueprint-compiler >/dev/null; then
    python3 -m pip install --user --break-system-packages \
        'blueprint-compiler>=0.19'
fi

if [ -x /usr/bin/meson ]; then
    # Use the system Meson for both the unprivileged build and the privileged
    # install. sudo must load the same Meson version as the one that created
    # meson-private/build.dat.
    MESON_BIN=/usr/bin/meson
else
    if ! command -v meson >/dev/null; then
        python3 -m pip install --user --break-system-packages 'meson>=1.0'
    fi
    MESON_BIN="$(command -v meson)"
fi
command -v ninja >/dev/null || sudo dnf5 install -y ninja-build

if [ -f "${SOURCE_RPM}" ]; then
    sudo dnf5 builddep --srpm "${SOURCE_RPM}"
else
    echo "未找到 Fedora 源码包，尝试直接安装 GNOME Control Center 的构建依赖。"
    sudo dnf5 install -y \
        gcc gettext libxslt desktop-file-utils \
        gtk4-devel libadwaita-devel gnome-desktop4-devel \
        gnome-settings-daemon-devel gnome-online-accounts-devel \
        gsettings-desktop-schemas-devel
fi

if ! grep -q 'SENSEL_HAPTIC_HELPER' "${SOURCE_DIR}/panels/mouse/cc-mouse-panel.c"; then
    patch -p1 -d "${SOURCE_DIR}" < "${PATCH_FILE}"
fi

MESON_OPTIONS=(
    --prefix=/usr
    --buildtype=release
    -Dtests=false
    -Ddocumentation=false
    -Dmalcontent=false
    -Dlocation-services=disabled
    -Dibus=false
    -Dsnap=false
)

if [ -f "${BUILD_DIR}/build.ninja" ]; then
    if ! "${MESON_BIN}" setup --reconfigure "${BUILD_DIR}" "${SOURCE_DIR}" "${MESON_OPTIONS[@]}"; then
        STALE_BUILD_DIR="${BUILD_DIR}.stale-$(date +%Y%m%d%H%M%S)"
        echo "构建目录与当前 Meson 版本不兼容，保留旧目录并重新配置：${STALE_BUILD_DIR}"
        mv "${BUILD_DIR}" "${STALE_BUILD_DIR}"
        "${MESON_BIN}" setup "${BUILD_DIR}" "${SOURCE_DIR}" "${MESON_OPTIONS[@]}"
    fi
else
    "${MESON_BIN}" setup "${BUILD_DIR}" "${SOURCE_DIR}" "${MESON_OPTIONS[@]}"
fi

"${MESON_BIN}" compile -C "${BUILD_DIR}"

echo "即将把修改后的 GNOME Settings 安装到系统。原 Fedora RPM 不会从数据库中删除；需要回滚时可执行："
echo "  sudo dnf5 reinstall gnome-control-center"
read -r -p "继续安装？[y/N] " answer
case "${answer}" in
    y|Y|yes|YES) ;;
    *) echo "已完成构建，未安装到系统。构建目录：${BUILD_DIR}"; exit 0 ;;
esac

sudo install -d -m 0755 /usr/local/libexec
sudo install -d -m 0755 /usr/local/bin
sudo install -d -m 0755 /usr/share/applications
sudo install -d -m 0755 /etc/polkit-1/rules.d
sudo install -o root -g root -m 0755 "${HELPER_FILE}" /usr/local/libexec/sensel-haptic-set
sudo install -o root -g root -m 0755 "${DAEMON_FILE}" /usr/local/libexec/sensel-haptic-daemon
sudo install -o root -g root -m 0644 "${POLKIT_RULE_FILE}" /etc/polkit-1/rules.d/49-sensel-haptic.rules
sudo install -o root -g root -m 0755 "${GUI_FILE}" /usr/local/bin/sensel-haptic-control
sudo install -o root -g root -m 0644 "${GUI_DESKTOP_FILE}" /usr/share/applications/sensel-haptic-control.desktop
while IFS= read -r -d '' po_file; do
    language="$(basename "$(dirname "$(dirname "${po_file}")")")"
    sudo install -d -m 0755 "/usr/share/locale/${language}/LC_MESSAGES"
    sudo msgfmt --check --check-format \
        -o "/usr/share/locale/${language}/LC_MESSAGES/${TRANSLATION_DOMAIN}.mo" \
        "${po_file}"
done < <(find "${TRANSLATION_DIR}" -type f \
    -path "*/LC_MESSAGES/${TRANSLATION_DOMAIN}.po" -print0)
sudo "${MESON_BIN}" install -C "${BUILD_DIR}"
sudo update-desktop-database /usr/share/applications 2>/dev/null || true

echo
echo "安装完成。请关闭并重新打开“设置”，进入“鼠标/触控板”，即可看到 Sensel Haptic Touchpad。"
echo "独立控制面板也已安装，可从应用菜单打开“Sensel Haptic Touchpad”，或运行： sensel-haptic-control"
echo "如果面板仍是旧版本，请先执行： pkill -x gnome-control-center（会关闭当前设置窗口）。"
