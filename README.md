# 第 2 周 · 企业级数据仓库与经营分析可视化系统

> 云购生活新零售企业 · 数据清洗进阶 + Hive 四层数仓建模 + 探索性分析
> 环境：Hive 4.0.0（Tez）· Derby Metastore · Docker · beeline　**已全部实跑验证（2026-11-04）**
> 前一阶段：第 1 周完成 ODS 贴源层与数据质量预评估

---

## 一、目录结构

```
第二周/
├── README.md                      本文件：执行指南 + 交付物清单 + 与手册差异汇总
├── sql/
│   ├── clean/                     第 2 周清洗层（步骤 1~4）
│   │   ├── 00_init.sql            建库 + 会话参数 + ODS 就绪检查
│   │   ├── 01_enum_standard.sql   枚举标准化（4 个视图 + 取值分布基线）
│   │   ├── 02_abnormal_format.sql 异常值 / 格式标准化（4 个视图）
│   │   ├── 03_split_merge.sql     字段拆分合并 + 去重落地（dwd_user / dwd_order_tmp）
│   │   └── 04_quality_report.sql  数据质量对比报告（五类脏数据 before/after）
│   ├── dwd/                       第 2 周建模层（步骤 5~7）
│   │   ├── 10_ddl_dim.sql         维度表 DDL：dim_user / dim_product / dim_store / dim_date
│   │   ├── 11_ddl_fact.sql        事实表 DDL：dwd_order / dwd_order_item / dwd_user_behavior
│   │   ├── 12_etl_dim.sql         维度表加载（含日期维度生成）
│   │   └── 13_etl_fact.sql        事实表动态分区加载 + 6 组验收校验
│   └── ads/
│       └── 20_eda.sql             探索性分析（12 组查询，步骤 8 + H5 判定）
├── docs/
│   ├── 数仓架构设计文档.md         分层架构、维度建模、存储策略、与手册差异说明
│   ├── 数据质量对比报告.md         五类脏数据判定规则、前后对比、枚举映射总表
│   ├── 探索性分析简报.md           指标口径、7 个分析专题、6 条假设判定
│   └── 第2周AI协同日志.md          AI 协同记录、产出清单、反思总结
├── pdf/                           四份文档的排版稿（Chrome 打印，图表已渲染为矢量图）
└── logs/                          全部 10 个脚本的原始/清洗后执行日志
```

---

## 二、执行顺序（严格串行，不可跳步）

```bash
# 方式一：在容器内执行（本机即按此方式验证）
bash hr.sh sql/clean/00_init.sql
bash hr.sh sql/clean/01_enum_standard.sql
bash hr.sh sql/clean/02_abnormal_format.sql
bash hr.sh sql/clean/03_split_merge.sql
bash hr.sh sql/clean/04_quality_report.sql
bash hr.sh sql/dwd/10_ddl_dim.sql
bash hr.sh sql/dwd/11_ddl_fact.sql
bash hr.sh sql/dwd/12_etl_dim.sql
bash hr.sh sql/dwd/13_etl_fact.sql
bash hr.sh sql/ads/20_eda.sql

# 方式二：宿主机 beeline 直连（需自行安装 beeline）
beeline -u jdbc:hive2://localhost:10000 -f sql/clean/00_init.sql
# ……其余同上
```

`hr.sh` 是本周的执行封装：把 SQL 拷进容器、用 beeline 执行、过滤日志噪声、把结果落到 `logs/<脚本名>.log`。同时通过 `--hiveconf` 抬高 Tez 计数器上限（否则多分支 union 会直接失败）。

**为什么必须串行**：02 依赖 01 的视图，03 依赖 02 的视图，13 依赖 03 的表与 12 的维度表。任何一步跳过，下游都会因"表/视图不存在"直接失败——这比跑出错误数据好，因为报错能立刻发现。

**可重复执行**：所有 DDL 用 `drop table if exists`，所有加载用 `insert overwrite`，重跑任意次结果一致。

---

## 三、本周交付物核对清单（对应手册第四部分）

| 序号 | 交付物 | 对应文件 | 状态 | 验收方式 |
|---|---|---|---|---|
| 1 | 枚举 / 异常 / 格式清洗脚本 | `sql/clean/01` ~ `03` | ✅ 已实跑通过 | `dwd_order_tmp` = **15,000**，去重 600，时间戳 100% 解析 |
| 2 | 数据质量对比报告 | `docs/数据质量对比报告.md` + `04_quality_report.sql` | ✅ 已实跑填入 | 12 项检查中 11 项 after_cnt = 0，email 保留 193（预期） |
| 3 | 数仓架构设计文档 | `docs/数仓架构设计文档.md` | ✅ 已完成（含实跑记录） | 四层职责、总线矩阵、第九节实跑验证 |
| 4 | DWD 建模与 ETL 脚本 | `sql/dwd/10` ~ `13` | ✅ 已实跑通过 | 外键完整性 4 项全 0；GMV 一致 |
| 5 | 探索性分析简报 | `docs/探索性分析简报.md` + `sql/ads/20_eda.sql` | ✅ 已实跑填入 | 指标卡已填，6 条假设全部判定 |
| + | 第 2 周 AI 协同日志（第 1 周惯例） | `docs/第2周AI协同日志.md` | ✅ 已完成 | 7 条真实协同记录 + 产出清单 + 反思 |
| + | 全部文档排版稿 | `pdf/*.pdf`（4 份） | ✅ 已生成 | mermaid 图已渲染为矢量图，中文排版 A4 |

> 本周边界：所有数字均为 SQL 实跑输出，执行日志在 `logs/` 下（每步一份）。没有任何一处估算值。

---

## 四、与手册的差异汇总

实现时发现部署手册存在 10 处时序、粒度、语法或口径问题，逐条对照见 `docs/数仓架构设计文档.md` 第八节。最关键的三条：

| 编号 | 问题 | 后果 | 本实现 |
|---|---|---|---|
| D2 | 步骤 8 用 `dwd_order.product_id` 关联商品维度，但订单表建表语句无此字段 | 直接报错；若强行加字段会导致订单行膨胀、GMV 翻倍 | 新增 `dwd_order_item` 明细事实表，品类分析走明细粒度 |
| D1 | 步骤 3 从步骤 6 才创建的 `dwd_order` 取数 | 先读后建，脚本无法按序执行 | 改为从 `v_order_clean` 视图生成 |
| D9 | 步骤 1~3 从 ODS 出发但无去重环节 | 600 行重复订单导致 GMV 被重复计算 | 03 脚本补 `row_number()` 去重，15600 → 15000 |

其余 7 条（`percentile` 语法不兼容、枚举字段只写了 2 个、只有 `select` 没有落地语句、修复率口径、`distinct` 收敛标准 2~4 与 `order_status` 五值冲突、"约 900"与实测 6 万行级/6,338 字段级不符等）见架构文档第八节 D3~D10。

**除手册本身的问题外，实跑还暴露了 6 个脚本侧的坑**（字段名 `unit_price`、行为时间双格式、优惠截断用了原始金额、Hive 无 `sequence()`、366 分区 Derby 事务回滚、P99×3 阈值失效），逐条记录在 `docs/数仓架构设计文档.md` 第九节。这部分才是本周真正花时间的地方。

---

## 五、环境状态与前置依赖

| 项 | 要求 | 当前状态 |
|---|---|---|
| ODS 层 | 6 张外部表（1000 / 600 / 60 / 15600 / 37549 / 60000） | ✅ 已就绪，00 脚本复验一致 |
| Docker | Hive 4.0.0 + Derby Metastore | ✅ 三容器 Up（hive-server / hive-metastore / mysql） |
| HiveServer2 | `localhost:10000` 可连 | ✅ 可用 |
| 存储 | 容器内本地文件系统 `/opt/hive/data/warehouse` | ✅ 可写 |

**三个硬门槛实测结果（全部通过）**：

| 门槛 | 期望 | 实测 |
|---|---|---|
| `03` 3.1 行数守恒 | `dwd_order_tmp` = 15,000 | **15,000** |
| `04` 五类脏数据 | after_cnt 归零（email 除外） | **11/12 归零**，email 保留 193 |
| `13` 4.3 GMV 一致 | `dwd_order` = `dwd_order_tmp` | 均为 **39,708,649.13** |

> 首次启动 HiveServer2 时若容器反复 Exit(1) 并报 `HiveServer2 running as process 7`，是残留 pid 文件导致（容器重启后 PID 7 被新进程占用）：把 `/opt/hive/conf/hiveserver2.pid` 改成一个不存在的 PID 再启动即可。

---

## 六、Git 提交建议

```bash
git add sql/ docs/ README.md
git commit -m "feat(week2): 完成枚举/异常/格式清洗、四层数仓建模与探索性分析框架"
```

建议按脚本分组拆成 3 次提交，便于回溯：

1. `feat(clean): 枚举标准化与异常值/格式清洗脚本`
2. `feat(dwd): 维度建模 DDL 与事实表分区加载 ETL`
3. `docs(week2): 数据质量对比报告、数仓架构设计文档与探索性分析简报`
