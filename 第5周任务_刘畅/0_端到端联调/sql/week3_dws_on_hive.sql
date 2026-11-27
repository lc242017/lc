-- =====================================================================
-- 五周串联补齐：第3周 DWS 汇总层 + 核心 KPI（Hive 真实口径版）
-- 背景：第3周 DWS/ADS 原只在本地 SQLite 跑通，Hive 版因 schema 不兼容
--       （第3周用 status/order_date/product_id，真实 Hive 为 order_status/
--        stat_date + dwd_order_item.product_id）从未落到 Hive。
-- 本脚本按真实 Hive schema 改写，打通 ydsh_dwd → dws → ads 链路。
-- 数据源：ydsh_dwd.dwd_order（15000单，2024全年，已实跑验证）
--         ydsh_dwd.dwd_order_item（订单明细，含 product_id）
--         ydsh_dwd.dim_product / dim_store
-- 有效订单口径：order_status IN ('已完成','已支付')（与第4周 ADS 口径一致）
-- GMV 锚点：39,708,649.13 元（全量口径，与第4周 ads_kpi 一致）
-- 生成时间：2026-11-27
-- =====================================================================

CREATE DATABASE IF NOT EXISTS dws;

-- ---------- DWS-1：按天+门店汇总 ----------
DROP TABLE IF EXISTS dws.dws_order_store_day;
CREATE TABLE dws.dws_order_store_day AS
SELECT
    store_id,
    stat_date                       AS order_date,
    SUM(pay_amount)                 AS gmv,
    COUNT(DISTINCT order_id)        AS orders,
    COUNT(DISTINCT user_id)         AS users
FROM ydsh_dwd.dwd_order
WHERE order_status IN ('已完成','已支付')
GROUP BY store_id, stat_date;

-- ---------- DWS-2：按天+品类汇总（走明细表取 product_id） ----------
-- 口警告：dwd_order_item.item_amount 为行级金额口径，全表合计 6.45 亿，
--         与订单实付 GMV 3970万不同。本表仅用于品类结构分析，不作 GMV 对外口径。
--         品类 GMV 对外以第4周 ads.ads_category_sales.net_sales 为准。
DROP TABLE IF EXISTS dws.dws_category_day;
CREATE TABLE dws.dws_category_day AS
SELECT
    p.category,
    o.stat_date                     AS order_date,
    SUM(i.item_amount)              AS gmv,
    COUNT(DISTINCT o.order_id)      AS orders
FROM ydsh_dwd.dwd_order o
JOIN ydsh_dwd.dwd_order_item i ON o.order_id = i.order_id
JOIN ydsh_dwd.dim_product p     ON i.product_id = p.product_id
WHERE o.order_status IN ('已完成','已支付')
GROUP BY p.category, o.stat_date;

-- ---------- DWS-3：按天+渠道汇总（渠道取自 dwd_order.channel，非 dim_store） ----------
DROP TABLE IF EXISTS dws.dws_channel_day;
CREATE TABLE dws.dws_channel_day AS
SELECT
    o.channel,
    o.stat_date                     AS order_date,
    SUM(o.pay_amount)               AS gmv,
    COUNT(DISTINCT o.order_id)      AS orders,
    COUNT(DISTINCT o.user_id)       AS users
FROM ydsh_dwd.dwd_order o
WHERE o.order_status IN ('已完成','已支付')
GROUP BY o.channel, o.stat_date;

-- ---------- DWS-4：按周大盘汇总（周一为起点） ----------
DROP TABLE IF EXISTS dws.dws_order_week;
CREATE TABLE dws.dws_order_week AS
SELECT
    date_sub(next_day(stat_date, 'MO'), 7)  AS week_start,
    SUM(pay_amount)                         AS gmv,
    COUNT(DISTINCT order_id)                AS orders,
    COUNT(DISTINCT user_id)                 AS active_users,
    ROUND(SUM(pay_amount)/COUNT(DISTINCT order_id), 2) AS aov
FROM ydsh_dwd.dwd_order
WHERE order_status IN ('已完成','已支付')
GROUP BY date_sub(next_day(stat_date, 'MO'), 7);

-- ---------- DWS-5：按天+月大盘汇总 ----------
DROP TABLE IF EXISTS dws.dws_order_day;
CREATE TABLE dws.dws_order_day AS
SELECT
    stat_date                       AS order_date,
    stat_month,
    SUM(pay_amount)                 AS gmv,
    COUNT(DISTINCT order_id)        AS orders,
    COUNT(DISTINCT user_id)         AS users
FROM ydsh_dwd.dwd_order
WHERE order_status IN ('已完成','已支付')
GROUP BY stat_date, stat_month;

-- =====================================================================
-- ADS 补充表（第3周新增指标，与第4周已有 ads 表互补，不覆盖）
-- =====================================================================

-- ---------- ADS-A：渠道结构占比 ----------
DROP TABLE IF EXISTS ads.ads_channel_share;
CREATE TABLE ads.ads_channel_share AS
SELECT
    channel,
    ROUND(SUM(gmv), 2)                                  AS gmv,
    SUM(orders)                                         AS orders,
    ROUND(SUM(gmv) / t.total_gmv, 4)                    AS gmv_share
FROM dws.dws_channel_day
CROSS JOIN (SELECT SUM(gmv) AS total_gmv FROM dws.dws_channel_day) t
GROUP BY channel, t.total_gmv
ORDER BY gmv DESC;

-- ---------- ADS-B：品类销售额 Top10 + 占比 ----------
DROP TABLE IF EXISTS ads.ads_category_top10;
CREATE TABLE ads.ads_category_top10 AS
SELECT
    c.category,
    c.sales,
    c.cnt,
    ROUND(c.sales / t.total_sales, 4)                   AS sales_share
FROM (
    SELECT
        p.category                          AS category,
        ROUND(SUM(i.item_amount), 2)        AS sales,
        COUNT(DISTINCT o.order_id)          AS cnt
    FROM ydsh_dwd.dwd_order o
    JOIN ydsh_dwd.dwd_order_item i ON o.order_id = i.order_id
    JOIN ydsh_dwd.dim_product p     ON i.product_id = p.product_id
    WHERE o.order_status IN ('已完成','已支付')
    GROUP BY p.category
) c
CROSS JOIN (
    SELECT ROUND(SUM(item_amount), 2) AS total_sales
    FROM ydsh_dwd.dwd_order_item
) t
ORDER BY c.sales DESC
LIMIT 10;

-- ---------- ADS-C：大盘 KPI 总表（第3周口径） ----------
-- 说明：用聚合子查询先算各指标，再拼装，规避 CROSS JOIN 在 GROUP BY 下的列引用限制
DROP TABLE IF EXISTS ads.ads_kpi_overall_w3;
CREATE TABLE ads.ads_kpi_overall_w3 AS
SELECT
    m.gmv, m.orders, m.aov, m.active_users,
    ROUND(rep.user_cnt_2plus * 1.0 / m.active_users, 4)         AS repurchase_rate
FROM (
    SELECT
        ROUND(SUM(pay_amount), 2)                               AS gmv,
        COUNT(DISTINCT order_id)                                AS orders,
        ROUND(SUM(pay_amount)/COUNT(DISTINCT order_id), 2)      AS aov,
        COUNT(DISTINCT user_id)                                 AS active_users
    FROM ydsh_dwd.dwd_order
    WHERE order_status IN ('已完成','已支付')
) m
CROSS JOIN (
    SELECT COUNT(1) AS user_cnt_2plus FROM (
        SELECT user_id FROM ydsh_dwd.dwd_order
        WHERE order_status IN ('已完成','已支付')
        GROUP BY user_id HAVING COUNT(DISTINCT order_id) >= 2
    ) t
) rep;

-- ---------- ADS-D：月度 KPI（第3周口径） ----------
DROP TABLE IF EXISTS ads.ads_kpi_month_w3;
CREATE TABLE ads.ads_kpi_month_w3 AS
SELECT
    stat_month                                          AS month,
    ROUND(SUM(pay_amount), 2)                           AS gmv,
    COUNT(DISTINCT order_id)                            AS orders,
    ROUND(SUM(pay_amount)/COUNT(DISTINCT order_id), 2)  AS aov,
    COUNT(DISTINCT user_id)                             AS active_users
FROM ydsh_dwd.dwd_order
WHERE order_status IN ('已完成','已支付')
GROUP BY stat_month;
