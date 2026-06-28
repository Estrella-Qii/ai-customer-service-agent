# AI 智能客服 Agent

一个面向客服场景的 RAG 智能客服后端项目。它可以上传知识库文档，自动切片、向量化、写入向量数据库，然后基于检索结果调用大模型生成客服回复。

项目当前默认使用：

- FastAPI：提供 HTTP API 和 Swagger 文档
- DeepSeek：作为 LLM 生成回答
- 硅基流动：提供 OpenAI-compatible API 和 Embedding
- LangChain：文档切片、Embedding、向量库集成
- Qdrant：向量数据库
- Redis：保存会话记忆
- Docker Compose：启动 Qdrant，也可以同时启动 API 服务

## 当前完成度

这个项目目前是一个可以演示的 RAG 客服后端 MVP。

已完成：

- FastAPI 服务入口
- Swagger API 文档
- DeepSeek / OpenAI-compatible LLM 调用
- 文档上传接口
- 支持 `.txt`、`.md`、`.pdf`
- 文档切片
- 硅基流动 Embedding 向量化
- Qdrant collection 自动创建
- 向量入库
- 相似度检索
- RAG 问答接口
- Redis 会话记忆
- 会话历史查询与清空接口
- 示例知识库文档
- `.env.example` 示例配置
- Dockerfile
- Docker Compose

后续计划：

- 用 LangGraph 编排 Agent 工作流
- 增加简单聊天前端页面
- 增加单元测试和 GitHub Actions
- 增加鉴权、限流、日志等生产能力

## 接口说明

启动后打开：

```text
http://127.0.0.1:8000/docs
```

主要接口：

- `GET /health`：健康检查
- `POST /chat`：直接调用大模型对话
- `POST /documents/upload`：上传知识库文档，自动切片并入库
- `GET /documents/search`：从向量库检索相关知识片段
- `POST /rag/ask`：检索知识库后，让大模型基于资料回答
- `GET /sessions/{session_id}/history`：查看会话历史
- `DELETE /sessions/{session_id}`：清空会话历史

## 项目结构

```text
app/
  core/
    config.py          # 环境变量配置
  rag/
    document_loader.py # 文档解析与切片
    embeddings.py      # Embedding 配置
    vector_store.py    # Qdrant 向量库
    retriever.py       # 检索封装
    qa.py              # RAG 问答逻辑
  memory/
    store.py           # Redis 会话记忆
  llm.py               # LLM 调用封装
  main.py              # FastAPI 入口
routers/
  documents.py         # 文档上传与检索接口
  rag.py               # RAG 问答接口
knowledge_base_samples/
  refund_policy.md     # 示例：退款政策
  shipping_policy.md   # 示例：物流政策
  membership_faq.md    # 示例：会员 FAQ
```

## 本地启动

### 1. 创建虚拟环境

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

### 2. 安装依赖

```powershell
pip install -r requirements.txt
```

### 3. 配置环境变量

复制 `.env.example` 为 `.env`：

```powershell
copy .env.example .env
```

然后填入自己的密钥：

```text
LLM_API_KEY=your_llm_api_key_here
SILICONFLOW_API_KEY=your_siliconflow_api_key_here
```

不要把 `.env` 上传到 GitHub。

### 4. 启动 Qdrant 和 Redis

```powershell
docker compose up -d qdrant redis
```

### 5. 启动 FastAPI

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

打开：

```text
http://127.0.0.1:8000/docs
```

## Docker Compose 启动

先准备 `.env`：

```powershell
copy .env.example .env
```

填好密钥后启动：

```powershell
docker compose up --build
```

API 地址：

```text
http://127.0.0.1:8000/docs
```

如果只想启动 Qdrant，本地用 Python 跑 API：

```powershell
docker compose up -d qdrant redis
```

## 使用流程

1. 打开 `http://127.0.0.1:8000/docs`
2. 在 `POST /documents/upload` 上传知识库文档
3. 在 `GET /documents/search` 测试检索效果
4. 在 `POST /rag/ask` 测试基于知识库的客服回答

示例请求：

```json
{
  "question": "订单已经发货还能退款吗？",
  "top_k": 4,
  "session_id": "demo-user-001"
}
```

返回结果会包含：

- `answer`：大模型生成的客服回复
- `session_id`：本次会话 ID
- `sources`：引用的文档来源
- `contexts`：检索到的原始知识片段

如果不传 `session_id`，系统会自动生成一个新的会话 ID。下一次请求带上同一个 `session_id`，客服就能参考前文进行多轮对话。

## 知识库文档从哪里来

可以使用真实业务资料，例如：

- 售后政策、退款政策、物流政策
- 产品说明书、安装指南、使用教程
- 常见问题 FAQ
- 客服历史高频问题整理
- 官网帮助中心文章
- 会员规则、优惠券规则、活动规则
- 内部 SOP 和客服话术

建议先整理成 `.md` 或 `.txt` 文件。每个文件围绕一个主题，标题清晰，段落不要太长。

## 安全说明

本项目通过 `.env.example` 提供配置模板。实际使用时，请在本地创建 `.env` 并填写自己的 API Key。

`.env`、虚拟环境、缓存文件和本地向量库数据已经在 `.gitignore` 中忽略，不应提交到版本库。

## License

MIT
