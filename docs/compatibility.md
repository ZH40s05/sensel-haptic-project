# 兼容性与限制 / Compatibility and limitations

本项目对设备匹配刻意保守。仅凭 Sensel 品牌名不足以确认协议兼容：实现依
赖特定的 HID 报告布局与私有寄存器映射。

This project is intentionally conservative about device matching. A Sensel
brand name alone is not sufficient to establish protocol compatibility: the
implementation relies on a particular HID report layout and private register
map.

## 已知目标 / Known target

当前已验证的目标是以如下方式暴露的 Sensel 触觉触摸板 / The currently
validated target is the Sensel haptic touchpad exposed as:

- USB 标识 `2C2F:0028` / USB identity `2C2F:0028`；
- `SNSL0028` 的 hidraw/sysfs 路径 / an `SNSL0028` hidraw/sysfs path；
- Linux `/dev/hidrawN` 字符设备 / a Linux `/dev/hidrawN` character
  device。

桌面集成目标是 Fedora GNOME 与 GNOME Control Center 50.0 源码结构；安装依赖
见 [README](../README.md)。

The desktop integration targets Fedora GNOME and the GNOME Control Center 50.0
source layout; see the [README](../README.md) for installation dependencies.

### 浏览器（WebHID 面板）/ Browsers (WebHID panel)

WebHID 面板依赖浏览器的 WebHID 实现。当前支持矩阵 /
The WebHID panel depends on the browser's WebHID implementation.
Current support matrix:

| 平台 / Platform | Chrome | Edge | Opera | Firefox | Safari |
| --- | --- | --- | --- | --- | --- |
| Windows | ✅ | ✅（151 实测 / verified） | ✅ | ❌ | ❌ |
| macOS | ✅ | ✅ | ✅ | ❌ | ❌ |
| Linux | ✅*（需 udev 规则 / needs udev rule） | ✅* | ✅* | ❌ | ❌ |
| ChromeOS | ✅ | — | — | ❌ | ❌ |

Firefox 与 Safari 未实现 WebHID，无替代开关。Linux 上的额外要求见
`tools/70-sensel-haptic-webhid.rules` 头部注释。

Firefox and Safari do not implement WebHID and offer no flag to enable
it. For the additional Linux requirement see the header of
`tools/70-sensel-haptic-webhid.rules`.

## 验证层级 / Validation levels

| 领域 / Area | 状态 / Current status |
| --- | --- |
| 协议帧与范围校验 / Protocol framing and range checks | 硬件无关单元测试覆盖（Python + WebHID/Node 双套）/ hardware-independent unit tests (Python + WebHID/Node) |
| Shell、Python、翻译、桌面入口 / Shell, Python, translations, desktop entry | 装有可选工具时由 `tests/check.sh` 覆盖 / covered by `tests/check.sh` |
| 独立面板 / Standalone panel | 在目标设备上手动验证 / validated manually on the target device |
| WebHID 面板 / WebHID panel | 假固件协议测试全覆盖；Edge 151 页面加载与 WebHID 检测实测；真机连线待用户在 Chromium 中确认 / fake-firmware protocol tests; page load + WebHID detection verified on Edge 151; live device pairing pending user confirmation |
| GNOME 设置补丁 / GNOME Settings patch | 对照文档化 GNOME 50.0 源码结构验证 / validated against the documented layout |
| 其他 Sensel 触摸板 / Other Sensel touchpads | 不保证；需兼容性报告 / not guaranteed; requires a report |
| 挂起恢复、多设备、固件升级 / Suspend/resume, multiple devices, firmware upgrades | 无自动化测试覆盖 / not covered by automated tests |

## 提交兼容性报告 / Adding a compatibility report

为另一设备提议支持前，请记录 / Please record the following before
proposing support for another device:

1. 笔记本与触摸板具体型号 / exact laptop and touchpad model；
2. 内核与发行版版本 / kernel and distribution versions；
3. GNOME/KDE 或其他桌面版本 / GNOME/KDE or other desktop version；
4. 固件版本（如有）/ firmware version, if available；
5. 解析后的 `/sys/class/hidraw/hidrawN` 路径 / the resolved path；
6. 只读寄存器观察 / read-only register observations；
7. 设置是否在重启与挂起恢复后保留 / whether settings survive reboot
   and suspend/resume。

在理解寄存器映射与安全回滚流程之前，不要在不熟悉的设备上测试写入。

Do not test writes on an unfamiliar device until the register map and safe
rollback procedure are understood.
