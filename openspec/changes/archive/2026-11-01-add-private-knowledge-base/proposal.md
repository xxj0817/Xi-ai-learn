# Proposal

## Why

小程序目前的出题证据只有两类：模型自身记忆，和 Tavily 抓到的公开网页。企业培训资料、客服知识库、内部考题这类私有知识大模型既不知道也搜不到，用户无法用自己的资料刷题。项目最早的 MVP 范围也写明「允许用户自由输入想学的知识」，本节补上「用户自己的文档」这条输入路径。

> 说明：本变更为**补记归档**。功能已在代码中实现并端到端验证（后端 384 项测试通过，真实百炼 Embedding + DeepSeek + Tavily 跑通上传→检索→出题→引证），此前漏走了 OpenSpec 流程，现补齐 proposal / specs / design / tasks 以让规格体系与代码一致。

## What Changes

- 新增「私有知识库」能力：上传 PDF / Word / Markdown / TXT 或粘贴文本，解析 → 切分 → 向量化 → 存入向量库，可列举、可删除
- 向量化使用百炼 `text-embedding-v4`（1024 维，单批 10 条），向量按用户隔离存放在 Chroma
- 出题时把「知识库检索」作为工具交给研究 Agent，与 Tavily 工具并列，由 Agent 自主决定查私有库还是联网
- `POST /quiz/tasks` 与 `POST /quiz/generate` 新增可选字段 `knowledge_doc_ids`；为空表示使用该用户全部已就绪文档
- `QuizSource.origin` 新增 `knowledge`；题库 `source_type` 新增 `kb`，与网页/用户资料共存时为 `mixed`
- 研究结果缓存 key 纳入知识库文档范围，不同文档集不共享缓存
- 前端新增知识库页面与首页入口，支持勾选参与出题的文档
- 未配置 Embedding 凭据时知识库接口返回 5031，出题链路按原有逻辑降级，既有功能零影响

## Capabilities

### New Capabilities

- `knowledge-base`: 用户私有文档的上传、解析、切分、向量化、列举、删除与按用户隔离的语义检索

### Modified Capabilities

- `knowledge-retrieval`: 研究 Agent 的工具集从「仅 Tavily」扩展为「Tavily + 知识库检索」，缓存 key 增加知识库文档范围
- `quiz-generation`: 出题请求支持知识库文档范围，题库 `source_type` 增加 `kb` / `mixed`

## Impact

- 新增依赖：`langchain-chroma`、`chromadb`、`pypdf`、`docx2txt`、`langchain-text-splitters`、`python-multipart`
- 新增接口：`POST /knowledge/documents`、`POST /knowledge/documents/text`、`GET /knowledge/documents`、`DELETE /knowledge/documents/{doc_id}`
- 新增表：`knowledge_documents`（迁移 `005_knowledge_base.sql`）
- 新增运行目录：`backend/data/chroma`、`backend/data/uploads`（已加入 `.gitignore`）
- 新增配置项：`KB_ENABLED`、`DASHSCOPE_API_KEY`、`EMBEDDING_*`、`KB_*` 共 20 项
- 现有出题、报告、用户、异步任务接口与响应结构保持兼容：所有新增请求字段可选、新增响应字段有默认值
