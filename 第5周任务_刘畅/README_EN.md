# Yundu Life Retail — Enterprise Data Warehouse & Business Analytics System

> A complete, end-to-end data warehouse and business analytics platform built for a new-retail enterprise.
> From raw CSV files to a one-click-deployed decision-support system.

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Hive](https://img.shields.io/badge/Hive-4.0-orange.svg)](https://hive.apache.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/license-For%20learning%20only-green.svg)](LICENSE)

---

## Overview

This project solves four real business pain points for a new-retail company operating an online store and 60 offline branches:

1. **Scattered data** — orders, users, products and behavior spread across multiple source CSV files;
2. **Inconsistent metrics** — different teams define GMV, AOV and repurchase rate differently;
3. **Slow analytics** — reports depended on manual Excel aggregation;
4. **No forecasting** — no sales trend prediction for stocking and marketing decisions.

Over five weeks we built a unified, end-to-end analytics platform where every core metric shares one single definition.

## Architecture

```
Raw CSV (6 files)
      │ ingest
      ▼
  ODS  ── raw source mirror, fully traceable
      │ clean (5 types of dirty data)
      ▼
  DWD  ── star-schema detail, one-order-one-item grain
      │ aggregate (day/week/month × store/category/channel)
      ▼
  DWS  ── light aggregation for multi-dimensional analysis
      │
      ▼
  ADS  ── 6 application metric tables
      │
      ├──► Forecasting   (trend decomposition + linear regression)
      ├──► NL2SQL        (7 natural-language business questions)
      └──► Visualization (Superset / ECharts / Streamlit)
                 │
                 ▼
         Docker Compose one-click deployment
```

## Features

- **Layered warehouse**: ODS → DWD → DWS → ADS, each layer固化 a single metric definition;
- **Data quality governance**: detect and clean 5 types of dirty data, with a before/after comparison report;
- **Unified metric definitions**: GMV / orders / AOV / active users / repurchase rate — one source of truth;
- **GMV forecasting**: additive trend decomposition + linear regression, MAPE 16.35% vs baselines 34.55% / 53.93%;
- **NL2SQL question answering**: natural language → intent → SQL (whitelist-validated) → read-only execution;
- **Multi-end visualization**: Superset dashboards, ECharts big screen (online + offline), Streamlit chat app;
- **One-click deployment**: Docker Compose with health checks; secrets injected via `.env`, never committed;
- **Query optimization**: partition pruning (59% faster), ADS pre-aggregation (71% faster).

## Quick Start

### Option A — One-click with Docker (recommended)

```bash
cp .env.example .env          # fill in API keys and DB passwords
docker compose up -d
# Superset  http://localhost:8088   (admin / admin)
# Streamlit http://localhost:8501
# Big screen: double-click echarts/index_standalone.html (works offline)
```

### Option B — Local SQLite fallback (no Hive cluster needed)

```bash
pip install -r requirements.txt
python etl/gen_dwd.py             # generate local DWD detail
python etl/run_etl.py             # DWS/ADS + KPI + consistency checks
python forecast/forecast_gmv.py   # trend + regression + rolling forecast
python nl2sql/cli.py              # 5 demo questions
python insight/insight.py         # AI insight + auto report
```

## Tech Stack

| Layer | Technology |
|---|---|
| Data ingestion | Python, CSV |
| Warehouse | Hive 4.0 (Tez), MySQL 8.0 |
| Local fallback | SQLite (isomorphic substitute) |
| Orchestration | Shell, Docker Compose |
| Forecasting | Python (scikit-learn, linear regression) |
| NL2SQL | LangChain, OpenAI-compatible API |
| BI & Visualization | Superset 4.1.1, ECharts, Streamlit |
| Security | `.env` injection, SQL whitelist, read-only DB account |

## Project Structure

```
.
├── sql/                  ODS → DWD → DWS → ADS SQL scripts
├── etl/                  DWD generator + DWS/ADS executor
├── forecast/             trend analysis + GMV forecasting
├── llm/  nl2sql/         LLM client + NL2SQL chain
├── insight/              AI anomaly attribution + auto report
├── app/                  data export / MySQL sync / NL2SQL / Streamlit
├── superset/             custom Dockerfile + init scripts
├── echarts/              dashboards (online + offline editions)
├── docs/                 requirements / cleaning / architecture / deployment / API docs
├── README.md             Chinese documentation entry
└── README_EN.md          this file
```

## Metric Definitions

All metrics follow one source of truth (`docs/metrics.md` v1.2):

| Metric | Definition |
|---|---|
| GMV | `sum(pay_amount) where status='paid'` (actual payment, refunds excluded) |
| Orders | `count(distinct order_id)` |
| AOV | `GMV ÷ orders` (aggregate first, then divide — never row-wise average) |
| Active users | `count(distinct user_id) where status='paid'` |
| Repurchase rate | users with ≥2 orders ÷ ordering users (window must be stated) |

## Data Notes

Two data sources exist in this teaching project and must not be mixed:

- **Real Hive tables** (final reporting basis): GMV 39,708,649.13 CNY / 15,000 orders / 2024 full year;
- **Local SQLite teaching substitute** (week 3 fallback): GMV 9,051,397.85 CNY / 116,192 orders / ~180 days — used only for forecasting and NL2SQL self-checks within its own consistent scope.

All external reporting and dashboards use the real Hive figures.

## Team

- **Liu Chang** — project integration, data warehouse, forecasting, documentation & defense
- Course: Enterprise Project Practicum · Data Warehouse & Data Analytics track

## License

For academic/learning use only.
