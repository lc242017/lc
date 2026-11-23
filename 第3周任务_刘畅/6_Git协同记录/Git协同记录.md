# Git 协同记录（步骤 6 交付物）

仓库：`yunmall-dw`　分支模型：main + feature 双分支，PR 合入

## 1. 分支与提交记录

```
* 94c5263 (HEAD -> main) merge: 合并 feature/nl2sql，解决 README 冲突
|\
| * ecae76c docs(readme): 补充团队协作规范（feature 分支修改）
| * ed307fe test(nl2sql): 5 个示例问答演示记录
| * d0016e2 feat(nl2sql): 步骤4-5 大模型接入与 NL2SQL 查询接口
* | 227e4e1 docs(readme): 补充上线计划（main 分支修改）
|/
* dda1c4c feat(forecast): 步骤3 GMV 趋势分析与预测建模产物
* df55d2b docs(output): KPI 指标结果表与口径一致性校验产物
* b1ca2bd feat(dw): 步骤1-2 DWS/ADS 建模与 KPI 指标计算脚本
```

## 2. Pull Request 记录

### PR #1：feat(nl2sql): NL2SQL 查询接口

| 项 | 内容 |
|---|---|
| 源分支 | `feature/nl2sql` |
| 目标分支 | `main` |
| 变更范围 | `llm/`（2 文件）、`nl2sql/`（4 文件）、演示记录 2 份 |
| 关联 Issue | #3「经营分析需要一个自然语言问数入口」 |
| 自测 | `python llm/test_api.py` PASS；`python nl2sql/cli.py` 5 个示例全部返回正确结果 |

**PR 描述**：

> 按《第3周部署操作手册》步骤 4-5 实现：密钥放 `.env`（已被 `.gitignore` 忽略），
> 通过环境变量读取，无硬编码；大模型走 OpenAI 兼容协议最小化调用（temperature=0）；
> Schema 注入 Prompt 并附口径约定与 few-shot 示例；模型输出先过 `SQLGuard`
> 白名单（只允许单条 SELECT/WITH），再在连接级 `query_only` 双保险下执行。

### Code Review 评论记录

| # | 审阅人 | 评论 | 处理结果 |
|---|---|---|---|
| 1 | 张工（导师） | `SQLGuard` 要把 `pragma`、`attach` 也拦掉，防止本地执行时改变数据库状态 | ✅ 已补充 FORBIDDEN 正则 |
| 2 | 张工（导师） | 模型温度建议 0，保证同问题生成 SQL 可复现 | ✅ chat 默认 temperature=0 |
| 3 | 李工（队友） | 离线环境没 Key 跑不通怎么办？ | ✅ 增加 offline-mock 模板引擎，链路不中断 |
| 4 | 李工（队友） | 执行结果最好限行数，防止"查全表"刷屏 | ✅ execute_sql 限 200 行 |

### Review 意见修复提交

`d0016e2` 已包含全部 4 条 review 意见的修复，审阅结论：**Approved**，准予合入。

## 3. 合并冲突处理记录（手册验收点：能解决一次合并冲突）

- **冲突文件**：`README.md`
- **原因**：`feature/nl2sql` 在文末追加「协作规范」一节的同时，`main` 在同一位置追加了「上线计划」一节，自动合并失败（`CONFLICT (content): Merge conflict in README.md`）。
- **处理**：人工合并，两节内容均保留（先「上线计划」后「协作规范」），确认无冲突标记残留后完成合并提交 `94c5263`。
- **经验**：文档类冲突建议约定"分节编辑、不共用文末锚点"；代码冲突必须先理解双方意图再取/合。

## 4. Issue 记录

| 编号 | 标题 | 状态 | 说明 |
|---|---|---|---|
| #1 | GMV 口径是否含退款单 | ✅ Closed | 按 metrics.md v1.1 统一为实付口径，DWS/ADS 不再二次过滤 |
| #2 | 预测模型在大促日误差大 | ✅ Closed | 大促日作为模型不可识别事件单独拆解，报告注明适用边界 |
| #3 | 需要自然语言问数入口 | ✅ Closed | 由 PR #1（NL2SQL）解决 |

## 4.1 自检阶段补充提交（v1.0.1）

| 提交 | 说明 |
|---|---|
| `3f867e0` | feat(dw)：补齐渠道维度 `dws_channel_day` / `ads_channel_share`，一致性校验扩到四条链路 |
| `a98440f` | fix(nl2sql)：修复 LangChain `ChatPromptTemplate` 把 SYSTEM_PROMPT 中 JSON 花括号当模板变量的 `KeyError('"sql"')`，改用静态 `SystemMessage`；新增 `nl2sql/test_langchain.py` |

自检结论：手册 1.1 的「按天/品类/门店/渠道」四个维度已全部落地；LangChain 链路已实测
（链构建 → Prompt 渲染 → 共用 SQLGuard → 执行），未配置 Key 时仍以离线模式运行主链路。

## 4.2 v1.1：按任务书交付清单补齐（2026-11-13）

对照《03_第3周任务书》五、交付物清单自检，缺 3 项，已补：

| 提交 | 说明 |
|---|---|
| SQL 重构 | `sql/ddl|dws|ads` 四目录（任务书要求 sql/dws/、sql/ads/）；新增周维度、品类占比、用户价值分层 |
| 趋势分解 | `forecast/trend_analysis.py`：趋势/季节性/残差分解 + 月周环比 + 2σ 异常日（全部可归因营销事件） |
| AI 洞察 | `insight/insight.py`：z-score 异常检测 → LLM 归因（离线模板回退）→ 数字回查验证 60/60；`docs/AI应用反思.md` |

## 5. 团队分工

| 成员 | 职责 |
|---|---|
| 数据分析组 | DWS/ADS 建模、KPI 计算、口径文档 |
| 算法组 | 读取链路、特征工程、预测建模与评估 |
| AI 应用组 | 大模型接入、NL2SQL 链路、SQLGuard |
| 导师/审阅 | Code Review、口径把关、验收 |
