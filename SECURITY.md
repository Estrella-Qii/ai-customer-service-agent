# Security Policy

## Supported versions

项目尚未发布首个稳定版本。安全修复只针对默认分支和最新发布版本（发布后）。

## Reporting a vulnerability

请不要在公开 Issue 中粘贴 API Key、访问令牌、真实客服数据或可直接利用的漏洞细节。

优先使用 GitHub 仓库的 **Private vulnerability reporting**。如果该功能尚未启用，请仅提交不包含利用细节的公开 Issue，请求维护者提供私密联系方式。

报告应包含：

- 受影响的 commit 或版本
- 最小复现步骤
- 可能影响的数据或能力
- 已验证的缓解方式（如有）

## Deployment warning

当前项目没有内置身份认证、租户隔离和速率限制。默认配置适合本地开发与受控内网，不应直接暴露到公网。部署者应在外层添加 TLS、身份认证、请求限流、日志脱敏、备份与数据保留策略。

`.env`、Qdrant 数据、Redis 数据、治理 JSON 和日志均属于运行时敏感资产，不应提交到仓库。
