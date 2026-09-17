# Contributing

感谢你愿意改进这个项目。我们优先接受可复现的缺陷修复、测试、文档，以及与“可自托管 RAG 客服”定位直接相关的功能。

## 开始之前

1. 搜索现有 Issues，避免重复讨论。
2. 对较大功能先开 Issue，写清问题、使用场景、数据边界和替代方案。
3. 不要提交真实客服对话、企业内部文档、API Key、访问令牌或个人信息。

## 本地开发

```bash
python -m venv .venv
pip install -r requirements-dev.txt
cp .env.example .env
docker compose up -d qdrant redis
python -m uvicorn app.main:app --reload
```

Windows PowerShell 使用 `.\.venv\Scripts\Activate.ps1` 和 `Copy-Item .env.example .env`。

## 提交前检查

```bash
ruff check .
ruff format --check .
python -m unittest discover -s tests -v
pip-audit -r requirements.txt
docker compose config --quiet
```

涉及 Web 工作台时，请同时检查桌面和窄屏布局，并验证至少一次上传、提问或会话操作。涉及 API 行为时，请补充失败路径测试，不只覆盖成功响应。

## Pull Request 约定

- 一个 PR 解决一个清晰问题，避免顺手重构无关模块。
- 描述用户可见变化、验证命令、已知限制和配置迁移。
- 新增环境变量时同步更新 `.env.example` 和 README。
- 新增依赖时说明理由，并确认 `pip-audit` 没有引入已知漏洞。
- 不虚构用户、性能、采用率或效果指标；实验结果必须能复现。

## Commit 建议

使用简短的祈使句，例如：

```text
Limit uploaded document size
Document the self-hosted deployment flow
Add regression coverage for draft review states
```

维护者可能会在合并前 squash commits，以保持历史清晰。
