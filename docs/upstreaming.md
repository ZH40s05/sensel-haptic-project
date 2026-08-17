# 上游化计划 / Upstreaming plan

本仓库适合作为独立社区项目，但当前代码树是 Fedora 专属的集成组合，而不是
能原样提交给某个上游项目的补丁。

The repository is suitable as an independent community project, but the
current tree is a Fedora-specific integration bundle rather than a patch
that can be submitted unchanged to one upstream project.

## 推荐顺序 / Recommended order

### 1. 稳固独立项目 / Stabilize the independent project

- 把 Sensel 协议实现保留在用户态 / keep the protocol in userspace；
- 记录确切的设备与固件边界 / document the exact device and firmware
  boundary；
- 为帧、范围校验、持久化与读回失败补充假设备测试 / add fake-device
  tests for framing, range validation, persistence, and readback failures；
- 发布可复现检查与 Fedora 包 / publish reproducible checks and a Fedora
  package；
- 收集多于一种设备与固件版本的报告 / collect reports from more than one
  device and firmware revision。

### 2. 把合适的层次提交给合适的项目 / Submit the right layer to the right project

| 目标 / Target | 适合的贡献 / Suitable contribution |
| --- | --- |
| Linux 内核 HID | 若设备暴露稳定的标准接口，提交小的设备 quirk 或标准 HID 触觉映射 / a small quirk or standard HID haptic mapping if a stable standard interface exists |
| libinput | 属于输入后端的指针、压力、手势或按键行为 / pointer, pressure, gesture, or button behavior |
| GNOME Control Center | 由稳定系统 API 支撑的通用设置界面，而非直接访问 Sensel 寄存器 / a generic settings UI backed by a stable system API |
| Fedora | RPM、依赖元数据、Polkit 集成与桌面集成 / an RPM, dependency metadata, Polkit integration |

在更底层的上游 API 出现前，Python daemon、私有寄存器映射、Fedora 安装
器与 GNOME 补丁应保持项目专属。

The Python daemon, private register map, Fedora installer, and GNOME patch
should remain project-specific until a lower-level upstream API exists.

## 上游提案前的审查清单 / Review checklist before an upstream proposal

- 说明用户可见问题与受影响设备 / state the user-visible problem and
  affected devices；
- 把协议、安全、打包与界面改动拆成不同提交 / separate protocol,
  security, packaging, and UI changes into different commits；
- 附日志与只读观察，不含专有应用文件 / include logs and read-only
  observations, not proprietary application files；
- 测试热插拔、权限错误、畸形应答与挂起恢复 / test hotplug, permission
  errors, malformed replies, and suspend/resume；
- 提议前把 GNOME 补丁 rebase 到当前上游源码 / rebase the GNOME patch
  onto the current upstream source first；
- 附上相应上游要求的签核与贡献来源 / include the appropriate sign-off
  and contribution provenance。
