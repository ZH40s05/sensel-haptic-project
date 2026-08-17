name: 功能需求 / Feature request
description: 希望支持的新能力 / Suggest a new capability
labels: enhancement
body:
  - type: textarea
    id: problem
    attributes:
      label: 想解决的问题 / Problem to solve
      description: 什么场景下需要这个功能 / What situation needs this
    validations:
      required: true
  - type: textarea
    id: solution
    attributes:
      label: 期望的方案 / Proposed solution
  - type: dropdown
    id: entry
    attributes:
      label: 相关入口 / Affected entry point(s)
      options:
        - WebHID 网页版 / WebHID web panel
        - 独立 Tk 面板 / Standalone Tk panel
        - GNOME 设置集成 / GNOME Settings integration
        - 命令行 helper / CLI helper
        - 全部 / All
    validations:
      required: true
