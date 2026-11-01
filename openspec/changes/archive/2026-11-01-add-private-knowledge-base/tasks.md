# Tasks

> 本变更的实现在补记本 change 之前已完成并通过验证，因此所有任务均标记为完成；每条的验证方式写在描述里，可逐条复核。

## 1. 依赖与配置

- [x] 1.1 在 `backend/requirements.txt` 增加 `langchain-chroma==1.1.0`、`langchain-text-splitters==1.1.3`、`chromadb==1.5.9`、`pypdf==6.21.4`、`docx2txt==0.9`、`python-multipart==0.0.33`，安装后 `python -c "import chromadb, pypdf"` 成功
- [x] 1.2 在 `app/core/config.py` 增加 `kb_enabled`、`dashscope_api_key`、`dashscope_base_url`、`embedding_model/dimensions/batch_size/timeout`、`chroma_persist_dir`、`kb_upload_dir`、`kb_max_file_bytes`、`kb_max_documents_per_user`、`kb_max_text_chars`、`kb_chunk_size/overlap`、`kb_top_k`、`kb_context_max_chars`、`kb_max_documents_per_quiz`、`kb_upload_timeout_seconds`，并通过 `kb_chunk_overlap < kb_chunk_size` 校验（`pytest tests/test_config.py` 通过）
- [x] 1.3 在 `.env.example` 补齐同名配置块，并在 `.env` 追加空占位；`.gitignore` 增加 `backend/data/`（`git check-ignore -v backend/data/chroma` 命中）

## 2. 知识库数据模型与持久化

- [x] 2.1 新增 `app/models/knowledge.py`（文档、列表、删除结果、粘贴文本请求、检索命中），`KnowledgeSourceType` 覆盖 pdf/docx/md/txt（`pytest tests/test_knowledge_loaders.py::test_detect_source_type*`）
- [x] 2.2 新增迁移 `005_knowledge_base.sql` 创建 `knowledge_documents` 表，幂等可重复执行（`pytest tests/test_knowledge_repository.py -k mysql` 通过，`SHOW TABLES` 可见）
- [x] 2.3 新增 `app/repositories/knowledge_repository.py`：MySQL 实现 + 内存降级，提供 create/get/list_by_user/count_by_user/mark_ready/mark_failed/delete（`pytest tests/test_knowledge_repository.py` 全绿，含用户隔离与越权删除）
- [x] 2.4 `QuizSource.origin` 增加 `knowledge`（`pytest tests/test_quiz_grounding.py tests/test_research_knowledge.py` 通过）

## 3. 文档解析与切分

- [x] 3.1 新增 `app/knowledge/loaders.py`：按扩展名识别 pdf/docx/md/txt，PDF 用 `pypdf`、Word 用 `docx2txt`、文本按 UTF-8→GB18030 兜底解码；空文件、损坏文件、不支持格式统一抛 `InvalidInput`（`pytest tests/test_knowledge_loaders.py` 覆盖 5 种扩展名 + 3 类失败）
- [x] 3.2 新增 `app/knowledge/splitter.py`：`RecursiveCharacterTextSplitter(chunk_size, chunk_overlap, add_start_index=True)`，中英混排分隔符，输出带 `doc_id/title/source_type/chunk_index` 且无空白块（`pytest tests/test_knowledge_loaders.py -k split` 通过）

## 4. 向量化与向量库

- [x] 4.1 新增 `app/knowledge/embeddings.py`：`build_embeddings()` 构造 `OpenAIEmbeddings(model=text-embedding-v4, dimensions, base_url, check_embedding_ctx_length=False, chunk_size=10)`，外层 `KnowledgeEmbeddings` 显式分批；缺少 Key 时抛 `RuntimeError`（`pytest tests/test_knowledge_embeddings.py` 7 项通过，含 25 条输入 → 10/10/5 分批断言）
- [x] 4.2 新增 `app/knowledge/vector_store.py`：`ChromaKnowledgeStore` 用模块级缓存保证单 `PersistentClient`，collection 为 `kb_user_{user_id}`，提供 add/search/delete_document/count，全部调用走 `asyncio.to_thread`（`pytest tests/test_knowledge_vector_store.py` 7 项通过，含跨用户隔离与按文档过滤）

## 5. 知识库服务与接口

- [x] 5.1 新增 `app/services/knowledge_service.py`：上传→解析→切分→向量化→入库，配额/大小/类型校验，失败回滚（清向量 + 清文件），`search()` 输出受 `kb_context_max_chars` 约束的上下文，`resolve_doc_ids()` 校验归属（`pytest tests/test_knowledge_service.py` 13 项通过，含超限、损坏、嵌入失败回滚、字符预算）
- [x] 5.2 新增 `app/api/v1/routes/knowledge.py` 与路由注册：`POST /knowledge/documents`（multipart）、`POST /knowledge/documents/text`、`GET /knowledge/documents`、`DELETE /knowledge/documents/{doc_id}`，全部 `require_user`，服务不可用返回 5031（`pytest tests/test_knowledge_api.py` 10 项通过，含 401/400/404/503）
- [x] 5.3 `app/main.py` 装配 `knowledge_service` 并注入 `create_app`，MySQL 缺失时降级为内存元数据仓库（`pytest tests/test_knowledge_api.py` 与 `/openapi.json` 中出现 3 条 knowledge 路由）

## 6. 多源检索集成

- [x] 6.1 新增 `app/knowledge/retriever_tool.py`：`StructuredTool` 名 `knowledge_search`，调用服务并写入 `SourceCollector`（`pytest tests/test_research_knowledge.py::test_agent_receives_knowledge_tool` 通过）
- [x] 6.2 `SourceCollector` 增加 `record_knowledge()` 与 `knowledge` 排序权重，「用户资料 → 知识库 → 网页」合并编号（`pytest tests/test_research_knowledge.py::test_knowledge_sources_are_used_without_agent` 通过）
- [x] 6.3 `ResearchService.gather()` 增加 `user_id` / `knowledge_doc_ids`，构建知识库工具并入工具集，判定条件从「有网页来源」改为「有网页或知识库来源」，并加确定性兜底（`pytest tests/test_research_knowledge.py` 8 项通过）
- [x] 6.4 研究缓存 key 纳入 `knowledge_doc_ids`（`pytest tests/test_research_knowledge.py::test_knowledge_scope_participates_in_cache_key` 通过）
- [x] 6.5 `QuizService` 解析知识库范围并传参，`_source_type()` 支持 `kb` / `mixed`，匿名或越权请求返回 400（`pytest tests/test_research_knowledge.py -k quiz` 通过）

## 7. 前端

- [x] 7.1 新增 `types/knowledge.ts`、`services/api.ts` 知识库接口、`services/upload.ts`（`Taro.uploadFile` multipart 封装），`services/request.ts` 导出 `apiUrl` / `currentAuthHeader`（`npx tsc --noEmit` 通过）
- [x] 7.2 新增 `pages/knowledge/index`（列表 / 上传 / 删除 / 粘贴文本 / 未启用提示），并在 `app.config.ts` 注册页面（`npm run build:weapp` 编译成功）
- [x] 7.3 首页新增「我的知识库」入口与文档勾选 chips，未勾选时提交全部；`useUserStore` 增加 `knowledge` / `knowledgeEnabled` / `loadKnowledge` 并在 `ensureSession` 中加载（`npx tsc --noEmit` + `npm run build:h5` 通过）

## 8. 验证

- [x] 8.1 后端全量回归保持绿色（`pytest -q` → 384 passed, 1 skipped）
- [x] 8.2 真实链路验证：真实百炼 Embedding 上传 MD/PDF/粘贴文本 → 建库 → 用 `knowledge_doc_ids` 出题 → 轮询到 `succeeded`，题库 `source_type` 含知识库来源、每题 citations 指向知识库来源、历史详情返回 sources/grounding（已用 3 份文档跑通，耗时 14.1s）
- [x] 8.3 更新 `README.md` 与 `docs/方案设计文档.md`（API 表、错误码、知识库章节、测试数量）

## Workflow follow-up

- 归档本 change 并同步 delta 到主规格（`openspec archive add-private-knowledge-base`）
