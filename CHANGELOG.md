# 更新日志 / Changelog

本文件记录用户可感知的变更。格式基于 Keep a Changelog，版本遵循
语义化版本。

User-visible changes are recorded here. Format based on Keep a
Changelog; versioning follows Semantic Versioning.

## [未发布 / Unreleased]

- 网页副标题文字精简。
- Web page tagline shortened.
- 精简中文主导的双语文档，并明确 README、WebHID、兼容性、安全和逆向笔记的职责。
- Simplified the Chinese-first bilingual documentation and clarified ownership across
  the README, WebHID, compatibility, security, and reverse-engineering guides.

## [1.0.0] — 2026-08-17

首个稳定版本。

### 新增 / Added

- **WebHID 跨平台面板**（`tools/sensel-haptic-web.html`）：单文件、零
  依赖，Chromium 系浏览器（Chrome / Edge / Opera）在 Windows /
  macOS / Linux / ChromeOS 直接打开即用；无 root、无服务进程。
  功能与桌面版一致。在线版托管于 GitHub Pages。
  （`cd23ba2`）
- **可调释放比值**：主点击与 TrackPoint 的抬起触发力度可按按下力度的
  5%–100% 比值调节，Windows 固定 65%。GUI 从 up/down 寄存器对反推
  当前比值。（`a008992`）
- **草稿式编辑**：所有滑条/开关改动只写 RAM 即时预览；全局
  保存（仅提交改动项，逐寄存器 写→存，带 n/N 进度）、取消、重置
  （载入参考设备首选预设：强度 100 / 点击 60 / TrackPoint 120 /
  按钮开）。解决每次调节写 flash 卡 2–3 秒的问题。（`ded2aed`、
  `f8fa16c`，需求来自 issue #1）
- 独立 Tk 控制面板与 Fedora GNOME 设置集成（GNOME Control Center
  50.0 补丁），共用 root helper 链路（Polkit + pkexec）。
- 简体/繁体中文翻译；中文为主的双语文档。
- 假固件协议测试（Python 与 Node/WebHID 双套）接入 `tests/check.sh`。
- 项目图标（SVG + PNG 多尺寸）与桌面入口品牌化。

### 修复 / Fixed

- **flash 忙窗口重试**：persist 写入后固件写闪存期间（约 1.5–3 秒）
  寄存器管道不应答，导致所有设置写入必败（EREMOTEIO/超时）。为
  读/写路径加入最多 3 次、间隔 1.5 秒的重试（仅对 OSError/
  TimeoutError，协议错误立即失败）。实测于 SNSL0028。（`f097c61`）
- 标量设置（强度、TrackPoint 按钮）去掉写后立即读回验证——该读回
  必然撞上忙窗口，令每次调节多等约 2.5 秒。（`446e40f`）

### 变更 / Changed

- 文档全部重写为中文为主的双语版本。（`25f5b18`）
- 仓库开源（public）并启用 GitHub Pages。

[未发布 / Unreleased]: https://github.com/ZH40s05/sensel-haptic-project/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/ZH40s05/sensel-haptic-project/releases/tag/v1.0.0
