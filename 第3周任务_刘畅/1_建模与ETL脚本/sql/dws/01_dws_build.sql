-- =====================================================================
-- 01_dws_build.sql  步骤 1a：DWS 汇总层建设（Hive 正式口径）
-- 汇总维度：按天/周 × 门店/品类/渠道 + 按周大盘
-- 上游：dwd.dwd_order / dwd.dim_product / dwd.dim_store
-- =====================================================================

-- ---------- DWS：按天 + 门店汇总 ----------
drop table if exists dws.dws_order_store_day;
create table dws.dws_order_store_day as
select
    store_id,
    order_date,
    sum(pay_amount)            as gmv,
    count(distinct order_id)   as orders,
    count(distinct user_id)    as users
from dwd.dwd_order
where status = 'paid'          -- 口径：只统计有效订单
group by store_id, order_date;

-- ---------- DWS：按天 + 品类汇总（供品类趋势与预测复用） ----------
drop table if exists dws.dws_category_day;
create table dws.dws_category_day as
select
    p.category,
    o.order_date,
    sum(o.pay_amount)          as gmv,
    count(distinct o.order_id) as orders
from dwd.dwd_order o
join dwd.dim_product p on o.product_id = p.product_id
where o.status = 'paid'
group by p.category, o.order_date;

-- ---------- DWS：按天 + 渠道汇总（线上/线下） ----------
drop table if exists dws.dws_channel_day;
create table dws.dws_channel_day as
select
    s.channel,
    o.order_date,
    sum(o.pay_amount)          as gmv,
    count(distinct o.order_id) as orders,
    count(distinct o.user_id)  as users
from dwd.dwd_order o
join dwd.dim_store s on o.store_id = s.store_id
where o.status = 'paid'
group by s.channel, o.order_date;

-- ---------- DWS：按周大盘汇总（周一为一周起点） ----------
-- Hive：date_sub(next_day(order_date,'MO'),7) 取所在周的周一
drop table if exists dws.dws_order_week;
create table dws.dws_order_week as
select
    date_sub(next_day(order_date, 'MO'), 7) as week_start,
    sum(pay_amount)                         as gmv,
    count(distinct order_id)                as orders,
    count(distinct user_id)                 as active_users,
    round(sum(pay_amount) / count(distinct order_id), 2) as aov
from dwd.dwd_order
where status = 'paid'
group by date_sub(next_day(order_date, 'MO'), 7);
