# 第 4 周：可视化实现 + 项目部署

本目录是《云购生活新零售》课程第 4 周部署操作手册的**完整执行产出**。
所有数据来自真实 Hive 表（非模拟），前 3 周项目位于 `E:/项目实训`。

## 目录结构

```
第4周/
├── README.md                    # 本文件
├── .env.example                 # 密钥模板（密钥不落盘）
├── docker-compose.yml           # 一键部署编排（Superset + App）
├── sql/
│   ├── 01_ads_build.sql         # ADS 指标层（6 张表，已执行）
│   └── 02_optimization.sql      # 查询优化：分区裁剪 + 大 key 加盐
├── superset/
│   ├── Dockerfile               # 定制镜像（补 Hive/MySQL 驱动）
│   ├── init_superset.sh         # 初始化脚本（修正手册命令顺序）
│   └── README.md                # Superset 连接配置说明
├── app/
│   ├── export_data.py           # Hive ADS → JSON
│   ├── sync_to_mysql.py         # JSON → MySQL ydsh_ads
│   ├── nl2sql.py                # NL2SQL 引擎（意图识别 → SQL → 结果）
│   ├── streamlit_app.py         # Streamlit 问答应用
│   ├── superset_register_db.py  # 注册 Superset 数据源（CLI）
│   ├── benchmark.py             # 查询压测脚本
│   └── Dockerfile               # App 镜像
├── echarts/
│   ├── index.html               # 大屏（在线版，需 HTTP 服务）
│   ├── index_standalone.html    # 大屏（离线版，双击可开）★推荐
│   ├── echarts.min.js           # 本地 ECharts 库
│   ├── build_standalone.py      # 生成离线版
│   ├── serve.py                 # 启动大屏 HTTP 服务
│   └── data/                    # 6 个指标 JSON
└── docs/
    ├── 第4周执行报告.md          # 完整执行记录
    ├── 交付物核对清单.md         # 5 项交付物核对
    └── benchmark_result.md      # 真实压测结果
```

## 快速验证

### 1. 数据大屏（最简单）
直接双击 `echarts/index_standalone.html`，用浏览器打开即可看到完整大屏（离线可用）。

### 2. 查询压测结果
查看 `docs/benchmark_result.md`（分区裁剪提速 59%，ADS 预聚合提速 71%）。

### 3. NL2SQL 问答引擎（命令行）
```bash
cd app
python3 nl2sql.py "总体GMV是多少" "品类销售排行" "浙江省销售额是多少"
```

### 4. Streamlit 问答应用
```bash
pip install streamlit pandas
cd app
streamlit run streamlit_app.py
```

### 5. Superset（当前已在运行）
访问 http://localhost:8088，账号 admin / admin。
数据源 `ydsh_ads`（MySQL）已注册，含 6 张 ADS 指标表。

### 6. Docker 一键部署
```bash
cd 第4周
cp .env.example .env      # 按需修改密钥
docker compose up -d
```
访问 Superset http://localhost:8088 、App http://localhost:8501 。

## 数据刷新流程

ADS 指标变化时，按顺序刷新各层数据：
```bash
cd app
python3 export_data.py        # Hive ADS → echarts/data/*.json
python3 sync_to_mysql.py      # JSON → MySQL ydsh_ads（Superset 数据源）
cd ../echarts
python3 build_standalone.py   # 重新生成离线大屏
```

## 手册纠错记录

1. **Superset 初始化顺序**：手册写 `create-admin → db upgrade → init`，空库会失败；
   正确为 `db upgrade → create-admin → init`。
2. **容器内网络**：手册连接串用 `localhost`，容器内指向自身；
   应使用 `host.docker.internal` 或 Docker 网桥网关（本环境 IPv6 解析有问题，用 `172.17.0.1`）。
3. **缺失 ADS 层**：手册步骤 2 要求选 ADS 表，但项目只做到 DWD 层，本执行补齐了 ADS 层。
4. **MySQL 端口**：手册写 3306，实际环境 MySQL 映射在 3307。
