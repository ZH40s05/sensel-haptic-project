# Sensel Windows 控制面板逆向结果 / Sensel Windows panel reverse engineering

分析对象是 Windows 分区中的 Sensel Haptic Touchpad 1.2.12.0。逆向过程中
使用的完整应用包仅保留在本地工作目录 artifacts/sensel-windows-app-1.2.12.0/；
该应用及其运行时文件不属于本仓库发布内容。

The analysis target is the Sensel Haptic Touchpad 1.2.12.0 application from
the Windows partition. The complete application package used during
reverse engineering is kept only in the local working directory; the
application and its runtime files are not part of this repository.

## 结论 / Summary

Windows 控制面板没有调用一个独立的"触发力度 API"。它通过
`SenselSerialDevice` 的 HID 管道读写 Sensel 内部寄存器：

The Windows panel does not call a separate "trigger force API". It reads
and writes Sensel internal registers through the `SenselSerialDevice` HID
pipe:

| 设置 / Setting | 寄存器 / Register | 单位/范围 / Unit |
| --- | ---: | --- |
| 主点击按下力度 / main press force | `0x0038` | `Gf / 2`，8 位 / 8-bit |
| 主点击释放力度 / main release force | `0x0090` | `Gf / 2`，8 位 / 8-bit |
| 3HB 左按下/释放 / left press/release | `0x0091` / `0x0092` | Windows TrackPoint 档位寄存器值 / level register value |
| 3HB 右按下/释放 / right press/release | `0x0093` / `0x0094` | 同上 / same |
| 3HB 中按下/释放 / middle press/release | `0x0095` / `0x0096` | 同上 / same |
| TrackPoint 按钮模式 / button mode | `0x008A` | `0` / `1` |
| 触觉反馈强度 / haptic intensity | `0x00AB` | `0..100` |

主点击力度的控制面板逻辑是 / The main click force logic is:

```text
down = selected_gf / 2                 // 整数除法 / integer division
up   = round(down * 0.65)
write 0x0038 = down
write 0x0090 = up
save each register as UserSetting
```

当前版本的三个主点击选项为 `120`、`164`、`190` Gf，对应寄存器值分别为
`(60,39)`、`(82,53)`、`(95,62)`。

The three main click options are 120/164/190 Gf, mapping to register pairs
(60,39), (82,53), (95,62).

Windows 控制面板的完整可调界面为五项 / The full adjustable UI has five
items:

1. `Haptic Feedback`：开关关闭时把 `0x00AB` 写为 `0`，并保存关闭前的强度；重新开启时恢复保存值，没有保存值则使用 `50`。
2. `Haptics Intensity`：设置界面显示 `1..10` 档非线性强度，底层仍向 `0x00AB` 写入原始字节值
   `[32, 45, 55, 63, 71, 77, 84, 89, 95, 100]`；独立的 `Haptic Feedback` 开关关闭时写入 `0`，并保留关闭前的档位。
3. `Click Force`：界面显示 `Low / Medium / High` 三档，底层对应 `120 / 164 / 190 Gf`，写入 `0x0038` 和 `0x0090`。
4. `Enable TrackPoint Buttons`：写入 `ptp_buttons_config`（`0x008A`）的 `0/1`。
5. `TrackPoint Click Force`：界面显示 `Low / Medium / High` 三档，底层对应 `28 / 38 / 60` 三档寄存器值；同一个选项同时写入 3HB 左、右、中三个区域的按下/释放寄存器。

3HB 的写入逻辑与主点击不同：Windows 直接把所选档位写入三个按下寄存器，即
`down = selected_level`；释放寄存器写入 `up = round(down * 0.65)`，然后依次保存六个寄存器。
初始化时 Windows 读取按下寄存器，并将其乘以 2 后按 `56`、`76` 阈值选择三档，等价于原始寄存器值
`<=28` 为低档、`<=38` 为中档、`>38` 为高档。

For 3HB Windows writes the selected level directly to the three down
registers and `round(down * 0.65)` to the three up registers, saving all
six. 65% is hardcoded in Windows; this project exposes it as an adjustable
5..100 percent ratio.

## HID 管道帧 / HID pipe framing

设备 VID/PID 是 `0x2C2F:0x0028`，Windows 程序使用 HID 报告 ID `9`。每个 HID 报告固定 21 字节：

The device VID/PID is `0x2C2F:0x0028` and the Windows program uses HID
report ID 9. Each report is a fixed 21 bytes:

```text
[0]    09                         报告 ID / report ID
[1]    N                          有效数据长度，最多 19 / payload length, max 19
[2:]   N 字节协议数据 / N bytes of protocol data
其余   0                          填充到 21 字节 / zero padding to 21
```

内部寄存器命令为 / The register command is:

```text
command[0] = ((address & 0x3f00) >> 7) | 0x01 | (0x80 if read else 0)
command[1] = address & 0xff
command[2] = size
```

普通写寄存器发送 / A register write sends:

```text
[command[0], command[1], size, data..., sum(data) & 0xff]
```

读寄存器返回的数据依次为 / A register read returns:

```text
[read_ack, status, size_u16_le, data..., sum(data) & 0xff]
```

普通写返回 `[write_ack, status]`；ACK 值分别是 `0x01` 和 `0x05`。保存用户设置时，Windows 程序向 `0x0230` 写入 `<address:u16><0x4000:u16><0x51>`。

## 固件持久化行为（实测） / Firmware persistence behavior (measured)

- 写寄存器不持久化（`persist=False`）= 只改 RAM，立即生效，不触发 flash。
- 保存单个 UserSetting 后，固件把整块用户设置从 flash 重载回 RAM，抹掉其他未保存的改动。批量保存必须逐个"写寄存器→保存"。
- 向 `0x0230` 一次写多条 record 只处理第一条。
- 每次保存后约 2.6 秒 flash 忙窗口，期间触摸板无输入、寄存器管道不应答
  （EREMOTEIO 或超时），一次重试即可恢复。

- A non-persisted write changes RAM only: immediate effect, no flash.
- After each UserSetting save the firmware reloads the whole user-setting
  block from flash, discarding other unsaved RAM changes; batch saves must
  interleave write-then-save per register.
- Writing multiple records to `0x0230` in one write only processes the
  first.
- Each save opens a ~2.6 s flash-busy window with no touchpad input and an
  unresponsive register pipe (EREMOTEIO or timeout); one retry recovers.

## 已验证 / Verified

本机当前设备是 `/dev/hidraw1`（`SNSL0028:00`）。只读验证得到 / The local
device is `/dev/hidraw1` (`SNSL0028:00`). Read-only verification:

```text
0x0038 = 0x3c
0x0090 = 0x27
0x0091 = 0x3c
0x0092 = 0x27
0x0093 = 0x3c
0x0094 = 0x27
0x0095 = 0x3c
0x0096 = 0x27
0x00ab = 0x64 (100)
```

工具 `tools/sensel-hid-pipe.py` 默认只做读操作；写入需显式使用 `write`、`set-main-click-force` 或 `set-haptic-intensity`。例如：

```bash
sudo python3 tools/sensel-hid-pipe.py read 0x0038
sudo python3 tools/sensel-hid-pipe.py set-main-click-force 164
sudo python3 tools/sensel-hid-pipe.py set-haptic-intensity 50
```

写入私有寄存器可能影响触摸板的按键行为；建议先记录 `read` 结果，并优先使用 `--no-persist` 做临时测试。

## 当前项目如何使用这些发现 / Current project use

当前 GNOME、Tk 和 WebHID 入口都复用上面的寄存器映射；它们的用户操作、安装
方式和权限模型分别记录在 [README](../README.md)、[架构说明](architecture.md)
和 [WebHID 使用说明](webhid.md) 中。

The GNOME, Tk, and WebHID entry points all reuse the register map above. Their
user workflows, installation, and permission models are documented in the
[README](../README.md), [architecture guide](architecture.md), and
[WebHID guide](webhid.md).

独立 GUI 额外支持 `1..255` 的原始力度值和 5%–100% 释放比值；这些值仍受单字节
寄存器上限约束，超出 Windows 预设范围后应逐步调节并保留可恢复的当前值。

The standalone GUI additionally exposes raw force values from `1..255` and
5%–100% release ratios. The one-byte register limit still applies; values beyond
the Windows presets should be changed gradually with a recoverable baseline.
