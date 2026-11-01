# 规格增量：闯关题生成（知识库扩展）

## ADDED Requirements

### Requirement: 出题支持知识库文档范围

出题请求 SHALL 接受可选的 `knowledge_doc_ids` 字段，用于指定本次出题参考的私有文档。字段缺省或为空时 SHALL 使用该用户全部已就绪文档；现有请求字段与响应结构 MUST 保持不变，旧客户端无需修改。

#### Scenario: 指定单份文档

- **WHEN** 请求携带一个已就绪的 `doc_id`
- **THEN** 出题只基于该文档及其它已启用的资料

#### Scenario: 未指定范围

- **WHEN** 请求不携带 `knowledge_doc_ids`
- **THEN** 系统使用该用户全部已就绪文档，且响应结构与非知识库场景一致

#### Scenario: 引用不属于自己的文档

- **WHEN** 请求中的 `doc_id` 不属于当前用户，或文档尚未就绪
- **THEN** 接口返回 400 参数错误，不进入出题流程

#### Scenario: 未登录却指定知识库

- **WHEN** 匿名请求携带 `knowledge_doc_ids`
- **THEN** 接口返回 400 参数错误并提示需要登录

### Requirement: 题库来源类型覆盖知识库

题库的 `source_type` SHALL 能反映知识库来源：仅知识库时为 `kb`，知识库与网页或用户资料混合时为 `mixed`，既有取值（`text` / `user` / `web` / `mixed`）的判定规则 MUST 保持不变。

#### Scenario: 仅知识库来源

- **WHEN** 研究结果只包含知识库分块
- **THEN** 题库 `source_type` 为 `kb`，`grounding.provider` 标识知识库

#### Scenario: 知识库与网页混合

- **WHEN** 研究结果同时包含知识库分块与网页结果
- **THEN** 题库 `source_type` 为 `mixed`

#### Scenario: 原有来源类型不变

- **WHEN** 请求未使用知识库，且只有网页来源
- **THEN** 题库 `source_type` 仍为 `web`，与引入知识库之前一致

### Requirement: 知识库出题的引证与降级

基于知识库出题时，每题 MUST 引用真实存在的来源编号；引证校验与重试规则 MUST 与既有行为一致。知识库不可用时 MUST 继续完成出题，MUST NOT 向用户返回知识库相关错误。

#### Scenario: 知识库来源被引证

- **WHEN** 题目依据知识库分块出题
- **THEN** 该题的 `citations` 指向知识库来源的编号

#### Scenario: 知识库不可用时降级

- **WHEN** 嵌入服务不可用或知识库检索失败，但请求指定了知识库范围
- **THEN** 用户仍收到结构完整的题库，`grounding.status` 不以「已核实」冒充知识库证据
