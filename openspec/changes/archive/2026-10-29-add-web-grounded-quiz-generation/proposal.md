# 提案：联网检索增强的 AI 出题

## Why

当前出题只依赖大模型的训练语料。遇到训练截止之后才出现、或训练语料覆盖不足的新概念时（例如 `Harness Engineering`），模型会张冠李戴，把另一个领域的知识当成正确答案，生成方向完全错误的题目与讲解。

这类错误无法靠调 Prompt 或换模型根治，必须让出题链路在生成前拿到可核实的最新外部知识。用户还可能直接粘贴一个网页链接，希望基于整页内容出题，因此只做关键词搜索不够，必须同时支持「按关键词搜索」和「按网址提取整页内容」。

## What Changes

- 接入 LangChain 官方 `langchain-tavily` 包提供的 `TavilySearch` 与 `TavilyExtract` 工具，交给一个独立的研究 Agent 自主决定调用哪个工具、传入什么参数。
- 向 Agent 提供多组官方工具实例：快速搜索（只返回摘要片段）、深度搜索（返回整页正文）、本地搜索（指定国家）、全球搜索，以及整页提取工具。因为 `max_results`、`include_raw_content`、`country` 在官方工具中只能实例化时设置，用多实例实现「动态调整结果条数 / 摘要或全文 / 国家范围」。
- 支持网页输入：从 `user_input` 与 `source_urls` 识别 http/https 链接，先用 `TavilyExtract` 预提取用户给的网址，保证用户资料优先；当输入只有一个网址时，从页面内容推导学习主题。
- 地区自适应：按「请求 region/locale > Accept-Language > 输入文本语言」解析用户地区，决定是否提供本地搜索工具；Tavily 只支持国家级 boost，不支持城市级过滤。
- Agent 输出结构化的研究结果（规范主题 + 实际采用的 URL），工具调用结果统一采集、去重、截断并编号为 `S1..Sn`。
- 出题 Prompt 升级到 `quiz_prompt_v2`：把参考资料注入上下文，要求题目只能依据资料、禁止混用同名概念、每题输出 `citations`。
- 严格校验引证：题目必须引用真实存在的来源编号，不合格时重试；重试后仍不合格则保留题目并把核实状态降级为「部分核实」。
- 为 Agent 设置模型调用次数、工具调用次数、递归步数与总超时边界；Agent 失败时先尝试一次直接快速搜索，仍失败则静默降级为纯模型出题。
- 新增 `quiz_grounding` 表持久化来源与核实状态；本次只交付后端与 API 字段，小程序页面不展示来源（前端后续单独接入）。

## Capabilities

### New Capabilities

- `knowledge-retrieval`：用官方 Tavily 工具与独立研究 Agent，为任意学习主题收集可核实、可追溯、可降级的外部知识；同时支持关键词搜索与整页提取，并按用户地区选择本地/全球资料。
- `quiz-generation`：基于研究结果生成闯关题，输出题库级来源与核实状态、题目级引证，并在引证不合法时重试或降级标记。

### Modified Capabilities

无。项目当前 `openspec/specs/` 为空，本变更首次建立上述两个能力。

## Impact

- 受影响接口：
  - `POST /api/v1/quiz/generate`：请求新增 `source_text`、`source_urls`、`region`、`locale`；响应新增 `sources`、`grounding`，题目新增 `citations`（均为新增字段，旧客户端可忽略）。
  - `GET /api/v1/user/quizzes/{quiz_id}`：详情新增可选 `sources`、`grounding`。
- 受影响代码：
  - 新增 `backend/app/search/`（官方工具套件、结果采集与截断适配层）。
  - 新增 `backend/app/agents/research_agent.py`、`app/services/research_service.py`、`app/prompts/research_prompt.py`。
  - 新增 `backend/app/llm/model_factory.py`（复用 DeepSeek 模型配置）。
  - 改动 `backend/app/prompts/quiz_prompt.py`（升级到 v2）。
  - 改动 `backend/app/services/quiz_service.py`、`quiz_normalizer.py`。
  - 改动 `backend/app/models/quiz.py`、`app/models/user.py`、`app/core/config.py`、`app/repositories/quiz_repository.py`。
  - 新增 `backend/migrations/003_quiz_grounding.sql`。
- 依赖：新增 `langchain-tavily==0.2.18`（已核实兼容 `langchain 1.4.7` / `langchain-core 1.7.0`）；`langgraph 1.2.17` 随 LangChain 已存在；显式声明 `httpx==0.28.1`。
- 配置：新增 `TAVILY_API_KEY`、`TAVILY_BASE_URL`、`TAVILY_PROXY_URL`、工具预设、Agent 边界、地区映射等环境变量。
- 不在本次范围：前端页面展示、RAG 向量库、PDF/Word/视频解析、多轮追问式消歧、城市级搜索过滤。
