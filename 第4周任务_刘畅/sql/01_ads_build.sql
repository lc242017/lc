-- ============================================
-- 第 4 周：ADS 应用层指标表建设
-- 数据源：ydsh_dwd.dwd_order（订单事实，15000 单，2024 全年）
--          dwd.dim_product / dwd.dim_store（维度表）
-- 用途：为 Superset 仪表板 / ECharts 大屏 / Streamlit 问答提供统一指标口径
-- 特性：STORED AS ORC（列式存储）+ 分区裁剪（stat_month）
-- ============================================

CREATE DATABASE IF NOT EXISTS ads;

-- --------------------------------------------
-- 1. ADS 订单概览宽表（按月分区）—— 核心汇总指标
-- --------------------------------------------
DROP TABLE IF EXISTS ads.ads_order_overview;
CREATE TABLE ads.ads_order_overview (
    stat_month        STRING  COMMENT '统计年月 yyyy-MM',
    gmv               DOUBLE  COMMENT '成交总额(GMV)=实付金额之和',
    orders            BIGINT  COMMENT '订单数',
    aov               DOUBLE  COMMENT '客单价=GMV/订单数',
    discount_total    DOUBLE  COMMENT '优惠总额',
    refund_orders     BIGINT  COMMENT '退款中订单数'
) COMMENT '订单概览月表' PARTITIONED BY (stat_year STRING) STORED AS ORC;

INSERT OVERWRITE TABLE ads.ads_order_overview PARTITION (stat_year)
SELECT stat_month,
       round(sum(pay_amount), 2)                                   AS gmv,
       count(DISTINCT order_id)                                    AS orders,
       round(sum(pay_amount) / count(DISTINCT order_id), 2)        AS aov,
       round(sum(total_amount - pay_amount), 2)                    AS discount_total,
       sum(CASE WHEN order_status = '退款中' THEN 1 ELSE 0 END)     AS refund_orders,
       stat_year
FROM ydsh_dwd.dwd_order
WHERE stat_date >= '2024-01-01'          -- 分区裁剪
GROUP BY stat_month, stat_year;

-- --------------------------------------------
-- 2. ADS 品类销售排行 —— 柱状图
-- --------------------------------------------
DROP TABLE IF EXISTS ads.ads_category_sales;
CREATE TABLE ads.ads_category_sales (
    category      STRING  COMMENT '品类',
    orders        BIGINT  COMMENT '订单数',
    total_qty     BIGINT  COMMENT '销售件数',
    net_sales     DOUBLE  COMMENT '折后净销售额'
) COMMENT '品类销售排行' STORED AS ORC;

INSERT OVERWRITE TABLE ads.ads_category_sales
SELECT p.category,
       count(DISTINCT i.order_id)                              AS orders,
       sum(i.quantity)                                         AS total_qty,
       round(sum(i.quantity * i.price * (1 - i.discount)), 2)  AS net_sales
FROM ydsh_dwd.dwd_order_item i
JOIN dwd.dim_product p ON i.product_id = p.product_id
GROUP BY p.category;

-- --------------------------------------------
-- 3. ADS 区域销售 —— 地图
-- --------------------------------------------
DROP TABLE IF EXISTS ads.ads_region_sales;
CREATE TABLE ads.ads_region_sales (
    province   STRING  COMMENT '省份',
    orders     BIGINT  COMMENT '订单数',
    gmv        DOUBLE  COMMENT 'GMV'
) COMMENT '区域销售汇总' STORED AS ORC;

INSERT OVERWRITE TABLE ads.ads_region_sales
SELECT s.province,
       count(DISTINCT o.order_id)          AS orders,
       round(sum(o.pay_amount), 2)         AS gmv
FROM ydsh_dwd.dwd_order o
JOIN dwd.dim_store s ON o.store_id = s.store_id
GROUP BY s.province;

-- --------------------------------------------
-- 4. ADS 支付方式占比 —— 饼图
-- --------------------------------------------
DROP TABLE IF EXISTS ads.ads_paytype_share;
CREATE TABLE ads.ads_paytype_share (
    pay_type   STRING  COMMENT '支付方式',
    orders     BIGINT  COMMENT '订单数',
    gmv        DOUBLE  COMMENT 'GMV'
) COMMENT '支付方式占比' STORED AS ORC;

INSERT OVERWRITE TABLE ads.ads_paytype_share
SELECT pay_type,
       count(DISTINCT order_id)     AS orders,
       round(sum(pay_amount), 2)    AS gmv
FROM ydsh_dwd.dwd_order
GROUP BY pay_type;

-- --------------------------------------------
-- 5. ADS 门店 TopN 排行 —— 排行表
-- --------------------------------------------
DROP TABLE IF EXISTS ads.ads_store_rank;
CREATE TABLE ads.ads_store_rank (
    store_id    STRING  COMMENT '门店ID',
    store_name  STRING  COMMENT '门店名称',
    province    STRING  COMMENT '省份',
    orders      BIGINT  COMMENT '订单数',
    gmv         DOUBLE  COMMENT 'GMV'
) COMMENT '门店销售排行' STORED AS ORC;

INSERT OVERWRITE TABLE ads.ads_store_rank
SELECT s.store_id, s.store_name, s.province,
       count(DISTINCT o.order_id)     AS orders,
       round(sum(o.pay_amount), 2)    AS gmv
FROM ydsh_dwd.dwd_order o
JOIN dwd.dim_store s ON o.store_id = s.store_id
GROUP BY s.store_id, s.store_name, s.province;

-- --------------------------------------------
-- 6. ADS 核心 KPI 单行表 —— 大屏顶部指标卡
-- --------------------------------------------
DROP TABLE IF EXISTS ads.ads_kpi;
CREATE TABLE ads.ads_kpi (
    gmv            DOUBLE  COMMENT '总GMV',
    orders         BIGINT  COMMENT '总订单数',
    aov            DOUBLE  COMMENT '客单价',
    user_cnt       BIGINT  COMMENT '下单用户数',
    store_cnt      BIGINT  COMMENT '门店数',
    refund_rate    DOUBLE  COMMENT '退款率(%)'
) COMMENT '核心KPI单行表' STORED AS ORC;

INSERT OVERWRITE TABLE ads.ads_kpi
SELECT round(sum(pay_amount), 2),
       count(DISTINCT order_id),
       round(sum(pay_amount) / count(DISTINCT order_id), 2),
       count(DISTINCT user_id),
       count(DISTINCT store_id),
       round(sum(CASE WHEN order_status = '退款中' THEN 1 ELSE 0 END) * 100.0 / count(*), 2)
FROM ydsh_dwd.dwd_order
WHERE stat_date >= '2024-01-01';

-- 验证
SELECT 'ads tables built' AS status;
SHOW TABLES IN ads;
