# Sensel Windows 控制面板逆向结果

分析对象是 Windows 分区中的 Sensel Haptic Touchpad 1.2.12.0。逆向过程中使用的完整应用包仅保留在本地工作目录 artifacts/sensel-windows-app-1.2.12.0/；该应用及其运行时文件不属于本仓库发布内容。

## 结论

Windows 控制面板没有调用一个独立的“触发力度 API”。它通过 `SenselSerialDevice` 的 HID 管道读写 Sensel 内部寄存器：

| 设置 | 寄存器 | 单位/范围 |
| --- | ---: | --- |
| 主点击按下力度 | `0x0038` | `Gf / 2`，8 位 |
| 主点击释放力度 | `0x0090` | `Gf / 2`，8 位 |
| 3HB 左按下/释放 | `0x0091` / `0x0092` | Windows TrackPoint 档位寄存器值 |
| 3HB 右按下/释放 | `0x0093` / `0x0094` | Windows TrackPoint 档位寄存器值 |
| 3HB 中按下/释放 | `0x0095` / `0x0096` | Windows TrackPoint 档位寄存器值 |
| TrackPoint 按钮模式 | `0x008A` | `0` / `1` |
| 触觉反馈强度 | `0x00AB` | `0..100` |

主点击力度的控制面板逻辑是：

```text
down = selected_gf / 2                 // 整数除法
up   = round(down * 0.65)
write 0x0038 = down
write 0x0090 = up
save each register as UserSetting
```

当前版本的三个主点击选项为 `120`、`164`、`190` Gf，对应寄存器值分别为 `(60,39)`、`(82,53)`、`(95,62)`。

Windows 控制面板的完整可调界面为五项：

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

## HID 管道帧

设备 VID/PID 是 `0x2C2F:0x0028`，Windows 程序使用 HID 报告 ID `9`。每个 HID 报告固定 21 字节：

```text
[0]    09                         报告 ID
[1]    N                          有效数据长度，最多 19
[2:]   N 字节协议数据
其余   0                          填充到 21 字节
```

内部寄存器命令为：

```text
command[0] = ((address & 0x3f00) >> 7) | 0x01 | (0x80 if read else 0)
command[1] = address & 0xff
command[2] = size
```

普通写寄存器发送：

```text
[command[0], command[1], size, data..., sum(data) & 0xff]
```

读寄存器返回的数据依次为：

```text
[read_ack, status, size_u16_le, data..., sum(data) & 0xff]
```

普通写返回 `[write_ack, status]`；ACK 值分别是 `0x01` 和 `0x05`。保存用户设置时，Windows 程序向 `0x0230` 写入 `<address:u16><0x4000:u16><0x51>`。

## 已验证

本机当前设备是 `/dev/hidraw1`（`SNSL0028:00`）。只读验证得到：

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

## GNOME 设置注入

GNOME 设置的“鼠标/触控板”面板现在复用了反馈强度的特权 helper 链路：

- “触觉反馈”直接读写 `0x00AB`，与 Windows 的 `ptp_haptic_intensity` 寄存器一致；界面档位为
  1～10，按 `[32, 45, 55, 63, 71, 77, 84, 89, 95, 100]` 非线性映射。
- “点击力度”提供 Windows 控制面板同样的 `Low / Medium / High` 三档，底层对应 `120 / 164 / 190 Gf`。
- “TrackPoint 按钮”和 “TrackPoint 点击力度”分别对应 `0x008A` 与 `Low / Medium / High` 三档，底层寄存器值为 `28 / 38 / 60`。
- 触觉强度和开关直接使用 `0x00AB`；强度写入通过同一个 root-owned HID daemon 完成，并保存 Windows 使用的 UserSetting。
- 读取完整状态通过 `sensel-haptic-set --get-state` 完成；单项读写入口分别是 `--get/--set-intensity`、`--get/--set-click-force`、`--get/--set-trackpoint-click-force` 和 `--get/--set-trackpoint-buttons`。

## 独立 GUI 精确调节

独立控制面板 `sensel-haptic-control` 在保留 Windows 预设说明的同时提供连续范围：

- 独立 GUI 的 `Click Force`：界面统一显示主点击按下寄存器原始值 `1..255`；写入 helper 时转换为 `Gf = raw * 2`，因此底层仍按 `down = Gf / 2` 写入 `0x0038`，释放值按 `round(down * 0.65)` 写入 `0x0090`。Windows 的 `120 / 164 / 190 Gf` 预设在此界面显示为 `60 / 82 / 95`。
- `TrackPoint Click Force`：输入范围为 `1..255` 的 Windows 3HB 原始寄存器单位；三个按下寄存器直接写入该值，三个释放寄存器写入 `round(value * 0.65)`。

因此，两组寄存器都可以接受超过 Windows 图形界面预设的值；`255` 是单字节寄存器的写入上限。超过 Windows 校准范围后，实际手感和固件行为不再由 Windows 预设覆盖，建议逐步调节并保留可恢复的当前值。
