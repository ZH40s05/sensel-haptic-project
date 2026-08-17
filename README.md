# Sensel 触觉触摸板 GNOME 集成 / Sensel Haptic Touchpad for GNOME

面向部分 ThinkPad 机型所搭载 Sensel 触觉触摸板（haptic touchpad）的社区集成项目，
提供独立 Tk 控制面板，以及可选的 Fedora GNOME 设置集成。

A community integration for the Sensel haptic touchpad found in selected
ThinkPad systems, providing a standalone Tk control panel and an optional
GNOME Settings integration for Fedora.

> 本项目写入 Sensel 私有 HID 寄存器，属于实验性硬件集成软件，
> 不是 Sensel 或 GNOME 的官方发布。
>
> This project writes private Sensel HID registers. It is experimental
> hardware integration software, not an official Sensel or GNOME release.

## 功能 / Features

- 读取和调节触觉反馈强度（1–10 档，非线性映射）。
- 调节主点击按下力度与 TrackPoint 按钮点击力度（连续范围，超出 Windows 三档预设）。
- 按比值（5%–100%）调节释放（抬起）触发力度，Windows 固定 65%。
- 启用或禁用 TrackPoint 按钮。
- 草稿式编辑：所有改动先以 RAM 预览即时生效，统一"保存/取消/重置"，避免每次调节都写 flash 造成 2–3 秒卡顿。
- WebHID 单文件网页版（`tools/sensel-haptic-web.html`）：Chromium 系浏览器跨平台直连设备，功能与桌面版一致。
- 独立 GUI 与 GNOME 设置共用同一 root 特权 helper。
- 附带简体中文与繁体中文翻译。
- 寄存器校验与设备识别全部收在特权 helper 内。

- Read and write haptic feedback intensity (10 non-linear levels).
- Adjust main click force and TrackPoint button click force over a
  continuous range beyond the Windows presets.
- Adjust the release (up-register) force as a 5%–100% ratio of the press
  force; Windows hardcodes 65%.
- Enable or disable TrackPoint buttons.
- Draft editing: every change is previewed to RAM instantly, with global
  Save / Cancel / Reset, so adjustments no longer write flash and stall the
  touchpad for 2–3 seconds each time.
- Single-file WebHID web panel (`tools/sensel-haptic-web.html`): talks to
  the device directly from any Chromium browser with feature parity to
  the desktop panel.
- The standalone GUI and GNOME Settings share the same root-owned helper.
- Simplified and Traditional Chinese translations are included.
- Register validation and device identification stay inside the privileged
  helper.

## 支持环境 / Supported environment

已验证目标为 Fedora + GNOME Control Center 50.0，以及识别为 VID/PID
`2C2F:0028` 或 `SNSL` 设备路径的 Sensel HID 设备。

The tested target is Fedora with GNOME Control Center 50.0 and a Sensel HID
device identified by VID/PID 2C2F:0028 or an SNSL device path.

独立控制面板需要 / The standalone panel needs:

- Python 3.9 或以上 / or newer；
- Tk；
- gettext 运行时 / runtime support；
- sudo、pkexec 与 Polkit（特权写入）/ sudo, pkexec, and Polkit for
  privileged writes。

GNOME 设置构建另需 Fedora GNOME 开发包、Meson、Ninja、Blueprint Compiler
和可用的 C 编译器。安装脚本可以安装已知的 Fedora 构建依赖，但精确的包
集合取决于所装 Fedora 版本。

The GNOME Settings build additionally needs the Fedora GNOME development
packages, Meson, Ninja, Blueprint Compiler, and a working C compiler. The
installer can install the known Fedora build dependencies, but the exact
package set depends on the installed Fedora release.

## 安装 / Installation

### WebHID 跨平台面板（推荐，无需安装）/ WebHID cross-platform panel (no install)

用 Chromium 系浏览器（Chrome / Edge / Opera）直接打开
`tools/sensel-haptic-web.html`，点"连接触摸板"即可。无 root、无服务
进程、无依赖；协议在浏览器内直接通过 WebHID 与设备通信。

Open `tools/sensel-haptic-web.html` directly in any Chromium browser
(Chrome / Edge / Opera) and click Connect. No root, no server, no
dependencies; the protocol talks to the device through WebHID in the
browser.

- 功能与桌面版一致：草稿预览、保存/取消/重置、释放比值调节。
- Windows / macOS / ChromeOS 开箱即用；Linux 需先安装 udev 规则
  （见文件头注释）：`sudo cp tools/70-sensel-haptic-webhid.rules
  /etc/udev/rules.d/ && sudo udevadm control --reload && sudo udevadm trigger`。
- Safari 与 Firefox 不支持 WebHID。

- Feature parity with the desktop panel: draft preview, Save/Cancel/
  Reset, release-ratio adjustment.
- Works out of the box on Windows / macOS / ChromeOS; Linux needs the
  udev rule shipped in this repository first.
- Safari and Firefox do not implement WebHID.

### 独立控制面板 / Standalone control panel

在仓库根目录运行 / Run from the repository root:

    ./install-sensel-haptic-gui.sh

安装脚本会把 helper、daemon、Polkit 规则、桌面启动器与翻译目录装入系统
目录，无需构建 GNOME Control Center。

The installer installs the helper, daemon, Polkit rule, desktop launcher,
and translation catalogs under system directories. It does not require
building GNOME Control Center.

### GNOME 设置集成 / GNOME Settings integration

运行 / Run:

    ./install-sensel-gnome-settings.sh

若本地没有 GNOME 源码树，安装脚本会从 download.gnome.org 下载 GNOME
Control Center 50.0 源码包，校验 SHA-256，解压到（被 .gitignore 忽略的）
构建目录，应用补丁并构建。安装修改过的 GNOME 设置二进制前会请求确认。

If a local GNOME source tree is not available, the installer downloads the
GNOME Control Center 50.0 source archive from download.gnome.org, verifies
its SHA-256 checksum, extracts it under the ignored build directory, applies
the patch, and builds it. The script asks for confirmation before installing
the modified GNOME Settings binary.

可用覆盖变量 / Useful overrides:

    SENSEL_GNOME_SOURCE_DIR=/path/to/gnome-control-center-50.0 ./install-sensel-gnome-settings.sh
    SENSEL_GNOME_SOURCE_ARCHIVE=/path/to/gnome-control-center-50.0.tar.xz ./install-sensel-gnome-settings.sh
    SENSEL_GNOME_BUILD_DIR=/path/to/build ./install-sensel-gnome-settings.sh

对另一个经本地审查的源码包，可用 `SENSEL_GNOME_SOURCE_SHA256` 覆盖校验
和。仅当该包已通过其他方式可信验证时才可设为空值。

The source checksum can be overridden for a different, locally reviewed
source archive with SENSEL_GNOME_SOURCE_SHA256. Set it to an empty value
only when the archive is trusted and verified by another method.

测试后恢复发行版 GNOME 设置包 / To restore the distribution package:

    sudo dnf5 reinstall gnome-control-center

## 安全与设备访问 / Safety and device access

helper 以 root 运行，因为 Sensel HID 寄存器接口经由 hidraw 暴露。它会
拒绝意外路径与非 Sensel 设备、校验全部取值、用锁文件串行化访问，并在
写入后读回验证。

The helper runs as root because the Sensel HID register interface is exposed
through hidraw. It rejects unexpected paths and non-Sensel devices, validates
all values, serializes access with a lock file, and checks write readback.

Polkit 规则授权本地活跃的 wheel 组用户仅调用已安装的 helper。在共享机器
上安装前请审查该策略。私有寄存器写入可能改变触摸板手感或行为；实验前
请先记录当前值。

The Polkit rule grants the local active wheel group permission to invoke
only the installed helper. Review this policy before installing it on a
shared machine. Private register writes can change the feel or behavior of
the touchpad; record current values before experimenting.

安装脚本修改 `/usr/local`、`/usr/share` 与 `/etc/polkit-1` 下的系统文件，
面向用户能够审查并回退这些改动的 Fedora 系统。

The install scripts modify system files under /usr/local, /usr/share, and
/etc/polkit-1. They are intended for Fedora systems where the user can
review and revert those changes.

## 仓库结构 / Repository layout

    install-sensel-haptic-gui.sh       独立面板安装脚本 / Standalone panel installer
    install-sensel-gnome-settings.sh   GNOME 设置构建与安装 / Build and installer
    scripts/                           root helper、daemon 与 Polkit 规则 / helper, daemon, Polkit rule
    tools/                             GUI、HID 诊断工具与启动器 / GUI, diagnostic tool, launcher
    patches/                           GNOME Control Center 补丁 / patch
    locale/                            Gettext 翻译源 / translation sources
    docs/                              架构、协议与项目说明 / architecture, protocol, notes
    tests/                             硬件无关检查与单元测试 / checks and unit tests

本地源码、artifacts、构建目录、源码包、RPM、生成的翻译目录与 Windows
应用文件均被 .gitignore 刻意排除。它们可以存在于工作副本中用于调查，
但不属于公开检出的一部分。

The local source, artifacts, build directories, source archives, RPMs,
generated catalogs, and Windows application files are deliberately excluded
by .gitignore. They may exist in a working copy for investigation, but they
are not part of a public checkout.

## 开发与检查 / Development and checks

提交改动前先运行硬件无关检查 / Run the hardware-independent checks before
submitting changes:

    ./tests/check.sh

检查覆盖 shell 语法、Python 语法、协议行为、gettext 目录与桌面入口
（需相应验证工具已安装）。检查不访问硬件、不执行寄存器写入。

The checks cover shell syntax, Python syntax, protocol behavior, gettext
catalogs, and the desktop entry when the corresponding validation tools are
installed. They do not access hardware or perform register writes.

更多信息 / More information:

- [架构 / Architecture](docs/architecture.md)
- [兼容性与限制 / Compatibility and limitations](docs/compatibility.md)
- [上游化计划 / Upstreaming plan](docs/upstreaming.md)
- [Windows 逆向笔记 / Reverse-engineering notes](docs/sensel-windows-reverse-engineering.md)

GNOME 补丁基于上游 50.0 源码结构。更新 GNOME 时，先取得干净的上游源码
树，rebase 或重新生成补丁、本地构建，并同步更新文档中的校验和与兼容性
说明。

The GNOME patch is based on the upstream 50.0 source layout. When updating
GNOME, first obtain a clean upstream source tree, rebase or regenerate the
patch, build it locally, and update the documented checksum and
compatibility notes together.

## 翻译 / Translations

翻译源位于 locale 目录。从 GUI 生成模板 / To generate a template:

    xgettext --language=Python --from-code=UTF-8 --keyword=_ --output=locale/sensel-haptic-control.pot tools/sensel_haptic_gui.py

英文为回退语言。`SENSEL_HAPTIC_LOCALE` 与 `SENSEL_HAPTIC_LOCALEDIR` 可用
于在未安装到系统的情况下测试指定目录。

English is the fallback language. SENSEL_HAPTIC_LOCALE and
SENSEL_HAPTIC_LOCALEDIR can be used to test a specific catalog without
installing it system-wide.

## 逆向工程笔记 / Reverse-engineering notes

[docs/sensel-windows-reverse-engineering.md](docs/sensel-windows-reverse-engineering.md)
记录了实现所用的寄存器映射与 HID 帧格式。本仓库不再分发专有 Windows
应用及其运行时文件。

That document records the register mapping and HID framing used by the
implementation. The proprietary Windows application and its runtime files
are not redistributed by this repository.

## 许可 / License

原创项目代码以 GPL-2.0-or-later 授权，见 LICENSE。GNOME Control Center
与其他上游组件保留各自的许可声明。公开仓库边界与商标说明见 NOTICE.md。

Original project code is licensed under GPL-2.0-or-later; see LICENSE.
GNOME Control Center and other upstream components retain their own license
notices. See NOTICE.md for the public-repository boundary and trademark
note.
