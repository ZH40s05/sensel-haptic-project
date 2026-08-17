# 贡献指南 / Contributing

欢迎贡献，尤其是设备兼容性报告、Fedora/GNOME 集成修复与翻译。

Contributions are welcome, especially device compatibility reports, fixes
for the Fedora/GNOME integration, and translations.

提交 Pull Request 之前 / Before opening a pull request:

1. 运行 / Run `./tests/check.sh`。
2. 不要提交 source/、artifacts/、构建目录、Windows 应用文件或生成的翻译目录 / Do not commit source/, artifacts/, build directories, Windows application files, or generated translation catalogs.
3. GNOME 集成的改动应保持补丁基于 README.md 所记录的 GNOME Control Center 版本 / For changes to the GNOME integration, keep the patch based on the version documented in README.md.
4. 不要在不熟悉的设备上测试寄存器写入。helper 已刻意限制为 Sensel HID 设备，但硬件行为仍可能随固件不同 / Do not test register writes on an unfamiliar device. The helper is intentionally restricted to Sensel HID devices, but hardware behavior can still vary by firmware.
5. 不要复制专有 Windows 应用的代码或运行时文件。请在逆向笔记中描述观察到的协议行为，并把厂商二进制文件排除在仓库之外 / Do not copy code or runtime files from the proprietary Windows application. Describe observed protocol behavior in the reverse-engineering notes instead, and keep vendor binaries out of the repository.
6. 协议校验或寄存器映射变化时，同步增加或更新硬件无关测试。硬件测试必须记录所用设备型号、固件、内核与桌面版本 / Add or update hardware-independent tests whenever protocol validation or register mapping changes. Hardware tests must document the device model, firmware, kernel, and desktop versions used.

保持提交聚焦，并描述验证所用的设备、固件、Fedora 或 GNOME 版本。面向
Linux 或 freedesktop.org 上游的改动应拆分为可独立审查的提交，并携带相应
上游要求的签核元数据。

Keep commits focused and describe any device, firmware, Fedora, or GNOME
version used for validation. Changes intended for a Linux or
freedesktop.org upstream should be split into independently reviewable
commits and carry the appropriate sign-off metadata for that upstream.
