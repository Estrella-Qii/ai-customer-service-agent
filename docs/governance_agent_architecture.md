# Knowledge Governance Agent Architecture

## 业务背景

传统客服知识库维护成本高，常见问题包括：

- 业务规则、优惠活动和售后政策经常变化，知识库容易过期。
- 客服历史问题中隐藏着大量高频缺口，但人工整理成本高。
- 普通 RAG 可以检索并回答，却不一定知道“知识库是否缺少某类问题”。
- 不同客服可能给出不一致回答，导致用户体验和合规风险。

本项目将历史客服问题作为输入，构建一个客服知识库治理 Agent，用于发现知识缺口、生成知识库草稿、经过人工审核后回流知识库。

## 解决方案

系统在原有 RAG 客服问答链路旁边增加治理链路：

```text
历史客服问题
-> 检索现有知识库
-> 覆盖判断
-> knowledge gap
-> gap clustering
-> draft generation
-> human review
-> Qdrant 回流
-> RAG 验证
```

它的目标不是替代人工知识库运营，而是把“发现问题”和“生成初稿”的部分自动化，再由人工做最终把关。

## 系统架构

```text
FastAPI
├── /rag/ask
│   └── Customer Service LangGraph
│       ├── load_memory
│       ├── retrieve_context
│       ├── generate_answer
│       └── save_memory
│
├── /governance/analyze
│   └── Governance LangGraph
│       ├── retrieve_knowledge
│       ├── extract_gaps
│       ├── cluster_gaps
│       └── generate_drafts
│
└── /governance/drafts/{id}/approve
    └── split draft -> embed -> Qdrant
```

核心模块：

- `app/agent/workflow.py`：RAG 客服问答工作流。
- `app/agent/governance_workflow.py`：知识库治理工作流。
- `app/governance/models.py`：治理数据模型。
- `app/governance/service.py`：分析、审核、回流等业务逻辑。
- `app/governance/store.py`：本地 JSON 治理状态存储。
- `app/rag/vector_store.py`：Qdrant 入库、检索、文档管理。

## 数据流说明

1. 输入历史客服问题，可以是 mock 问题，也可以是脱敏后的真实问题。
2. 对每个问题调用现有 RAG retriever，检索当前知识库。
3. 先用启发式规则判断覆盖情况，例如无检索结果、弱相关、较强相关。
4. 对需要进一步判断的问题调用 LLM，输出结构化覆盖结论。
5. 将 `gap` 和 `weakly_covered` 转为 KnowledgeGap。
6. 按 suggested topic 聚类，形成 GapCluster。
7. 为每个 cluster 生成 KnowledgeDraft。
8. 人工执行 approve / edit / reject。
9. approve 后将 draft 转为 Markdown，切片、向量化并写入 Qdrant。
10. 后续 `/rag/ask` 可以在 sources 中命中新写入的 `governance_draft`。

## LangGraph 节点说明

当前治理 MVP 的 LangGraph 节点：

- `retrieve_knowledge`：对历史问题调用 Qdrant 检索，并做覆盖判断。
- `extract_gaps`：将未覆盖或弱覆盖的问题抽取为 knowledge gaps。
- `cluster_gaps`：按 suggested topic 聚类，得到高频缺口主题。
- `generate_drafts`：为每个 cluster 生成知识库文章草稿。

审核、JSON 存储、approve/reject/edit、Qdrant 写入属于工程动作，放在普通 service 函数中，没有强行塞进 LangGraph。

## RAG 与治理闭环的关系

RAG 问答链路负责“消费知识库”：

```text
用户问题 -> Qdrant 检索 -> LLM 回答 -> sources
```

治理链路负责“运营知识库”：

```text
历史问题 -> 发现缺口 -> 生成草稿 -> 审核 -> 回流 Qdrant
```

两者通过 Qdrant 连接。治理链路写入的新知识，会被后续 RAG 链路检索到。

## Human-in-the-loop 审核机制

KnowledgeDraft 默认状态为 `pending`。人工可以：

- `approve`：确认草稿可用，写入 Qdrant。
- `edit`：修改标题、标准答案、证据要求、风险提示，状态保持 pending。
- `reject`：拒绝草稿并记录原因。

这个设计避免 LLM 自动把不可靠内容写入知识库。

## approve 后如何回流 Qdrant

approve 流程：

1. 将 KnowledgeDraft 转为 Markdown 知识库文章。
2. 调用 `split_text_to_documents()` 切片。
3. 写入 metadata：
   - `source=governance_draft`
   - `draft_id`
   - `topic`
   - `review_status=approved`
4. 调用现有 `add_documents()` 入库 Qdrant。

后续 `/rag/ask` 返回的 sources 中会出现类似 `governance_draft_<draft_id>.md` 的来源。

## 治理前后 RAG 验证方式

`scripts/demo_governance_flow.py` 会自动：

1. 治理前问优惠券过期补发问题。
2. 分析 mock 历史问题并生成草稿。
3. approve 优惠券相关草稿。
4. 治理后再问同类问题。
5. 检查 after sources 是否包含 `governance_draft`。

如果包含，说明闭环验证通过。

## 当前 MVP 边界

当前版本重点验证闭环，不追求生产完备：

- 聚类采用 suggested topic 分组，没有引入复杂聚类模型。
- 覆盖判断采用启发式规则 + LLM 结构化判断。
- 治理状态使用本地 JSON 文件存储。
- 没有实现权限系统、多人审核、审计后台。
- 没有完整的离线评测集。

## 后续可扩展方向

- 使用 embedding 聚类或 HDBSCAN 做更稳定的 gap clustering。
- 增加覆盖率、命中率、人工采纳率等治理指标。
- 增加草稿版本管理与审核流。
- 加入真实工单系统或客服系统数据导入。
- 增加定时任务，周期性扫描高频未解决问题。
- 增加回归评测，避免新知识污染旧知识。
