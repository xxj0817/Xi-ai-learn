# 任务

## 1. 依赖与配置

- [x] 1.1 在 `backend/requirements.txt` 增加 `langchain-tavily==0.2.18` 与显式 `httpx==0.28.1`，运行 `backend/.venv/Scripts/python.exe -c "import langchain_tavily; print(langchain_tavily.__name__)"` 确认可导入
- [x] 1.2 在 `backend/app/core/config.py` 增加检索、工具预设、研究 Agent 与地区相关配置（`web_search_enabled`、`web_search_provider`、`tavily_api_key`、`tavily_base_url`、`tavily_proxy_url`、`tavily_trust_env_proxy`、`tavily_tool_timeout_seconds`、`tavily_search_result_max_chars`、`tavily_extract_result_max_chars`、`tavily_tool_total_max_chars`、`tavily_quick_max_results`、`tavily_quick_search_depth`、`tavily_deep_max_results`、`tavily_deep_search_depth`、`tavily_deep_include_raw_content`、`tavily_extract_format`、`tavily_extract_chunks_per_source`、`research_agent_timeout_seconds`、`research_agent_max_model_calls`、`research_agent_max_tool_calls`、`research_agent_recursion_limit`、`research_temperature`、`research_max_tokens`、`web_search_max_sources`、`source_snippet_max_chars`、`user_source_snippet_max_chars`、`source_total_max_chars`、`user_source_min_chars`、`user_source_text_max_chars`、`user_source_max_urls`、`web_search_cache_ttl_seconds`），并确认缺少 `TAVILY_API_KEY` 时 Settings 仍可正常构造
- [x] 1.3 在 `backend/tests/test_config.py` 补充默认值与边界校验测试，运行 `pytest tests/test_config.py -q` 通过
- [x] 1.4 在 `backend/.env.example` 增加上述变量及中文注释（含「未配置 Key 时自动降级」「用户提供的网址会发送给 Tavily Extract」「Tavily 只支持国家级 country」），逐行核对变量名与 `Settings` 字段一致

## 2. 官方 Tavily 工具套件与适配层

- [x] 2.1 新建 `backend/app/search/tavily_tools.py`：用 `TavilySearch` 创建 quick/deep × local/global 四个实例，用 `TavilyExtract` 创建整页提取实例；quick 不返回全文、deep 返回 `include_raw_content="markdown"`，结果条数分别为配置的 quick/deep 预设；无地区时只创建 global 两个。新增 `backend/tests/test_tavily_toolset.py` 断言工具名与预设参数（不发起真实请求），运行通过
- [x] 2.2 实现 `SourceCollector` 与 `StructuredTool` 薄包装：采集 search/extract 结果、按 URL 去重、长文优先、截断 `raw_content`、分配 `S1..Sn`。新增 `backend/tests/test_source_collector.py` 覆盖去重、长文优先、截断、编号与 `used_urls` 过滤，运行通过
- [x] 2.3 为包装层实现超时与代理路径：配置 `TAVILY_PROXY_URL` 或 `TAVILY_TRUST_ENV_PROXY` 时走官方 `_run` 的 `asyncio.to_thread` 同步路径，否则走原生 `_arun`；统一用 `asyncio.wait_for` 控制超时。用 Fake `BaseTool` 验证两条路径与超时行为，运行 `pytest tests/test_tavily_toolset.py -q` 通过
- [x] 2.4 为五个工具写入中文描述与使用场景（摘要 vs 全文、本地 vs 全球、整页提取），新增断言确认 Agent 可见的工具名、描述与参数 schema 符合设计，运行对应用例通过

## 3. 输入识别与地区解析

- [x] 3.1 实现 URL 识别与合并：从 `user_input` 提取 http/https 链接、去掉尾部中文标点、与 `source_urls` 合并去重、最多 3 条；URL-only 输入保留空主题供研究结果填充。新增 `backend/tests/test_url_detection.py` 覆盖 URL-only、URL+问题、多 URL、重复与非法 scheme，运行通过
- [x] 3.2 实现 `RegionResolver`：按 region/locale > `Accept-Language` 请求头 > 输入语言解析地区，映射到 Tavily 国家名；未知地区返回全球。新增 `backend/tests/test_region_resolver.py` 覆盖中文、英文、显式 region、未知地区与常见国家映射，运行通过
- [x] 3.3 扩展 `QuizGenerateRequest` 的 `source_text`（≤20000）、`source_urls`（≤3、http/https、≤2048、去重）、`region`/`locale`（≤32），并让路由把 `Accept-Language` 请求头传入服务层；在 `backend/tests/test_quiz_api.py` 增加合法与非法输入用例并运行通过

## 4. 研究 Agent 与研究服务

- [x] 4.1 在 `backend/app/llm/schemas.py` 增加 `ResearchBrief`（topic、used_urls、ambiguity_note），新建 `backend/app/prompts/research_prompt.py`（`research_prompt_v1`，包含工具选择规则、当前日期、地区说明、不可信数据约束），新增 `backend/tests/test_research_prompt.py` 并运行通过
- [x] 4.2 新建 `backend/app/llm/model_factory.py`（复用 DeepSeek `ChatOpenAI` 配置）与 `backend/app/agents/research_agent.py`：用 `create_agent` 装配工具、`system_prompt`、`response_format=ResearchBrief`、`ModelCallLimitMiddleware`、`ToolCallLimitMiddleware`。用 Fake 模型/工具验证 Agent 构建与结构化结果读取，不发起网络请求，运行通过
- [x] 4.3 实现 `backend/app/services/research_service.py`：先查缓存（缓存查询早于任何外部工具调用）、再预提取用户网址、用户资料 ≥800 字跳过 Agent、Agent 运行、`SourceCollector` 汇总、`used_urls` 过滤、按输入+地区+资料摘要写缓存。新增 `backend/tests/test_research_service.py` 覆盖这些分支并运行通过
- [x] 4.4 实现降级路径：无 Tavily Key、mock 模型（仍处理 source_text 与可用 URL 预提取，但不启动 Agent）、Agent 超时/轮次耗尽、无来源时回退一次直接 quick 搜索，仍无来源则返回空研究结果。新增对应用例，确认不向用户抛错，运行通过

## 5. 数据模型与 API 字段

- [x] 5.1 在 `backend/app/models/quiz.py` 增加 `SourceOrigin`、`QuizSource`、`GroundingStatus`、`QuizGrounding`，为 `Question` 增加默认空 `citations`，为 `Quiz` 增加默认 `sources` 与 `grounding`，运行现有 `pytest tests/test_quiz_validation.py tests/test_quiz_api.py -q` 确认旧行为不变
- [x] 5.2 在 `backend/app/models/user.py` 的 `QuizDetail` 增加可选 `sources` 与 `grounding`，运行 `pytest tests/test_history_api.py -q` 确认历史接口兼容
- [x] 5.3 在 `backend/tests/test_quiz_api.py` 增加响应断言：生成结果包含 `sources`、`grounding`、每题 `citations`，旧字段结构不变，运行通过

## 6. Prompt v2 与出题模型

- [x] 6.1 升级 `backend/app/prompts/quiz_prompt.py` 到 `quiz_prompt_v2`：支持 `sources`、`today`、资料分隔块、六条资料约束、引证要求与 strict 后缀，更新 `backend/tests/test_prompt_contract.py` 断言版本、资料块、引证字段与注入防护文本，运行通过
- [x] 6.2 扩展 `DeepSeekProvider.generate_quiz()` 与 `MockProvider.generate_quiz()` 接收 `sources` 并传入 Prompt（Mock 在有来源时为每题生成合法引证），运行 `pytest tests/test_deepseek_provider.py tests/test_mock_provider.py tests/test_prompt_template.py -q` 通过
- [x] 6.3 更新 `backend/app/services/quiz_normalizer.py`：清洗引证（大写、去重、剔除 `valid_source_ids` 之外的编号），保持其余结构校验不变，新增引证标准化用例并运行 `pytest tests/test_quiz_validation.py -q` 通过

## 7. 出题编排与降级

- [x] 7.1 改造 `QuizService.generate()`：调用 `ResearchService`、使用研究结果的主题与来源、引证缺失时重试、重试耗尽降级为 `partial`、无来源标记 `model_only`、按来源组合推导 `source_type`。新增 `backend/tests/test_quiz_grounding.py` 覆盖 grounded/partial/model_only/主题规范化/重试，运行通过
- [x] 7.2 在 `backend/app/main.py` 装配 `research_service`（支持测试注入），并在 `backend/app/api/v1/routes/quiz.py` 传入 `QuizService` 与 `Accept-Language` 请求头，运行 `pytest tests/test_quiz_api.py -q` 通过
- [x] 7.3 在 `backend/tests/test_quiz_api.py` 增加降级用例：无 Key、Agent 超时、研究无来源三种情况下接口仍返回 200 且 `grounding.status=model_only`，运行通过

## 8. 持久化与历史详情

- [x] 8.1 新增 `backend/migrations/003_quiz_grounding.sql`（仅 `CREATE TABLE IF NOT EXISTS`），在 `QuizRepositoryProtocol` 与 `QuizRepository` 实现 `save_grounding()`（`ON DUPLICATE KEY UPDATE`），并让 `get_quiz_detail()` 返回来源与核实状态；在 `backend/tests/conftest.py` 的 `FakeQuizRepository` 补齐方法
- [x] 8.2 在 `backend/tests/test_quiz_repository.py` 增加 `save_grounding` 幂等与详情读取用例（标记 `integration`），并在无 MySQL 环境下确认被跳过而非失败
- [x] 8.3 更新 `backend/app/services/history_service.py` 把来源与核实状态写入 `QuizDetail`（历史数据回退为空列表与 `model_only`），在 `backend/tests/test_history_api.py` 增加用例并运行通过

## 9. 文档同步

- [x] 9.1 在 `README.md` 增加「联网检索增强出题」小节：研究 Agent 能力、`TAVILY_API_KEY` 配置、工具套件、降级行为、第三方数据流向、成本提示与 Tavily 国家级限制，逐项核对与实现一致
- [x] 9.2 在 `docs/方案设计文档.md` 增补「研究 Agent + 官方 Tavily 工具」设计摘要，并更新生成题库接口的请求/响应示例（`source_text`、`source_urls`、`region`、`locale`、`sources`、`grounding`、`citations`），确认示例 JSON 可被 `python -m json.tool` 解析

## 10. 集成验证

- [x] 10.1 运行完整后端测试 `backend/.venv/Scripts/python.exe -m pytest -q`，确认全部通过且无新增跳过（基线 203 passed, 1 skipped）
- [x] 10.2 用 `TestClient` 冒烟一次「无检索凭据 → 出题成功 → 响应含 sources/grounding/citations 字段」的完整链路，并确认旧字段结构不变
- [x] 10.3 运行 `openspec validate add-web-grounded-quiz-generation --strict`，确认规格与任务清单无校验错误

## Workflow follow-up

- 在评审通过后归档本变更：`openspec archive add-web-grounded-quiz-generation`
- 归档后确认 `openspec/specs/knowledge-retrieval/` 与 `openspec/specs/quiz-generation/` 已生成主规格
