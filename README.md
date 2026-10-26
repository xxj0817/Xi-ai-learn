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

docs/                        需求分析与方案设计
prototype/                   高保真原型（UI 基线）
```

## 技术栈

- 前端：Taro 4.3.1、React 18、TypeScript、Sass、Zustand 5
- 后端：Python 3.12、FastAPI 0.162、Pydantic v2、LangChain 1.4、langchain-openai 1.7
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
> 2. 同一时间只能有一个构建进程写入 `dist/`；多个 `dev:weapp` 并发会互相覆盖产物。
> 3. 若仿真器白屏但控制台无报错，先点「编译」，再尝试关闭「设置 → 通用设置 → GPU 加速」。

## API

统一响应：`{ "code": 0, "message": "ok", "data": ... }`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/health` | 健康检查，返回当前 Provider 与模型 |
| POST | `/api/v1/quiz/generate` | 生成 3~8 道闯关题（默认 5 题） |
| POST | `/api/v1/report/generate` | 生成复盘报告（服务端权威判分） |

错误码：

| code | HTTP | 含义 |
| --- | --- | --- |
| 4001 | 400 | 参数或答题记录不合法 |
| 4002 | 502 | AI 生成失败（含重试后仍失败） |
| 4003 | 422 | 内容命中敏感词或提示词注入 |
| 4290 | 429 | 触发限流 |
| 4040 | 404 | 接口不存在 |

## 测试

```bash
cd backend
.venv\Scripts\python.exe -m pytest -q
```

- 92 项单元/接口测试覆盖：出题校验、重试与兜底、内容过滤、服务端判分、报告聚合、限流、Prompt 契约、模板花括号、DeepSeek 结构化输出降级与代理策略
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
