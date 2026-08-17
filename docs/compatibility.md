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

文档化桌面目标是 Fedora GNOME（GNOME Control Center 50.0 源码结构）。
独立面板不依赖 GNOME Control Center，但仍要求 Python 3.9+、Tk、
`pkexec` 与 Polkit。

The documented desktop target is Fedora GNOME with the GNOME Control Center
50.0 source layout. The standalone panel is independent of GNOME Control
Center, but still expects Python 3.9 or newer, Tk, `pkexec`, and Polkit.

## 验证层级 / Validation levels

| 领域 / Area | 状态 / Current status |
| --- | --- |
| 协议帧与范围校验 / Protocol framing and range checks | 硬件无关单元测试覆盖 / hardware-independent unit tests |
| Shell、Python、翻译、桌面入口 / Shell, Python, translations, desktop entry | 装有可选工具时由 `tests/check.sh` 覆盖 / covered by `tests/check.sh` |
| 独立面板 / Standalone panel | 在目标设备上手动验证 / validated manually on the target device |
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
