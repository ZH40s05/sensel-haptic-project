# WebHID 面板 / WebHID panel

`tools/sensel-haptic-web.html` 是一个不依赖本地服务的单文件控制面板。
它直接使用 Chromium 浏览器的 WebHID API 访问 Sensel 触摸板，适合不想
安装 Python、Tk 或 root helper 的用户。

`tools/sensel-haptic-web.html` is a single-file control panel with no local
server or runtime dependency. It accesses the Sensel touchpad through the
WebHID API provided by Chromium browsers, for users who do not want to
install Python, Tk, or the root helper.

## 快速开始 / Quick start

1. 使用 Chrome、Microsoft Edge 或 Opera；Firefox 与 Safari 目前不支持
   WebHID / Use Chrome, Microsoft Edge, or Opera. Firefox and Safari do not
   currently implement WebHID.
2. 打开在线版
   [GitHub Pages panel](https://zh40s05.github.io/sensel-haptic-project/)，
   或直接打开本地 `tools/sensel-haptic-web.html` / Open the live panel or
   the local HTML file directly.
3. 点击“连接触摸板”，在浏览器设备选择器中选择 `2C2F:0028` / Click
   Connect and select the `2C2F:0028` device in the browser picker.
4. 等待读取完成后即可调节。滑条和开关先写入设备 RAM；点“保存”才会
   写入 UserSetting flash / Adjust after the initial read. Sliders and
   switches write RAM first; Save writes the UserSetting to flash.

浏览器的设备授权按网站来源保存。在线版与本地 `file://` 版是不同来源，
首次使用时需要分别授权。

Browser permissions are stored per origin. The live page and a local
`file://` copy are different origins and may each ask for permission once.

## Linux 权限 / Linux permissions

Linux 的 hidraw 节点通常默认只有 root 可读写。若使用 WebHID，需要安装
仓库提供的 udev 规则，让当前桌面会话用户获得 `uaccess`：

Linux hidraw nodes are commonly root-only by default. Install the udev rule
shipped by this repository so the active desktop session receives `uaccess`:

```bash
sudo cp tools/70-sensel-haptic-webhid.rules /etc/udev/rules.d/
sudo udevadm control --reload
sudo udevadm trigger
```

拔插触摸板或重新登录后检查权限 / Unplug/replug the touchpad or log in
again, then check:

```bash
getfacl /dev/hidrawN
```

输出应包含当前用户的 `rw-` ACL。规则匹配 HID modalias 与 HID 内核设备
名称，不匹配 USB 专属的 `idVendor`/`idProduct` 属性；这是因为目标
触摸板通过 I2C-HID 暴露。

The output should contain an `rw-` ACL for the current user. The rule
matches the HID modalias and HID bus device name rather than USB-only
`idVendor`/`idProduct` attributes, because the target touchpad is exposed
through I2C-HID.

## 功能 / Features

网页版与 Tk 面板共用相同的寄存器语义：

The web panel uses the same register semantics as the Tk panel:

- 读取设备当前值 / read the current device state；
- 触觉强度 1–10 档 / 10-level haptic intensity；
- 主点击与 TrackPoint 按下力度 / main and TrackPoint press force；
- 主点击与 TrackPoint 释放比值 5%–100% / 5%–100% release ratios；
- TrackPoint 按钮开关 / TrackPoint button enablement；
- 草稿预览、保存、取消与重置 / draft preview, Save, Cancel, and Reset。

保存多个项目时，页面按固件要求逐个执行“写寄存器→保存”。每个保存动作
可能令设备约 2.6 秒不响应；页面底部会显示当前保存进度。

When several settings are saved, the page interleaves register write and
UserSetting save operations as required by the firmware. Each save may make
the device unresponsive for about 2.6 seconds; the status line shows the
current progress.

## 安全模型 / Security model

- 浏览器的设备选择器是授权边界；页面只能访问用户明确选择的 HID 设备。
- 页面只接受 VID/PID `2C2F:0028`，但仍应确认设备选择器中的设备名称。
- 页面没有 HTTP 后端，不监听端口，也不请求外部服务。
- 私有寄存器写入可能影响触摸板行为。第一次在新设备上使用前，建议先
  读取并记录当前值。

- The browser device picker is the authorization boundary; the page can
  access only a HID device explicitly selected by the user.
- The page filters for VID/PID `2C2F:0028`; still verify the device name in
  the picker.
- There is no HTTP backend, listening port, or external service request.
- Private register writes can change touchpad behavior. Record the current
  values before using the page on a new device.

## 故障排查 / Troubleshooting

### 没有 WebHID 或没有“连接”按钮 / WebHID is unavailable

确认使用 Chromium 系浏览器，并通过 HTTPS、localhost 或直接 `file://`
打开页面。Firefox、Safari 及普通的非 Chromium 浏览器不会提供
`navigator.hid`。

Use a Chromium browser and open the page over HTTPS, localhost, or directly
from `file://`. Firefox, Safari, and other non-Chromium browsers do not
provide `navigator.hid`.

### 设备选择器为空 / The device picker is empty

确认触摸板已连接、设备匹配 `2C2F:0028`，并在 Linux 上检查 hidraw ACL。
关闭占用同一 HID 节点的其他程序后再试。

Confirm that the touchpad is connected and matches `2C2F:0028`; on Linux,
check the hidraw ACL. Close other programs holding the same HID node and
try again.

### 读取超时或保存失败 / Read timeout or save failure

先断开再重新连接设备。保存期间不要拖动其他控件；完成后等待状态栏
恢复。若问题重复出现，记录浏览器版本、系统版本、设备路径与页面状态
文字，再提交兼容性报告。

Disconnect and reconnect the device. Do not change another control while a
save is in progress; wait for the status line to finish. If the problem
persists, record the browser version, OS, device path, and status text before
opening a compatibility report.

### 设备被其他程序占用 / The device is busy

关闭桌面版控制面板、诊断工具或其他可能打开该 hidraw/HID 设备的程序。
同一设备不应同时由 WebHID 与 root daemon 写入。

Close the desktop panel, diagnostic tool, or any other program that may have
the hidraw/HID device open. Do not write to the device concurrently through
WebHID and the root daemon.

## 已知限制 / Known limitations

- 仅支持 Chromium 系浏览器 / Chromium browsers only。
- 浏览器关闭或设备拔出后，RAM 草稿不会保留；只有点“保存”后的值会写入
  flash / RAM drafts do not survive browser close or device removal; only
  values saved through Save reach flash。
- 页面无法使用 GNOME 的 gettext `.mo` 文件，内置简体中文与英文界面；
  后续翻译需同时修改页面内的 `STR` 字典 / the page cannot consume
  GNOME gettext `.mo` files and carries built-in Chinese and English strings
  in its `STR` dictionary。
- 热插拔与挂起恢复依赖浏览器和 HID 实现，尚未覆盖全部组合 / hotplug
  and suspend/resume behavior depends on the browser and HID implementation
  and is not covered for every combination。
