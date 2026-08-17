# 架构 / Architecture

本项目是面向一族 Sensel 触觉触摸板的用户态集成。它与 Linux 内核输入路径
刻意分离：libinput 与内核继续负责指针、手势和按键事件，本项目仅通过
Sensel HID 寄存器管道修改设备设置。

The project is a userspace integration for one family of Sensel haptic
touchpads. It is deliberately separate from the Linux kernel input path:
libinput and the kernel continue to deliver pointer, gesture, and button
events, while this project changes device settings through the Sensel HID
register pipe.

```mermaid
flowchart LR
    gui[Standalone Tk control panel]
    settings[Patched GNOME Settings panel]
    auth[pkexec and Polkit]
    helper[Root-owned sensel-haptic-set]
    daemon[sensel-haptic-daemon]
    hid[/dev/hidrawN]
    device[Sensel haptic touchpad]

    gui --> auth
    settings --> auth
    auth --> helper
    helper --> daemon
    daemon --> hid
    hid --> device
```

## 组件 / Components

### `scripts/sensel-haptic-daemon`

特权协议实现。它校验 hidraw 路径、检查 Sensel sysfs 身份、用锁文件串行化
访问、组帧 21 字节报告 ID `0x09` 的 HID 报告、校验响应校验和，并对重要
写入执行读回验证。

This is the privileged protocol implementation. It validates the hidraw
path, checks the Sensel sysfs identity, serializes access with a lock file,
frames 21-byte report-ID `0x09` HID reports, checks response checksums, and
verifies important writes by reading the registers back.

daemon 同时持有面向用户的寄存器操作 / The daemon also owns the
user-facing register operations:

- 触觉强度 / haptic intensity；
- 主点击力度（按下/释放比值可调）/ main click force with an adjustable
  release ratio；
- TrackPoint 按钮点击力度 / TrackPoint button click force；
- TrackPoint 按钮启用 / TrackPoint button enablement；
- 通过 Sensel `UserSetting` 寄存器持久化 / persistence through the
  Sensel `UserSetting` register。

固件约束：每次保存 UserSetting 后，固件把整块用户设置从 flash 重载回
RAM，约 2.6 秒内寄存器管道不应答（flash 忙窗口）。因此写入路径带有
OSError/TimeoutError 重试，GUI 的草稿模型把预览（只写 RAM）与提交
（逐寄存器 写→保存）分开。

Firmware constraint: after each UserSetting save the firmware reloads the
whole user-setting block from flash and stops answering the register pipe
for roughly 2.6 seconds (the flash-busy window). Write paths therefore
retry on OSError/TimeoutError, and the GUI draft model separates preview
(RAM-only) from commit (per-register write-then-save).

### `scripts/sensel-haptic-set`

Polkit 使用的窄命令分发器。它在把操作交给 daemon 前拒绝意外参数。把这层
校验放在特权边界很重要，因为 GUI 输入不能被当作可信输入。

This is the narrow command dispatcher used by Polkit. It rejects unexpected
arguments before handing an operation to the daemon. Keeping this
validation at the privileged boundary is important because GUI input must
not be treated as trusted.

### `tools/sensel_haptic_gui.py`

独立面板是 Tk 应用。它发现匹配的 hidraw 节点、通过 `pkexec` 调用
helper、异步执行操作，保证设备查询期间界面不阻塞。编辑采用草稿模型：
改动即时预览到 RAM，全局"保存/取消/重置"管理未持久化的更改。

The standalone panel is a Tk application. It discovers matching hidraw
nodes, uses `pkexec` to invoke the helper, and performs operations
asynchronously so the UI remains responsive while the device is being
queried. Editing uses a draft model: changes preview to RAM immediately,
and global Save / Cancel / Reset manage the unpersisted modifications.

### `patches/sensel-gnome-control-center.patch`

可选补丁，向 GNOME Control Center 鼠标面板加入 Sensel 专属行。它是发行
版集成层，不是通用 GNOME 或 libinput API。补丁当前面向 GNOME Control
Center 50.0 源码结构，上游面板变化时必须 rebase。

This optional patch adds Sensel-specific rows to the GNOME Control Center
mouse panel. It is a distribution integration layer, not a generic GNOME or
libinput API. The patch currently targets the GNOME Control Center 50.0
source layout and therefore must be rebased whenever the upstream panel
changes.

### `tools/sensel-hid-pipe.py`

开发者诊断工具。暴露原始寄存器读取与显式选择加入的写入，用于协议调查。
不应作为日常桌面配置入口。

This is a developer diagnostic tool. It exposes raw register reads and
explicitly opt-in writes for protocol investigation. It should not be used
as the normal desktop configuration entry point.

## 特权边界 / Privilege boundary

GUI 与 GNOME 面板无特权。正常配置路径只在 helper 与 daemon 中打开
hidraw 节点。诊断工具也能打开它，但只作为显式调用的开发者操作。Polkit
规则授权本地活跃 `wheel` 用户调用已安装的 helper；helper 自身仍校验设
备、操作与取值。

The GUI and GNOME panel are unprivileged. The normal configuration path
opens the hidraw node only in the helper and daemon. The diagnostic tool
can also open it, but only as an explicitly invoked developer operation.
The Polkit rule grants the active local `wheel` user permission to invoke
the installed helper; the helper still validates the device, operation, and
value itself.

本项目不试图替代 libinput 或内核驱动。可上游化的未来设计会把这一设备
专属后端与通用指针事件处理分开，向桌面设置暴露稳定的系统 API，而不是
把私有寄存器访问嵌入桌面面板。

The project does not attempt to replace libinput or the kernel driver. A
future upstreamable design would keep this device-specific backend separate
from generic pointer-event handling and would expose a stable system API to
desktop settings instead of embedding private register access in a desktop
panel.
