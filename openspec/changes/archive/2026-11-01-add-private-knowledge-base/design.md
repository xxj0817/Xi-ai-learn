# Design

## Context

现有出题链路已经具备「研究 → 出题 → 引证」三层：`ResearchService` 负责收集来源（用户资料、Tavily 网页），`SourceCollector` 负责去重/截断/编号，`QuizService` 负责出题与引证校验。异步任务层（`QuizTaskWorker`）与前端轮询已稳定运行。

本次要在这条链路上增加第三类证据：用户自己的文档。约束条件：

- `QuizTaskStage` 是前端 `Record<QuizTaskStage, string>` 的键，新增阶段会破坏前端类型
- `ResearchService` 用 `_has_web_sources()` 判定「Agent 是否成功」，只命中知识库时会被误判为失败
- 研究缓存 key 当前为「输入 + 地区 + 用户资料」，不含文档范围会串数据
- 现有 313 项测试必须保持绿色，所有既有接口响应结构不能变

## Goals / Non-Goals

**Goals:**

- 用户上传 PDF / Word / Markdown / TXT 或粘贴文本后，能建立按用户隔离的可检索知识库
- 出题时知识库与网页作为并列数据源交给研究 Agent 自主选择
- 知识库来源与网页来源共用同一套编号与引证规则，前端能展示来源类型
- 全部为增量：不改变既有请求/响应契约，未配置嵌入凭据时知识库整体降级

**Non-Goals:**

- 视频输入（需要 ASR，本期不做）
- 文档级权限共享、团队知识库、文档版本管理
- 上传后的异步解析任务队列（当前为请求内同步完成 + 超时保护）
- 重排序模型 / 混合检索（BM25 + 向量）
- H5 端的文件选择（仅小程序支持上传，H5 走粘贴文本）

## Decisions

### 1. 向量库按用户划分 collection

`collection = kb_user_{user_id}`，metadata 携带 `doc_id / title / source_type / chunk_index`。

理由：隔离最彻底，检索无需跨用户过滤；即使过滤条件写错也不会串到别人数据。替代方案是单 collection + `where user_id`，查询更集中但任何一处漏写 filter 就是数据泄露。

### 2. 元数据落 MySQL，向量落 Chroma

`knowledge_documents` 表存 doc_id / user_id / title / 类型 / 大小 / 分块数 / 状态。列表、配额、删除都不需要扫向量库。MySQL 不可用时降级为进程内存储（仅开发便利）。

### 3. 自定义 `KnowledgeEmbeddings` 包一层 `OpenAIEmbeddings`

百炼两个硬约束必须显式处理：

- 单次请求最多 10 条输入 → `chunk_size=10`，并再包一层显式分批，避免上层调用方绕过
- 不接受 OpenAI 的 base64 输入格式 → `check_embedding_ctx_length=False`，否则会走 tiktoken + base64 编码

用 `OpenAIEmbeddings` 而不是自研 HTTP 客户端，是因为它就是官方 OpenAI 兼容集成，`base_url` / `dimensions` / 代理 / 超时都能复用现成参数。

### 4. 用 `pypdf` + `docx2txt`，不用 `langchain_community` 加载器

LangChain 官方文档现行示例已改为直接用 `pypdf.PdfReader` 构造 `Document`，`langchain_community` 的 `PyPDFLoader` / `Docx2txtLoader` 属于 legacy 包，会额外拉入数百 MB 依赖。功能等价，依赖更轻。

### 5. 知识库作为工具交给 Agent，而不是硬编码先查知识库

`knowledge_search` 与 Tavily 工具一起进 `create_agent`，符合「多源检索由 Agent 判断」的产品预期。但纯 Agent 驱动有漏洞：Agent 可能漏调、可能因为边界限制提前结束、离线 Mock 模式根本没有 Agent。因此增加一道确定性兜底——只要知识库工具可用且尚无任何可核实来源，就补一次基于用户输入的库内检索。

这是「Agent 自主 + 兜底确定性」的组合，而不是二选一。

### 6. 复用 `SourceCollector`，只新增 origin

知识库分块以 `origin=knowledge` 进入现有候选池，编号、排序、去重、总字符预算全部复用。收益是引证校验逻辑零改动，题目仍能逐题引用 `S1..Sn`。

`finalize()` 的排序变为「用户资料 → 知识库 → 网页」，因为私有资料的可信度高于公开网页。

### 7. 不新增 `QuizTaskStage`

知识库检索发生在研究阶段内，复用 `researching` 阶段，前端 `Record<QuizTaskStage, string>` 不需要改动。代价是前端看不到「正在查知识库」的细分文案，收益是零破坏性。

### 8. 上传在请求内同步完成，加超时保护

解析 + 切分 + 向量化在 `asyncio.wait_for(timeout=KB_UPLOAD_TIMEOUT_SECONDS)` 内完成，CPU 密集部分丢到 `to_thread`。文档上限 10MB，典型耗时数秒，不值得为它引入第二个任务队列与状态轮询。失败时回滚（清向量 + 清文件），不留半成品。

## Risks / Trade-offs

- **网页噪音稀释私有资料**：Agent 可能同时联网，公开资料（例如其它公司的差旅标准）会进入资料块，理论上有被误用的风险。实测中题目只引用知识库来源，未发生串味；如需严格私有，可后续追加 `knowledge_only` 开关。
- **嵌入调用产生外部数据传输**：文档正文会发送给百炼向量化，需在文档与 UI 中明示；原文与向量只存在自己服务器上。
- **Chroma 单进程多实例风险**：同目录多个 `PersistentClient` 会冲突，用模块级缓存 + 锁保证单实例。
- **删除的最终一致性**：向量删除失败时仍会删除元数据并记日志，可能出现少量孤儿向量；不影响检索正确性（元数据已不可见），后续可加清理任务。
- **依赖体积**：`chromadb` 会带入 `onnxruntime` / `tokenizers`，安装体积增加约 200MB+。
- **维度绑定**：collection 的向量维度取决于 `EMBEDDING_DIMENSIONS`，中途改维度需要重建知识库（当前无自动迁移）。
