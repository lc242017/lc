# API 配置指南（API Configuration Guide）

> 项目：云购生活新零售——企业级数据仓库与经营分析可视化系统
> 版本：v1.0（第5周整合定稿）　维护人：刘畅　日期：2026-11-23
> 定位：密钥配置、接口说明、调用示例，覆盖大模型 API 与 NL2SQL 问数接口。

---

## 一、密钥配置

### 1.1 环境变量模板（`.env.example`）

```bash
# 大模型 API（OpenAI 兼容协议，如 DeepSeek）
DEEPSEEK_API_KEY=your_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

# 数据库（Superset / MySQL）
MYSQL_HOST=localhost
MYSQL_PORT=3307
MYSQL_USER=bi_readonly
MYSQL_PASSWORD=your_password_here
MYSQL_DB=ydsh_ads

# 数据源开关
USE_HIVE=0        # 1=实时查 Hive；0=基于 ADS 预计算数据
```

### 1.2 安全要求

- `.env` 必须加入 `.gitignore`，**密钥不落盘、不入 Git**；
- 数据库账号用只读账号 `bi_readonly`，仅授权 `select`；
- NL2SQL 走 SQL 白名单校验，禁止 DDL/DML；
- 对外汇报与答辩材料中不出现真实密钥。

## 二、接口说明

### 2.1 大模型接入（`llm/client.py`）

| 项 | 说明 |
|---|---|
| 协议 | OpenAI 兼容 `/chat/completions` |
| 配置 | 从 `.env` 读取 Key / Base URL / Model |
| 降级 | 未配置 Key 时自动进入 `offline-mock` 模式，链路照常跑通 |
| 自检 | `python llm/test_api.py`（验证回复可达 + `.env` 已忽略） |

### 2.2 NL2SQL 问数接口（`nl2sql/` 模块）

| 模块 | 职责 |
|---|---|
| `schema.py` | Schema 抽取（带口径注释，让模型理解表结构） |
| `prompts.py` | Prompt 设计（系统约束 + few-shot 示例） |
| `chain.py` | 链路编排（LangChain LCEL）+ SQL 白名单校验 + 执行 |
| `cli.py` | 演示入口，内置 5 个示例问题 |
| `test_langchain.py` | 自检（构建 + Prompt 渲染 + 校验/执行，无需 Key） |

**处理流程**：自然语言问题 → 意图识别 → Prompt + Schema → 大模型生成 SQL → 白名单校验 → 只读执行 → 结果返回。

### 2.3 应用内 NL2SQL（`app/nl2sql.py`）

基于 ADS 指标层的降级实现：中文意图识别 → SQL 生成 → 结果返回，无需大模型 API 即可运行；设 `USE_HIVE=1` 可切换实时查询 Hive。

## 三、调用示例

### 3.1 命令行问数

```bash
cd app
python3 nl2sql.py "总体GMV是多少" "品类销售排行" "浙江省销售额是多少"
```

### 3.2 支持的 7 类问题

| 问题类型 | 示例 | 命中数据表 |
|---|---|---|
| 总体指标 | 总体GMV是多少 | `ads_kpi` |
| 月度趋势 | 各月销售趋势 | `ads_kpi`（按月） |
| 品类排行 | 品类销售排行 | `ads_category_sales` |
| 区域销售 | 浙江省销售额 | `ads_region_sales` |
| 支付占比 | 各支付方式占比 | `ads_paytype_share` |
| 门店 Top | 门店销售前十 | `ads_store_rank` |
| 订单概况 | 订单总数/退款率 | `ads_order_overview` |

### 3.3 Python 调用

```python
from nl2sql.chain import build_chain
chain = build_chain()
result = chain.invoke("上个月GMV是多少")
print(result)   # {"sql": "...", "data": ..., "answer": "..."}
```

### 3.4 启动问答 Web 应用

```bash
pip install streamlit pandas
cd app
streamlit run streamlit_app.py     # http://localhost:8501
```

## 四、Superset 数据源配置

| 项 | 值 |
|---|---|
| 数据库类型 | MySQL |
| 连接串 | `mysql+pymysql://bi_readonly:***@172.17.0.1:3307/ydsh_ads` |
| 数据表 | `ads_kpi` / `ads_category_sales` / `ads_region_sales` 等 6 张 |
| 初始化顺序 | `db upgrade → create-admin → init`（手册顺序有误） |
| 容器内网络 | 用网桥网关 `172.17.0.1`，不用 `localhost` |

## 五、验证与排错

| 检查 | 方法 | 通过标准 |
|---|---|---|
| API 可达 | `python llm/test_api.py` | 返回非空回复 |
| 密钥安全 | `git check-ignore .env` | 有输出（已忽略） |
| 问数正确 | `python nl2sql/cli.py` | 5 示例问题正确 |
| 引擎自检 | `python nl2sql/test_langchain.py` | 无报错 |
| Web 应用 | `streamlit run streamlit_app.py` | 页面可访问、问答闭环 |

> 常见网络问题（pip / CDN 超时）与 Web UI 未在本机实测的说明，见 `04_部署手册.md` 第四节。
