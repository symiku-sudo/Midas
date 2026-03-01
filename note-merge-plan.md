# 现存笔记智能合并功能计划（MVP）

## 目标
1. 在“已保存笔记”中发现可合并候选。
2. 支持人工确认后合并。
3. 合并默认非破坏性（保留原笔记，生成新合并笔记）。

## 范围（MVP）
1. 先做同源合并：B站和B站合并、小红书和小红书合并。
2. 暂不做跨源（B站+小红书）自动合并。
3. 合并入口放在笔记库页。
4. Android 入口按钮仅用于“合并笔记”，不承载编辑/删除/搬运等其他操作。

## 技术方案
1. 候选召回：
   - 基于标题+正文的关键词重叠、编辑距离、时间邻近、摘要相似度做初筛。
2. 智能判定：
   - 用 LLM 对候选对做“是否重复/是否互补/建议合并方式”判定并打分。
3. 合并生成：
   - LLM 输出结构化合并稿（去重、冲突标注、保留来源链接）。
4. 可追溯：
   - 记录 `merge_history`（源 `note_id` 列表、策略、时间、操作者）。
5. 可回退：
   - 基于 `merge_history` 支持按最近一次合并结果执行回退（恢复到合并前状态）。

### 模型与调用策略（MVP 默认）
1. 候选召回阶段使用规则打分（同源前提下）：
   - `keyword_overlap`：标题+正文关键词重叠率（0~1）。
   - `title_similarity`：标题相似度（Jaccard + 编辑距离归一化，0~1）。
   - `time_proximity`：时间邻近分（0~1，7 天内线性衰减）。
   - `summary_similarity`：摘要向量/文本相似度（0~1；无向量时退化为 BM25/TF-IDF 相似度）。
2. 召回总分：
   - `recall_score = 0.35*keyword_overlap + 0.25*title_similarity + 0.20*time_proximity + 0.20*summary_similarity`。
3. LLM 判定与生成统一复用现有 `llm.model`（默认 `gemini-3-flash-preview`，可配置）：
   - 判定输出固定 JSON：`decision`、`merge_intent_score`、`complementary_score`、`reason_codes`、`field_conflicts`。
   - 生成输出固定 JSON：`merged_title`、`merged_content`、`merged_tags`、`source_refs`、`conflict_markers`。
4. 失败降级：
   - LLM 超时（沿用 `llm.timeout_seconds`）或 JSON 解析失败时，不自动提交，候选降级为“仅人工确认”。
   - 降级记录 `fallback_reason` 到 `merge_history`，便于审计。

### 阈值与决策分层（MVP 默认）
1. 候选入池阈值：`recall_score >= 0.55`。
2. 高优先级建议：`merge_intent_score >= 0.85` 且 `complementary_score >= 0.40`。
3. 需人工谨慎确认：`0.65 <= merge_intent_score < 0.85`。
4. 默认不建议合并：`merge_intent_score < 0.65`（列表中折叠或不展示）。
5. 冲突提示阈值：
   - 字段相似度 `< 0.70` 标记普通冲突。
   - 字段相似度 `< 0.40` 标记高冲突，预览页默认展开并要求用户显式确认。
6. Android 侧仍保持“人工确认后 commit”，MVP 不做全自动合并落库。

### 字段冲突合并规则（MVP 默认）
1. `title`：
   - 默认选 `merge_intent_score` 更高来源的标题；若两侧评分差 `< 0.05`，选最近更新时间版本。
   - 保留 `title_candidates` 供预览页切换。
2. `content`：
   - 句子级去重（hash + 顺序保留），相同句仅保留一次。
   - 冲突段落按来源分块并加来源标记，用户可在预览中二选一或并存。
3. `summary`：
   - 默认取信息量更高版本（长度更长且实体覆盖更多），另一版本写入 `alt_summary`。
4. `tags`：
   - 并集去重，保留来源顺序；同义标签按归一化字典合并（如“AI/人工智能”）。
5. `source_refs`（来源链接/来源 note_id）：
   - 全量保留并去重，不允许被覆盖删除。
6. `metadata`（发布时间、作者、平台字段）：
   - 时间冲突默认保留最早发布时间，同时记录最近更新时间；
   - 平台特有字段冲突时不丢弃，按 `metadata_variants` 保存。
7. 每次字段决策都写入 `merge_history.field_decisions`，用于回退精确恢复。

## 后端实施步骤
1. 新增合并服务层（候选召回、LLM判定、合并生成）。
2. 新增表 `note_merge_history`（SQLite）。
3. 新增 API：
   - `POST /api/notes/merge/suggest`：返回候选组+置信度。
   - `POST /api/notes/merge/preview`：返回合并预览稿。
   - `POST /api/notes/merge/commit`：落库合并结果并写历史。
   - `POST /api/notes/merge/rollback`：按 `merge_id` 回退到合并前状态。
4. 保持统一响应协议 `ok/code/message/data/request_id`。
5. 更新接口文档与 README。
6. `note_merge_history` 至少包含：`merge_id`、`source_note_ids`、`merged_note_id`、`field_decisions`、`fallback_reason`、`rollback_of`、`operator`、`created_at`。
7. `rollback` 校验规则：
   - 仅允许回退“最近一次成功合并”；
   - 若该合并结果已参与后续合并，则拒绝一键回退并返回可识别错误码；
   - 回退成功后追加一条历史记录，不覆盖原 `merge_history`。

## Android 实施步骤
1. 笔记库页新增“合并笔记”按钮（唯一入口），点击后进入候选列表。
2. 候选列表页展示分组、相似度、命中原因；仅提供“预览合并”动作。
3. 预览页展示原文对比与合并稿，用户仅可“确认合并”或“返回”。
4. 合并成功后刷新笔记库并展示来源关系，同时在结果页提供“回退此次合并”按钮。
5. 用户对合并效果不满意时，可在结果页触发回退；回退成功后恢复到合并前状态并提示可重新发起合并。
6. 交互状态机：`Idle -> Suggesting -> Preview -> Committing -> Success/Failed -> Rollback(optional)`。

## 测试计划
1. 单测：候选召回排序、阈值、LLM输出解析失败兜底。
2. API测试：`suggest/preview/commit` 正常流和异常流。
3. 回归：现有笔记增删查、关键词检索不回归。
4. UI测试：候选展示、预览、确认合并、回退流程。
5. API测试：`rollback` 成功回退、重复回退、无效 `merge_id`、权限/状态异常。
6. 阈值边界测试：`0.55/0.65/0.85` 边界分数行为一致且可解释。
7. 字段冲突测试：`title/content/tags/metadata` 冲突时预览与落库结果一致。
8. 审计测试：`merge_history.field_decisions` 与回退恢复结果一一对应。

## DoD
1. 可从现有笔记中稳定产出候选。
2. 用户可预览并确认合并。
3. 合并结果可追溯，原笔记默认保留。
4. 用户可在合并后按效果触发回退，且回退结果可追溯。
5. 文档、测试、接口契约齐全。

## 待确认决策
1. 合并后是否默认保留原笔记（推荐：保留）。
2. 候选阈值偏保守还是偏激进（推荐：保守，减少误合并）。
3. MVP 是否只做同源合并（推荐：是）。
4. 回退入口时效（推荐：默认不设时效，但仅允许对最近一次合并执行一键回退）。
5. 是否在 MVP 引入 embedding 服务（推荐：先可选，缺失时自动降级到纯规则召回）。
6. 高冲突字段是否允许“一键并存”（推荐：允许，但必须在预览页可见且可改）。
