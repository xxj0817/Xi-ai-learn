# OpenSpec 超简单上手指南（本项目专用）

> 官方仓库：<https://github.com/Fission-AI/OpenSpec> · 官方文档：<https://openspec.dev/docs>
> 本文所有命令都来自官方文档，并适配了本仓库（`d:\VScodeProject\Xi-ai-learn`）的实际情况。

---

## 0. 一句话搞懂 OpenSpec 是干什么的

**它让你和 AI 先把"要做什么"写成几页纸，确认没问题了再让它写代码。**

每扩展一个功能，就是一个 **change（变更）**，对应一个文件夹，里面有 4 个文件：

| 文件 | 作用 | 谁写 |
|---|---|---|
| `proposal.md` | 为什么要做、做什么、不做什么 | AI 写，你审 |
| `specs/` | 需求条目 + 可验证的场景（这次新增/修改了什么） | AI 写，你审 |
| `design.md` | 技术方案（改哪些文件、怎么实现） | AI 写，你审 |
| `tasks.md` | 可勾选的实施清单 | AI 写，你审 |

功能做完后**归档**，这次的规格会自动合并进主规格库 `openspec/specs/`。
所以规格是**慢慢长出来的**，不需要一上来给整个项目补文档。

---

## 1. ⚠️ 最容易踩的坑：命令要在两个地方敲

90% 的新手卡在这里。

| 命令长什么样 | 在哪儿敲 | 举例 |
|---|---|---|
| `openspec xxx` | **终端**（VS Code 底部「终端」面板 / PowerShell） | `openspec init` |
| `/opsx-xxx` | **Copilot 聊天框**（就是平时让它写代码的那个框） | `/opsx-propose add-wrong-book` |

> 本项目用的是 VS Code + GitHub Copilot，所以聊天框里的写法是 **`/opsx-propose`**（横杠）。
> 官方文档里写的 `/opsx:propose`（冒号）是通用写法，Copilot 里换成横杠即可。

---

## 2. 安装 OpenSpec（整台电脑只做一次）

先确认 Node 版本（要求 ≥ 20.19，你当前是 24.15，✅ 满足）：

```powershell
node -v
```

然后二选一安装：

**方式 A：npm（简单，推荐）**

```powershell
npm install -g @fission-ai/openspec@latest
```

**方式 B：官方单文件安装脚本（npm 装不上时用）**

```powershell
irm https://raw.githubusercontent.com/Fission-AI/OpenSpec/main/scripts/binary/install.ps1 | iex
```

验证装好了：

```powershell
openspec --version
```

> 如果提示「openspec 不是可识别的命令」：**关掉终端重新开一个**（PATH 要重新加载）。

---

## 3. 初始化（每个项目只做一次）

```powershell
cd d:\VScodeProject\Xi-ai-learn
openspec init --tools github-copilot
```

跑完会生成：

```
openspec/
├── specs/                 # 主规格库（系统当前行为的唯一真相，初始是空的）
├── changes/               # 待办变更，一个功能一个文件夹
├── changes/archive/       # 已归档的历史变更
└── config.yaml            # 项目配置

.github/prompts/
├── opsx-propose.prompt.md
├── opsx-explore.prompt.md
├── opsx-apply.prompt.md
├── opsx-archive.prompt.md
├── opsx-update.prompt.md
└── opsx-sync.prompt.md
```

`.github/prompts/` 里这 6 个文件，就是聊天框里 `/` 后面能选到的命令。**别删它们**。

### 3.1 告诉 OpenSpec 这个项目长什么样（强烈建议做）

编辑 `openspec/config.yaml`，把下面的内容填进 `context` 字段（或用编辑器打开后追加）。填了它，AI 写方案时就不会给你套 Spring Boot 模板：

```yaml
context: |
  Xi-ai-learn 是一个「AI 闯关学习」小程序。
  - 前端：Taro 4.3 + React 18 + TypeScript，状态管理 Zustand，代码在 frontend/src/
    - 页面在 pages/，通用组件在 components/，接口封装在 services/api.ts
    - 样式用 SCSS + src/styles/tokens.scss 里的设计令牌，UI 必须严格对齐 prototype/ 原型图
  - 后端：Python 3.12 + FastAPI + Pydantic v2 + LangChain，代码在 backend/app/
    - 路由在 api/v1/routes/，业务在 services/，数据访问在 repositories/，模型在 models/
    - 数据库 MySQL，建表脚本在 backend/migrations/
    - 测试用 pytest，先写测试再实现
  - 所有产出（proposal/specs/design/tasks）都用中文书写
```

> 想让规格自动用中文写，也可以初始化时加 `--language chinese`（`openspec init --tools github-copilot --language chinese`）；CLI 若不认这个值，用上面 `context` 里那行「都用中文书写」同样有效。

### 3.2 openspec/ 要提交到 git

它是项目资产，和代码一起版本管理。本项目 `.gitignore` 没有忽略它，直接 `git add openspec .github/prompts` 即可。

---

## 4. 日常只用 4 个命令

```text
/opsx-explore  ──►  /opsx-propose  ──►  /opsx-apply  ──►  /opsx-archive
  （可选，想不清时用）      写方案给你审          写代码            归档合并规格
```

### 4.1 `/opsx-explore` —— 先聊聊，不动代码（可选）

**什么时候用**：需求还很模糊，或者你不想让 AI 乱猜现有代码结构。

```text
/opsx-explore 我想加一个错题本，但不确定现在答题记录是怎么存的
```

AI 会去读 `backend/app/repositories/quiz_repository.py`、`answer_records` 表结构等，然后告诉你现状和几种做法。**这个阶段不会写任何代码、不会建任何文件。**

### 4.2 `/opsx-propose` —— 生成方案（核心）

**什么时候用**：想清楚要做什么了。

```text
/opsx-propose add-wrong-book
```

AI 会创建 `openspec/changes/add-wrong-book/`，写入 proposal / specs / design / tasks 四个文件，然后停下等你审。

**你必须做的一件事**：打开 `proposal.md` 和 `tasks.md` **读一遍**。写错了现在改最便宜（用 `/opsx-update add-wrong-book` 让它改），代码写出来再改就贵了。

### 4.3 `/opsx-apply` —— 让它按清单写代码

```text
/opsx-apply add-wrong-book
```

AI 会照着 `tasks.md` 一条条实现，写完后把对应的复选框 `- [ ]` 改成 `- [x]`。

**注意**：这一步会真的改你的项目代码。建议先 `git status` 确认工作区干净，这样出问题能一键回滚（`git checkout -- .`）。

### 4.4 `/opsx-archive` —— 归档（收尾）

```text
/opsx-archive add-wrong-book
```

它会把这次的规格合并进 `openspec/specs/`，然后把整个 change 文件夹移到 `openspec/changes/archive/日期-名字/`。

---

## 5. 实战演示：给本项目加「错题本」

照抄这 5 步就能跑通一遍。假设你想加的功能是：**答错的题自动进错题本，可以在「我的」里复习**。

### 第 1 步：确认工作区干净

```powershell
cd d:\VScodeProject\Xi-ai-learn
git status
```

（有未提交改动也没关系，但建议先提交，方便回滚。）

### 第 2 步：在 Copilot 聊天框里先探个底

```text
/opsx-explore 我想加错题本功能，帮我看看现在答题记录是怎么存的，最省事的实现路径是什么
```

看完它的分析，你觉得 OK 再往下。

### 第 3 步：生成方案

```text
/opsx-propose add-wrong-book
```

然后打开这三个文件过一遍：

- `openspec/changes/add-wrong-book/proposal.md` —— 范围对不对？有没有多做？
- `openspec/changes/add-wrong-book/specs/*/spec.md` —— 需求场景写得对不对？
- `openspec/changes/add-wrong-book/tasks.md` —— 任务拆得合理吗？

不满意就让它改：

```text
/opsx-update add-wrong-book 我不要前端新页面，先在「我的」页里加个入口就行
```

### 第 4 步：校验格式（终端）

```powershell
openspec validate add-wrong-book
```

不通过说明规格写法有问题（缺场景、格式不对），让它改到通过为止。

### 第 5 步：写代码 → 跑测试 → 归档

```text
/opsx-apply add-wrong-book
```

写完后自己验一遍（本项目规矩）：

```powershell
cd backend; .\.venv\Scripts\python.exe -m pytest -q
cd ..\frontend; npx tsc --noEmit
```

都绿了就归档：

```text
/opsx-archive add-wrong-book
```

然后照常提交代码 + `openspec/` 目录。

---

## 6. 终端里的常用查询命令

这些都在**终端**敲，用来查看状态，不会改代码。

| 命令 | 干什么 |
|---|---|
| `openspec list` | 列出所有进行中的变更和已有规格 |
| `openspec show add-wrong-book` | 在终端里查看某个变更的内容 |
| `openspec status add-wrong-book` | 看这个变更的 4 个文件写了几个、还差几个 |
| `openspec validate --all` | 校验全部变更和规格的格式 |
| `openspec view` | 打开一个可视化看板（浏览器里看更直观） |
| `openspec archive add-wrong-book -y` | 不用聊天框，直接在终端归档（`-y` 跳过确认） |
| `openspec update` | 升级 CLI 后，重新生成 `.github/prompts/` 里的命令 |
| `openspec config profile` | 切换到「扩展工作流」（新手先别动） |

---

## 7. 五条铁律（照做不会翻车）

1. **不要一上来给整个项目补规格。**
   只在真正要改的地方写规格。补全量文档会立刻过期，纯浪费时间。

2. **一个 change 只干一件事。**
   `add-wrong-book` 就只做错题本。想顺手改 UI 风格？另开一个 `polish-home-ui`。

3. **`/opsx-propose` 之后一定先读 proposal 和 tasks。**
   这是 OpenSpec 唯一真正值钱的地方——让 AI 在写代码前暴露它的理解偏差。

4. **`/opsx-apply` 之前确保 git 干净。**
   出问题可以 `git checkout -- .` 一键回滚，代价最小。

5. **apply 时想改需求，别直接改代码，用 `/opsx-update`。**
   否则规格和代码就脱节了，下次 AI 读规格会读错。

---

## 8. 常见问题

**Q：`openspec` 命令找不到？**
A：关掉终端重开。还不行就看 `npm bin -g` 的输出目录有没有在 PATH 里。

**Q：聊天框里敲 `/` 看不到 `opsx-propose`？**
A：三步排查——① 确认 `openspec init` 跑过且 `.github/prompts/opsx-*.prompt.md` 存在；② 重启 VS Code；③ 确认用的是 Copilot Chat（不是其他扩展的聊天框）。

**Q：想让产出全部用中文？**
A：见 3.1 的 `config.yaml` → `context` 里写「所有产出都用中文书写」。

**Q：OpenSpec 会自动帮我 git commit 吗？**
A：不会。它只管规划和实现，提交还是你自己 `git add` / `git commit`。

**Q：`openspec/` 会不会很长很占地方？**
A：很短。一个 change 一般 4 个小 Markdown 文件，比一份 PRD 轻得多。

**Q：文档里提到的 stores / worksets / schemas / 扩展 profile 要装吗？**
A：**统统不用管。** 那些是团队多仓库、自定义流程用的高级功能。你现在只用 4 个命令就够。

**Q：能不能不装，直接用？**
A：不能，`openspec` CLI 是必须的（负责初始化目录和格式校验），聊天命令依赖它的产出。

---

## 9. 一页速查表

```text
# 一次性准备
npm install -g @fission-ai/openspec@latest
cd d:\VScodeProject\Xi-ai-learn
openspec init --tools github-copilot

# 每个新功能（在 Copilot 聊天框）
/opsx-explore   <想不清时先聊>
/opsx-propose   <功能名>
/opsx-update    <功能名> <要改的地方>
/opsx-apply     <功能名>
/opsx-archive   <功能名>

# 随时查状态（在终端）
openspec list
openspec status <功能名>
openspec validate --all
openspec view
```
