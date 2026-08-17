name: Bug 报告 / Bug report
description: 面板或 helper 运行不正常 / Something does not work as expected
labels: bug
body:
  - type: dropdown
    id: entry
    attributes:
      label: 使用入口 / Entry point
      options:
        - WebHID 网页版（Chrome/Edge 等浏览器）/ WebHID web panel
        - 独立 Tk 面板 / Standalone Tk panel
        - GNOME 设置集成 / GNOME Settings integration
        - 命令行 helper / CLI helper
    validations:
      required: true
  - type: textarea
    id: env
    attributes:
      label: 环境 / Environment
      description: 系统、浏览器/桌面、内核版本等 / OS, browser/desktop, kernel…
      placeholder: "Fedora 44, Edge 151, kernel 7.1.8"
    validations:
      required: true
  - type: textarea
    id: what-happened
    attributes:
      label: 发生了什么 / What happened
      description: 期望与实际行为 / Expected vs actual behavior
    validations:
      required: true
  - type: textarea
    id: logs
    attributes:
      label: 状态栏文字 / 状态输出 / Status output or logs
      description: |
        网页版：页面底部的红色/橙色状态文字。
        桌面版：状态栏文字；或运行
        `pkexec /usr/local/libexec/sensel-haptic-set --get-state /dev/hidrawN`
        （N 换成你的设备号）的输出。
      render: text
  - type: textarea
    id: repro
    attributes:
      label: 复现步骤 / Steps to reproduce
