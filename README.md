# 鱼皮 AI 闯关学习小程序

把一句话变成一组可玩的闯关题：AI 生成题目 → 即时判题与讲解 → 通关复盘报告。

当前仓库已完成 **MVP 核心闭环**：Taro 微信小程序前端 + FastAPI/LangChain 后端。

## 目录结构

```text
backend/                     FastAPI 后端
  app/
    api/v1/routes/           健康检查、题库生成、报告生成接口
    core/                    配置、日志、异常、限流
    llm/                     LangChain 调用层 + Mock Provider
    models/                  API 领域模型（Pydantic v2）
    prompts/                 版本化 Prompt
    services/                出题、判分、报告服务
    utils/                   文本清洗、内容过滤、ID 生成
  tests/                     pytest 测试（含真实 API 集成测试）
  requirements.txt
  .env.example               复制为 .env 后使用

frontend/                    Taro 4.3 小程序前端
  config/                    Taro 构建配置（weapp / h5）
  src/
    pages/                   首页、闯关页、报告页、题库、我的
    components/              图标、圆环、选项、导航等基础组件
    services/                请求封装与 API
    store/                   Zustand + 本地存储
    styles/                  设计令牌（严格对齐原型）
    utils/                   SVG、判题、设备信息
  project.config.json        微信开发者工具项目配置

docs/                        需求分析与方案设计、OpenSpec 使用教程
prototype/                   高保真原型（UI 基线）
```

## 技术栈

- 前端：Taro 4.3.1、React 18、TypeScript、Sass、Zustand 5
- 后端：Python 3.12、FastAPI 0.162、Pydantic v2、LangChain 1.4、langchain-openai 1.7、langchain-tavily 0.2.18
- 模型：DeepSeek `deepseek-flash`（OpenAI 兼容接口，默认关闭 thinking 模式）
- 测试：pytest 9 + httpx

## 快速开始

### 1. 后端

```bash
cd backend
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements-dev.txt --default-index https://pypi.org/simple
copy .env.example .env
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

默认使用 `LLM_PROVIDER=mock`，无需 API Key 即可跑通完整闭环。
接入真实模型时修改 `backend/.env`：

```dotenv
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-xxxx
DEEPSEEK_MODEL=deepseek-flash
DEEPSEEK_THINKING_ENABLED=false
```

> DeepSeek 已不再提供方案文档中写的 `deepseek-chat`，当前官方模型为 `deepseek-flash` / `deepseek-v4-pro`；
> 模型默认开启 thinking 模式且会忽略 temperature/top_p，因此项目默认显式关闭 thinking。
>
> 网络：程序默认**不读取**系统 `HTTP_PROXY`/`HTTPS_PROXY`，避免代理关闭后残留的环境变量导致连接失败。
> 需要走代理时设置 `DEEPSEEK_PROXY_URL=http://127.0.0.1:7890`，或设 `DEEPSEEK_TRUST_ENV_PROXY=true` 复用系统代理。

接口文档：<http://127.0.0.1:8000/docs>

### 2. 前端

```bash
cd frontend
npm install
npm run dev:weapp   # 输出 dist/，用微信开发者工具打开 frontend 目录
npm run dev:h5      # H5 预览 http://localhost:10086
```

微信开发者工具设置：

- 项目目录选择 `frontend/`（`miniprogramRoot` 指向 `dist/`）
- 详情 → 本地设置 → 勾选“不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书”
- 本地开发时后端地址为 `http://127.0.0.1:8000`，见 `src/services/request.ts`

> 构建约定：
> 1. `config/index.ts` 已关闭 `prebundle`（依赖预编译），否则小程序端会出现
>    `Cannot access 'c' before initialization`（`taro.js` 分块 TDZ）导致白屏。
> 2. 同一时间只能有一个构建进程写入产物目录；多个 `dev:weapp` 并发会互相覆盖。
> 3. H5 与小程序产物分目录：`build:h5` → `dist-h5/`，`build:weapp` → `dist/`。
>    如果 H5 产物写进了 `dist/`，模拟器会报 `根据 miniprogramRoot 指定的目录 dist/ 未找到 app.json`。
> 4. 重新 `build:weapp` 后模拟器**可能仍在跑旧的编译缓存**，表现为文案/样式没更新，或白屏但控制台不报错。
>    按顺序尝试：开发者工具点「编译」按钮 → 关闭项目重新打开 → 彻底退出开发者工具后重新启动。
>    用命令行重新拉起可确保加载最新产物（以实际安装路径为准）：
>
>    ```bash
>    "<开发者工具安装目录>/cli.bat" auto --project frontend --auto-port 9420
>    ```
>
> 5. 上述步骤都无效时，再尝试关闭「设置 → 通用设置 → GPU 加速」。

## API

统一响应：`{ "code": 0, "message": "ok", "data": ... }`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/health` | 健康检查，返回当前 Provider 与模型 |
| POST | `/api/v1/quiz/tasks` | 创建出题任务，立即返回任务状态（HTTP 202） |
| GET | `/api/v1/quiz/tasks/{task_id}` | 轮询任务状态，成功后返回完整题库 |
| POST | `/api/v1/quiz/generate` | 同步生成 3~8 道闯关题（兼容脚本与旧客户端，交互流程请用任务接口） |
| POST | `/api/v1/report/generate` | 生成复盘报告（服务端权威判分） |

错误码：

| code | HTTP | 含义 |
| --- | --- | --- |
| 4001 | 400 | 参数或答题记录不合法 |
| 4002 | 502 | AI 生成失败（含重试后仍失败） |
| 4003 | 422 | 内容命中敏感词或提示词注入 |
| 4041 | 404 | 生成任务不存在、已过期或不属于当前用户 |
| 4290 | 429 | 触发限流 |
| 4040 | 404 | 接口不存在 |
| 5040 | - | 出题任务整体超时，见轮询响应的 `error.code` |

## 异步出题任务（创建 + 轮询）

出题包含联网检索与多轮模型调用，耗时通常 10~30 秒且波动较大。交互流程统一使用「异步任务 + 轮询」，避免 HTTP 长连接超时：

1. `POST /api/v1/quiz/tasks` 校验参数、落库任务并立即返回 `202`，此时 `status=pending`。
2. 前端按响应里的 `poll_interval_ms`（默认 2000ms）轮询 `GET /api/v1/quiz/tasks/{task_id}`。
3. `status=succeeded` 时响应直接带上完整题库 `quiz`，前端进入闯关页；`status=failed` 时读取 `error.code` / `error.message`。

任务状态与阶段：

| status | 含义 |
| --- | --- |
| `pending` | 已创建，排队等待执行 |
| `running` | 执行中，配合 `stage` 展示进度 |
| `succeeded` | 完成，`quiz` 可用 |
| `failed` | 失败，`error` 说明原因 |

`stage` 依次为 `queued → researching → generating → validating → saving → completed`，`progress` 由阶段推导（0/10/35/70/90/100），前端无需自己计算。

创建任务示例：

```json
{
  "user_input": "Harness Engineering 是什么",
  "question_count": 5,
  "difficulty": "mixed"
}
```

轮询响应示例：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "task_id": "task_9f1c...",
    "status": "running",
    "stage": "generating",
    "progress": 35,
    "poll_interval_ms": 2000,
    "quiz": null,
    "error": null,
    "created_at": "2026-10-28T15:30:00Z",
    "updated_at": "2026-10-28T15:30:06Z"
  }
}
```

实现要点：

- 任务表 `quiz_tasks` 由 `backend/migrations/004_quiz_tasks.sql` 创建；MySQL 未启用时自动降级为进程内任务存储，功能仍可用
- 后台并发由 `QUIZ_TASK_MAX_CONCURRENCY` 控制，超出后任务保持 `pending` 排队；单任务超时由 `QUIZ_TASK_TIMEOUT_SECONDS` 控制
- 服务重启时，遗留的 `pending` / `running` 任务会被标记为失败，前端不会无限轮询
- 轮询读取接口不占用限流额度，避免 2 秒一次的轮询触发 `4290`
- 前端会把 `task_id` 写入本地缓存，切后台或重新进入小程序后可继续轮询同一个任务


## 联网检索增强出题

出题前会先运行一个独立的研究 Agent：它拿着官方 `TavilySearch` / `TavilyExtract` 工具，自主决定搜不搜、搜几次、用摘要还是整页正文、查本地还是全球资料，然后把带编号的来源交给大模型出题。

- **工具套件**：`tavily_search_quick_local` / `deep_local` / `quick_global` / `deep_global` + `tavily_extract_page`
  - quick：只返回摘要，适合简单概念；deep：返回整页正文，适合新概念或复杂主题
  - local / global：按用户地区选择；Tavily 的 `country` 只支持国家级，城市语义需要写进查询词
- **网址输入**：用户可以直接把网页链接粘贴到输入框，系统会先提取整页内容；如果输入只有一个网址，学习主题由页面内容推导，而不是 URL 字符串
- **用户资料优先**：`source_text` 与成功提取的网页正文合计 ≥ 800 字时，跳过研究 Agent，直接基于用户资料出题
- **引证**：每道题带 `citations`（如 `["S1"]`），题库带 `sources` 与 `grounding`；引证不合法会重试，重试后仍不合格标记为「部分核实」
- **静默降级**：未配置 Tavily Key、Agent 超时、检索无结果时，自动退回纯模型出题，不向用户报错

启用方式（`backend/.env`）：

```dotenv
WEB_SEARCH_ENABLED=true
WEB_SEARCH_PROVIDER=tavily
TAVILY_API_KEY=tvly-xxxx
# 需要代理时填写；留空表示直连
TAVILY_PROXY_URL=
```

**数据流向与成本**：

- 用户显式提供的网址会发送给 Tavily Extract 抓取正文；粘贴的 `source_text` 不会发送给检索服务
- 主题会用于生成搜索查询并发送给 Tavily，请不要在输入中放密钥、身份证号等敏感信息
- Tavily `basic` 约 1 credit/次，`advanced` 约 2 credits/次；研究结果默认缓存 30 分钟，减少重复消耗
- 未配置 Key 时不会发起任何外部检索请求，`grounding.status` 为 `model_only`

接口新增字段（均为可选，旧客户端不受影响）：

- 请求：`source_text`、`source_urls`、`region`、`locale`
- 响应：`sources`、`grounding`、题目级 `citations`

## 测试

```bash
cd backend
.venv\Scripts\python.exe -m pytest -q
```

- 313 项单元/接口/集成测试覆盖：出题校验、重试与兜底、内容过滤、服务端判分、报告聚合、限流、Prompt 契约、模板花括号、DeepSeek 结构化输出降级与代理策略、Tavily 工具套件、研究 Agent、引证校验与来源持久化、异步任务状态机与轮询
- 覆盖率 96%（`pytest --cov=app`）
- 集成测试 `tests/test_deepseek_integration.py` 需要设置 `DEEPSEEK_API_KEY` 才会执行，否则自动跳过

前端验证：

```bash
cd frontend
npx tsc --noEmit
npm run build:weapp
npm run build:h5
```

## MVP 范围说明

已实现：

- 首页输入 → AI 出题 → 逐题作答 → 即时正误反馈与解析 → 通关报告
- 单选 / 多选 / 判断题；多选需先勾选再提交
- 金币与经验值展示、未完成关卡续答、本地题库与学习统计
- 空态、加载态、失败提示、限流与敏感词过滤

原型适配说明：

- 原型中的手机状态栏（09:41 / 4G / 电量）属于设计外壳，小程序内改用系统状态栏安全区 + 自定义导航行
- 原型首页 Tab 为“闯关/题库/勋章”、报告页为“闯关/题库/我的”，已统一为“闯关/题库/我的”
- 原型缺少多选与判断题样式，已复用同一套选项组件扩展（多选带勾选与提交按钮，判断为正确/错误两项）
- 原型首页展示的已完成卡片与未完成关卡（602 金币、RAG 基础概念、数学闯关 60% 等）以“示例关卡”形式内置，可正常打开作答，数据存本地
- 原型中的手机状态栏（09:41 / 4G / 电量）属于设计外壳，小程序内使用系统状态栏 + 安全区占位
- “生成海报”按钮保留原型位置，MVP 阶段提示后续开放，未接入 Canvas 海报与微信登录

后续规划：微信登录、Canvas 分享海报、后端持久化、多源输入（文档/网页/视频）、RAG 私有知识库、错题复习与图表分析。

## 原型

直接用浏览器打开：

```text
prototype/Copilot生成的原型图/01-core-flow.html
prototype/Copilot生成的原型图/03-design-system-board.html
```
