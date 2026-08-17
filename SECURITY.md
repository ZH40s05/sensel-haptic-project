# 安全策略 / Security policy

本项目安装 root 拥有的 HID helper 与一条 Polkit 规则。任何一处的错误都可
能影响硬件设置或扩大本地权限，因此在修复可用之前，安全报告不应连同利用
代码一起公开发布。

This project installs a root-owned HID helper and a Polkit rule. A mistake
in either can affect hardware settings or expand local privilege, so
security reports should not be posted publicly with an exploit before a fix
is available.

在公开安全联系方式配置完成之前，请私下发送报告给仓库维护者，并包含 /
Until a public security contact is configured, send a private report to the
repository maintainer and include:

- 受影响的提交或版本 / the affected commit or release；
- Fedora、内核、GNOME 与设备固件版本 / Fedora, kernel, GNOME, and device
  firmware versions；
- 不包含秘密的复现步骤 / reproduction steps that do not include secrets；
- 预期与实际行为 / the expected and observed behavior。

未审查 `/usr/local/libexec` 与 `/etc/polkit-1/rules.d` 下所安装文件之前，
不要在生产工作站上运行安装脚本。

Do not run the installer on a production workstation without reviewing the
files installed under /usr/local/libexec and /etc/polkit-1/rules.d.
