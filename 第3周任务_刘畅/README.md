# 云购生活新零售 — 企业级数据仓库与经营分析可视化系统（第 3 周实训仓库）

主题：数据分析 · 预测建模 · AI 协同（NL2SQL）

本周目标：把数仓从 DWD 明细层推进到 DWS/ADS 汇总层，算出可复核的经营 KPI；
用 Python 完成趋势分析与 GMV 预测建模；接入大模型构建 NL2SQL 问数接口；
全程用 Git Fork / PR / Code Review 流程协同开发。

## 交付物对照（《03_第3周任务书》五、交付物清单）

| 序号 | 交付物 | 位置 | 状态 |
|---|---|---|---|
| 1 | DWS/ADS 建模与 ETL 脚本 | `sql/dws/`、`sql/ads/`、`etl/` | ✅ 按天/周/月 × 品类/门店/渠道汇总；五链路口径一致性校验通过 |
| 2 | KPI 指标结果表 | `output/kpi_summary.csv`、`ads_kpi_*.csv`、`ads_category_top10.csv`（含品类销售占比）、`ads_user_tier_summary.csv` | ✅ |
| 3 | 预测建模分析报告 | `docs/预测建模分析报告.docx`、`output/forecast_*`、`output/trend_*` | ✅ 含趋势分解/环比/模型评估与边界说明 |
| 4 | NL2SQL 接口代码 | `llm/`、`nl2sql/` | ✅ 含 Prompt 与 Schema 抽取 |
| 5 | AI 智能洞察 / 反思文档 | `insight/insight.py`、`output/ai_insight_report.md`、`docs/AI应用反思.md` | ✅ 异常归因 + 自动报告 + 数字验证 |
| 6 | PR / Code Review / Issue 记录 | `docs/Git协同记录.md`、git log | ✅ |

## 目录结构

```
yunmall-dw/
├── config/metrics.md       # 指标定义文档（口径唯一来源，先定口径再算数）
├── sql/                    # Hive 正式版 DDL/DML（上线口径）
│   ├── ddl/                # DWD 建表
│   ├── dws/                # DWS 汇总层（天/周 × 门店/品类/渠道）
│   ├── ads/                # ADS 应用层（KPI / TopN / 渠道 / 用户分层）
│   └── local/              # SQLite 兼容版（本地执行，逻辑与 Hive 版一一对应）
├── etl/
│   ├── gen_dwd.py          # DWD 明细数据生成（教学环境模拟源系统）
│   └── run_etl.py          # 步骤1-2 执行器：DWS/ADS 建模 + KPI 计算 + 口径校验
├── forecast/
│   ├── read_hive.py        # 步骤3-①：pyhive 读取（无 Hive 时回退本地 SQLite）
│   ├── forecast_gmv.py     # 步骤3-②：特征工程 + 线性回归 + 评估 + 滚动预测
│   └── trend_analysis.py   # 步骤3-补充：趋势分解 + 移动平均 + 月/周环比
├── llm/
│   ├── client.py           # 步骤4：大模型接入（.env 密钥管理 / OpenAI 兼容协议）
│   └── test_api.py         # 验收：回复可达 + .env 已忽略
├── nl2sql/
│   ├── schema.py           # 步骤5-①：Schema 抽取（带口径注释）
│   ├── prompts.py          # 步骤5-②：Prompt 设计（系统约束 + few-shot）
│   ├── chain.py            # 步骤5-③：链路（含 LangChain LCEL 适配器）+ SQL 白名单校验 + 执行
│   ├── cli.py              # 演示入口，5 个示例问题
│   └── test_langchain.py   # LangChain 链路自检（无需 Key）
├── insight/
│   └── insight.py          # 子任务5：AI 异常归因 + 自动经营报告 + 数字验证
├── output/                 # 结果产物（CSV / 图 / 演示记录）
└── docs/                   # 分析报告 / 协同记录 / AI 应用反思
```

## 快速开始

```bash
pip install -r requirements.txt

# 1. 生成 DWD 明细数据（本地模拟 Hive 源表）
python etl/gen_dwd.py

# 2. DWS/ADS 建模 + KPI 计算 + 口径一致性校验
python etl/run_etl.py

# 3. GMV 趋势分析与预测建模
python forecast/forecast_gmv.py

# 4. 大模型接入自检
python llm/test_api.py

# 5. NL2SQL 问答演示
python nl2sql/cli.py

# 6. LangChain 链路自检（构建 + Prompt 渲染 + 校验/执行）
python nl2sql/test_langchain.py

# 7. 趋势分解与环比分析（子任务 2 补充）
python forecast/trend_analysis.py

# 8. AI 智能洞察与自动报告（子任务 5；未配 Key 走离线模板）
python insight/insight.py
```

大模型（可选）：复制 `.env.example` 为 `.env`，填入 `DEEPSEEK_API_KEY`。
未配置时自动进入 offline-mock 模式，链路照常跑通。

## 本地执行与 Hive 的关系

教学环境没有 Hive 集群，用 SQLite 做同构替身：

| Hive | 本地 SQLite |
|---|---|
| `dwd.dwd_order` | `dwd_order` |
| `dws.dws_order_store_day` | `dws_order_store_day` |
| `ads.ads_kpi_day` | `ads_kpi_day` |

`sql/` 下的 Hive 版 SQL 是**上线口径的唯一事实源**；`sql/local/` 逻辑与之一一对应，
仅去掉库前缀。日期函数差异（`date('now',...)` vs `add_months`）在 README 与
`nl2sql/schema.py` 中已注明。

## 口径速查

GMV = 有效订单（status='paid'）实付金额之和；客单价 = GMV ÷ 去重订单量；
复购率 = 下单≥2 次用户数 ÷ 下单用户数。完整口径见 `config/metrics.md`。

## 上线计划

- 第 1 步：DWS/ADS SQL 在测试集群回放，比对本地 SQLite 结果；
- 第 2 步：NL2SQL 接口挂载内部网关，仅开放只读账号；
- 第 3 步：看板接入 ads_kpi_day / ads_category_top10。

## 协作规范

1. 分支命名：`feature/模块名`、`fix/问题描述`；
2. 提交信息遵循 Conventional Commits（feat/fix/docs/test 前缀）；
3. 合入 main 必须发起 PR，且至少 1 人 Code Review 通过；
4. 涉及口径变更的提交，必须同步修改 config/metrics.md 并在 PR 中说明。
