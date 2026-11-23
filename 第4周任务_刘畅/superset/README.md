# Superset 连接配置（手册步骤 1）

## 1. 启动与初始化

```bash
# 用官方镜像启动（已验证可行）
docker run -d --name bi-superset -p 8088:8088 \
  -e SUPERSET_SECRET_KEY="your_random_secret" \
  --add-host=host.docker.internal:host-gateway \
  apache/superset:4.1.1

# 初始化（顺序已修正！原手册顺序错误）
docker exec bi-superset superset db upgrade
docker exec bi-superset superset fab create-admin \
  --username admin --firstname Admin --lastname User \
  --email admin@example.com --password admin
docker exec bi-superset superset init
```

访问 http://localhost:8088 ，用 admin/admin 登录。

> **手册纠错**：原手册先 `create-admin` 再 `db upgrade`，空库状态下创建用户会失败。
> 正确顺序为 `db upgrade → create-admin → init`。

## 2. 容器内网络说明

Superset 容器内的 `localhost` 指向容器自身，无法访问宿主机上的 Hive/MySQL。
必须使用 `host.docker.internal`（启动时的 `--add-host` 参数已配置）连接宿主机服务。

## 3. 添加数据库连接

在 Superset UI：**Data → Database Connections → + Database**

### 3.1 连接 ADS 指标库（推荐，数据已预聚合）

由于 Hive Python 驱动在官方镜像中默认缺失，最快方式是先把 ADS 指标表导出到
 MySQL 的 `ydsh_ads` 库，再用 MySQL 连接（驱动 `pymysql` 通常可用）：

```
mysql+pymysql://root:root@host.docker.internal:3307/ydsh_ads
```

### 3.2 连接 Hive（需安装驱动）

官方镜像默认无 Hive 驱动，需基于提供的 `Dockerfile` 构建定制镜像：

```bash
docker build -t superset-hive ./superset
```

连接串：

```
hive://hive@host.docker.internal:10000/default
```

驱动要求（Dockerfile 已包含）：`pyhive`、`thrift`、`thrift-sasl`、`pymysql`。

## 4. 制作仪表板（手册步骤 2）

1. **创建数据集**：Data → Datasets → + Dataset，选择 `ads_order_overview` / `ads_category_sales` 等表
2. **制作 5 类图表**：
   - 销售趋势折线图：`ads_order_overview`（stat_month × gmv）
   - 品类柱状图：`ads_category_sales`（category × net_sales）
   - 区域地图：`ads_region_sales`（province × gmv）
   - 支付占比饼图：`ads_paytype_share`（pay_type × orders）
   - TopN 排行表：`ads_store_rank`
3. **组合 Dashboard** 并添加日期/品类筛选器，设置图表联动

验证通过标准：图表数据正确、筛选器可联动。
