# Governance Demo Script

## 脚本作用

`scripts/demo_governance_flow.py` 用于稳定演示知识库治理闭环：

```text
治理前 RAG 问答
-> 覆盖不足问题自动进入 /governance/unanswered_questions
-> 分析历史客服问题
-> 生成 knowledge gaps / clusters / drafts
-> 自动选择优惠券相关 draft
-> approve 并回流 Qdrant
-> 治理后 RAG 问答
-> 对比 sources 是否出现 governance_draft
```

它适合本地演示、贡献者验证，也适合在 push 前做一次端到端冒烟检查。

## 运行前准备

1. 安装依赖。
2. 配置 `.env`，填入 LLM 和 Embedding API key。
3. 启动 Qdrant 和 Redis。
4. 启动 FastAPI 服务。

`.env` 不应提交到 GitHub。

## 启动服务命令

```powershell
docker compose up -d qdrant redis
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

确认 API 可访问：

```text
http://127.0.0.1:8000/docs
```

## 运行 demo 命令

```powershell
.\.venv\Scripts\python.exe scripts\demo_governance_flow.py
```

可选参数：

```powershell
.\.venv\Scripts\python.exe scripts\demo_governance_flow.py --base-url http://127.0.0.1:8000 --top-k 8
```

默认 `--questions-source auto`：优先读取 `/governance/unanswered_questions` 中的 pending 问题；如果没有 pending 问题，则回退到 `knowledge_base_samples/mock_customer_questions.json`。

也可以显式指定：

```powershell
.\.venv\Scripts\python.exe scripts\demo_governance_flow.py --questions-source pending
.\.venv\Scripts\python.exe scripts\demo_governance_flow.py --questions-source mock
```

## 预期输出

脚本会输出几个阶段：

```text
1. Before governance: ask RAG
Before answer:
...
Before sources:
  - ...

2. Governance analyze: find gaps and generate drafts
Generated gaps: ...
Generated clusters: ...
Generated drafts: ...

Selected coupon-related draft:
  id: draft_xxxxx
  title: ...
  topic: ...

3. Approve draft and publish back to Qdrant
Review status: approved
Published chunks: ...

4. After governance: ask RAG again
After answer:
...
After sources:
  - governance_draft_draft_xxxxx.md
After sources contains governance_draft: True

5. Demo result
Verification passed: True
```

## 如何判断验证通过

满足以下条件即可认为闭环跑通：

- `/governance/analyze` 生成了 gaps、clusters、drafts。
- 脚本能找到优惠券相关 draft。
- approve 返回 `review_status=approved`。
- approve 后 `published_chunks` 大于 0。
- 第二次 `/rag/ask` 的 sources 中出现 `governance_draft`。

## 常见失败原因与排查

### 无法连接服务

检查 FastAPI 是否启动：

```text
http://127.0.0.1:8000/health
```

### Qdrant 或 Redis 未启动

运行：

```powershell
docker compose up -d qdrant redis
```

### LLM 或 Embedding 调用失败

检查 `.env`：

- `LLM_API_KEY`
- `LLM_BASE_URL`
- `LLM_MODEL`
- `SILICONFLOW_API_KEY`
- `SILICONFLOW_BASE_URL`
- `EMBEDDING_MODEL`

### 找不到优惠券相关 draft

检查 `knowledge_base_samples/mock_customer_questions.json` 是否包含优惠券过期、补发、恢复等问题。

### approve 成功但 RAG sources 没有 governance_draft

可能原因：

- `top_k` 太小，治理草稿没有被召回。
- Qdrant collection 中已有很多旧数据干扰召回。
- Embedding 服务异常导致写入或检索失败。
- 草稿内容与 after question 相似度不足。

可尝试：

```powershell
.\.venv\Scripts\python.exe scripts\demo_governance_flow.py --top-k 8
```

或清理本地 Qdrant 测试数据后重新运行。

## Windows 本机运行后端时的 Qdrant 地址

如果 FastAPI 在 Windows 本机运行，而 Qdrant 通过 Docker Compose 启动，`.env` 应使用：

```text
QDRANT_URL=http://127.0.0.1:6333
QDRANT_HOST=127.0.0.1
QDRANT_PORT=6333
```

不要使用 `http://qdrant:6333`。这个地址只适合 FastAPI 也运行在 Docker Compose 容器网络里的情况。

## 重置 demo collection

如果更换过 `EMBEDDING_MODEL`，旧 Qdrant collection 的向量维度可能和当前 embedding 模型不一致。上传接口会返回类似：

```text
qdrant collection dimension mismatch
```

此时运行：

```powershell
.\.venv\Scripts\python.exe scripts\reset_demo_store.py
```

然后重新上传 `knowledge_base_samples/` 下的示例知识库文档。
