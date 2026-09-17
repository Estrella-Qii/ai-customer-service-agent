# Changelog

本文件遵循 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)；项目计划采用 [Semantic Versioning](https://semver.org/)。

## [Unreleased]

## [0.1.0] - 2026-09-17

### Added

- 知识库治理工作流、草稿审核 API 和治理闭环演示脚本。
- 服务就绪检查、Web 首次使用引导和示例问题。
- 开源贡献、安全、Roadmap、Issue 模板和 `v0.1.0` 发布说明。
- CI 中的 Ruff、依赖漏洞审计、Compose 校验和容器构建。

### Changed

- Docker 容器改为非 root 用户运行，并为 API、Redis、Qdrant 增加健康检查。
- 依赖增加兼容版本范围，避免无界升级。
- 对外错误响应不再直接返回内部异常内容。

### Fixed

- 限制上传文件大小并规范化客户端文件名。
- 限制问题、会话 ID 和治理批次大小。
- 防止已发布治理草稿被直接编辑或拒绝。
- 治理 JSON 使用进程内锁和原子替换，降低单进程并发写坏文件的风险。

[Unreleased]: https://github.com/Estrella-Qii/ai-customer-service-agent/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Estrella-Qii/ai-customer-service-agent/releases/tag/v0.1.0
