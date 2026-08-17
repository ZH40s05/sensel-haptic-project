# Sensel 触觉触摸板工具 / Sensel Haptic Touchpad Tools

面向部分 ThinkPad 机型所搭载 Sensel 触觉触摸板（haptic touchpad）的社区工具，
提供免安装的 WebHID 网页面板、独立 Tk 控制面板，以及可选的 Fedora GNOME
设置集成。

A community toolkit for the Sensel haptic touchpad found in selected ThinkPad
systems, providing a no-install WebHID web panel, a standalone Tk control panel,
and an optional Fedora GNOME Settings integration.

> 本项目写入 Sensel 私有 HID 寄存器，属于实验性硬件集成软件，不是 Sensel 或
> GNOME 的官方发布。
>
> This project writes private Sensel HID registers. It is experimental hardware
> integration software, not an official Sensel or GNOME release.

## 功能 / Features

- 读取和调节触觉反馈强度（1–10 档，非线性映射）。
- 调节主点击和 TrackPoint 按钮的按下力度，并按 5%–100% 比值调节释放力度。
- 启用或禁用 TrackPoint 按钮。
- 草稿式编辑：改动先写入 RAM 即时预览，统一使用“保存/取消/重置”，避免每次
  调节都写 flash。
- 提供无需安装的单文件 WebHID 面板，以及独立 Tk 面板和可选 GNOME 设置集成。
- 独立 GUI 与 GNOME 设置共用 root helper；寄存器校验和设备识别在特权边界内完成。
- 附带简体中文与繁体中文翻译。

- Read and adjust haptic feedback intensity with 10 non-linear levels.
- Adjust main and TrackPoint press force, plus release force as a 5%–100% ratio.
- Enable or disable TrackPoint buttons.
- Preview changes in RAM and use global Save / Cancel / Reset controls instead of
  writing flash for every adjustment.
- Provide a no-install single-file WebHID panel, a standalone Tk panel, and an
  optional GNOME Settings integration.
- The desktop entries share a root-owned helper; register validation and device
  identification stay inside the privileged boundary.
- Simplified and Traditional Chinese translations are included.

## 支持环境 / Supported environment

当前已验证的目标是 Fedora GNOME、GNOME Control Center 50.0 源码结构，以及以
VID/PID `2C2F:0028` 和 `SNSL0028` 路径暴露的 Sensel HID 设备。其他设备不保证兼容；
详细矩阵和验证状态见 [兼容性说明 / compatibility guide](docs/compatibility.md)。

The validated target is Fedora GNOME, the GNOME Control Center 50.0 source layout,
and a Sensel HID device exposed as VID/PID `2C2F:0028` with an `SNSL0028` path.
Other devices are not guaranteed; see the [compatibility guide](docs/compatibility.md)
for the support matrix and validation status.

独立控制面板需要 / The standalone panel needs:

- Python 3.9 或以上 / Python 3.9 or newer；
- Tk；
- gettext 运行时 / gettext runtime support；
- sudo、pkexec 与 Polkit（特权写入）/ sudo, pkexec, and Polkit for privileged writes。

GNOME 设置构建另需 Fedora GNOME 开发包、Meson、Ninja、Blueprint Compiler 和可用
的 C 编译器。安装脚本可以安装已知的 Fedora 构建依赖，但精确的包集合取决于所装
Fedora 版本。

The GNOME Settings build additionally needs Fedora GNOME development packages,
Meson, Ninja, Blueprint Compiler, and a working C compiler. The installer can
install known Fedora build dependencies, but the exact package set depends on the
Fedora release.

## 安装 / Installation

### WebHID 跨平台面板（推荐，无需安装）/ WebHID panel (recommended, no install)

打开 [在线版 / live panel](https://zh40s05.github.io/sensel-haptic-project/)，或
直接打开 `tools/sensel-haptic-web.html`。使用 Chrome、Edge 或 Opera；Linux 用户
首次使用前需安装仓库中的 udev 规则。完整步骤、权限说明和故障排查见
[WebHID 使用说明 / WebHID guide](docs/webhid.md)。

Open the [live panel](https://zh40s05.github.io/sensel-haptic-project/) or open
`tools/sensel-haptic-web.html` directly. Use Chrome, Edge, or Opera; Linux users
must install the shipped udev rule first. See the [WebHID guide](docs/webhid.md)
for setup, permissions, and troubleshooting.

### 独立控制面板 / Standalone control panel

在仓库根目录运行 / Run from the repository root:

    ./install-sensel-haptic-gui.sh

安装脚本会安装 helper、daemon、Polkit 规则、桌面启动器与翻译目录，不需要构建
GNOME Control Center。

The installer installs the helper, daemon, Polkit rule, desktop launcher, and
translation catalogs. It does not require building GNOME Control Center.

### GNOME 设置集成 / GNOME Settings integration

运行 / Run:

    ./install-sensel-gnome-settings.sh

若本地没有 GNOME 源码树，脚本会下载 GNOME Control Center 50.0 源码包、校验
SHA-256、应用补丁并构建；安装修改过的 GNOME Settings 二进制前会请求确认。

If no local GNOME source tree is available, the script downloads GNOME Control Center
50.0, verifies its SHA-256 checksum, applies the patch, and builds it. It asks for
confirmation before installing the modified GNOME Settings binary.

可用覆盖变量 / Useful overrides:

    SENSEL_GNOME_SOURCE_DIR=/path/to/gnome-control-center-50.0 ./install-sensel-gnome-settings.sh
    SENSEL_GNOME_SOURCE_ARCHIVE=/path/to/gnome-control-center-50.0.tar.xz ./install-sensel-gnome-settings.sh
    SENSEL_GNOME_BUILD_DIR=/path/to/build ./install-sensel-gnome-settings.sh

对另一个经本地审查的源码包，可用 `SENSEL_GNOME_SOURCE_SHA256` 覆盖校验和；
仅当该包已通过其他方式可信验证时才可设为空值。

For a different locally reviewed source archive, override the checksum with
`SENSEL_GNOME_SOURCE_SHA256`. Leave it empty only when the archive is trusted and
verified by another method.

测试后恢复发行版 GNOME 设置包 / To restore the distribution package:

    sudo dnf5 reinstall gnome-control-center

## 安全与设备访问 / Safety and device access

桌面 helper 以 root 运行，因为 Sensel 寄存器接口经由 hidraw 暴露。它会校验
设备和取值、串行化访问，并对适用的写入执行验证。私有寄存器可能改变触摸板行为；
首次实验前请记录当前值。WebHID 不安装 root helper，但浏览器设备选择器和系统
HID 权限仍是安全边界。

The desktop helper runs as root because the Sensel register interface is exposed
through hidraw. It validates devices and values, serializes access, and verifies
applicable writes. Private registers may change touchpad behavior; record current
values before experimenting. WebHID does not install a root helper, but the browser
device picker and OS HID permissions remain its security boundary.

安装脚本会修改 `/usr/local`、`/usr/share` 和 `/etc/polkit-1` 下的系统文件。共享
机器或生产工作站请先审查安装内容；安全报告流程见 [安全策略 / security policy]
(SECURITY.md)。

The installers modify system files under `/usr/local`, `/usr/share`, and
`/etc/polkit-1`. Review the installed files before using them on a shared or
production workstation; see [the security policy](SECURITY.md) for reporting.

## 仓库结构 / Repository layout

    install-sensel-haptic-gui.sh       独立面板安装脚本 / standalone panel installer
    install-sensel-gnome-settings.sh   GNOME 设置构建与安装 / GNOME Settings installer
    scripts/                           root helper、daemon 与 Polkit 规则 / helper and rule
    tools/                             GUI、WebHID、诊断工具与图标 / GUI, WebHID, tools, icons
    patches/                           GNOME Control Center 补丁 / GNOME patch
    locale/                            Gettext 翻译源 / translation sources
    docs/                              架构、兼容性、WebHID 与协议说明 / guides and notes
    tests/                             硬件无关检查与单元测试 / checks and unit tests

本地源码、artifacts、构建目录、源码包、RPM、生成的翻译目录和 Windows 应用文件
均被 `.gitignore` 排除，不属于公开检出内容。

Local source, artifacts, build directories, source archives, RPMs, generated
catalogs, and Windows application files are excluded by `.gitignore` and are not
part of a public checkout.

## 开发与文档 / Development and documentation

提交改动前先运行硬件无关检查 / Run the hardware-independent checks before submitting:

    ./tests/check.sh

检查覆盖 shell、Python、协议行为、翻译目录和桌面入口（需相应验证工具已安装），
不访问硬件，也不执行寄存器写入。

The checks cover shell, Python, protocol behavior, translation catalogs, and the
desktop entry when the corresponding tools are installed. They do not access
hardware or perform register writes.

更多信息 / More information:

- [WebHID 使用说明 / WebHID guide](docs/webhid.md)
- [架构 / Architecture](docs/architecture.md)
- [兼容性与限制 / Compatibility and limitations](docs/compatibility.md)
- [Windows 逆向笔记 / Reverse-engineering notes](docs/sensel-windows-reverse-engineering.md)
- [上游化计划 / Upstreaming plan](docs/upstreaming.md)
- [更新日志 / Changelog](CHANGELOG.md)
- [贡献指南 / Contributing](CONTRIBUTING.md)
- [安全策略 / Security policy](SECURITY.md)

GNOME 补丁当前基于上游 50.0 源码结构；更新 GNOME 时应重新审查补丁、构建结果、
兼容性说明和源码校验和。

The GNOME patch targets the upstream 50.0 source layout. When updating GNOME,
review the patch, build result, compatibility notes, and source checksum together.

## 翻译 / Translations

翻译源位于 `locale/`，生成模板和测试变量见
[locale/README.md](locale/README.md)。英文为回退语言。

Translation sources live under `locale/`; see [locale/README.md](locale/README.md)
for template generation and test variables. English is the fallback language.

## 逆向工程与许可 / Reverse engineering and license

寄存器映射与 HID 帧格式记录在
[Windows 逆向笔记 / reverse-engineering notes](docs/sensel-windows-reverse-engineering.md)。
本仓库不分发专有 Windows 应用及其运行时文件。

The [reverse-engineering notes](docs/sensel-windows-reverse-engineering.md) record
the register map and HID framing used by the implementation. Proprietary Windows
applications and runtime files are not redistributed.

原创项目代码以 GPL-2.0-or-later 授权，见 LICENSE。GNOME Control Center 与其他
上游组件保留各自的许可声明；公开仓库边界与商标说明见 NOTICE.md。

Original project code is licensed under GPL-2.0-or-later; see LICENSE. GNOME
Control Center and other upstream components retain their own license notices.
See NOTICE.md for repository-boundary and trademark information.
