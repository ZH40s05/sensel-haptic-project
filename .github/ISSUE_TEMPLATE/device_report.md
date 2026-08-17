name: 设备兼容报告 / Device compatibility report
description: 在新机型/固件上验证或报告不兼容 / Verified or broken on a new model/firmware
labels: compatibility
body:
  - type: textarea
    id: hardware
    attributes:
      label: 硬件 / Hardware
      description: 笔记本型号与触摸板型号 / Laptop and touchpad model
      placeholder: "ThinkPad X1 Carbon Gen 13, SNSL0028:00 2C2F:0028"
    validations:
      required: true
  - type: input
    id: kernel
    attributes:
      label: 内核与发行版 / Kernel and distribution
      placeholder: "Fedora 44, kernel 7.1.8-200.fc44"
    validations:
      required: true
  - type: input
    id: desktop
    attributes:
      label: 桌面环境 / Desktop
      placeholder: "GNOME 50.4"
  - type: input
    id: firmware
    attributes:
      label: 触摸板固件版本（如有）/ Touchpad firmware (if known)
  - type: textarea
    id: sysfs
    attributes:
      label: hidraw 路径 / Resolved sysfs path
      description: |
        运行 / run:
        `readlink -f /sys/class/hidraw/hidrawN/device`
      render: text
    validations:
      required: true
  - type: textarea
    id: registers
    attributes:
      label: 只读寄存器观察 / Read-only register observations
      description: |
        可选但强烈建议 / optional but strongly recommended:
        `sudo python3 tools/sensel-hid-pipe.py --device /dev/hidrawN read 0x0038`
        等对 0x0038/0x0090/0x0091-0x0096/0x008A/0x00AB 的读取结果。
      render: text
  - type: checkboxes
    id: persistence
    attributes:
      label: 持久性 / Persistence
      options:
        - label: 设置在重启后保留 / Settings survive reboot
        - label: 设置在挂起恢复后保留 / Settings survive suspend/resume
  - type: dropdown
    id: result
    attributes:
      label: 结果 / Result
      options:
        - 完全可用 / Fully working
        - 部分功能异常 / Partially working
        - 无法识别或写入 / Device rejected or writes fail
    validations:
      required: true
