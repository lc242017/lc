-- =====================================================================
-- 01_ads_build.sql  步骤 1b：ADS 应用层建设（Hive 正式口径）
-- 面向业务场景输出：渠道结构、品类 TopN 与销售占比、销售日报
-- =====================================================================

-- ---------- ADS：渠道结构（线上/线下占比，供经营分析看板） ----------
drop table if exists ads.ads_channel_share;
create table ads.ads_channel_share as
select
    channel,
    round(sum(gmv), 2)                                              as gmv,
    sum(orders)                                                     as orders,
    round(sum(gmv) / t.total_gmv, 4)                                as gmv_share
from dws.dws_channel_day
cross join (select sum(gmv) as total_gmv from dws.dws_channel_day) t
group by channel, t.total_gmv
order by gmv desc;

-- ---------- ADS：品类销售额 Top10 + 品类销售占比 ----------
drop table if exists ads.ads_category_top10;
create table ads.ads_category_top10 as
select
    c.category,
    c.sales,
    c.cnt,
    round(c.sales / t.total_sales, 4)                               as sales_share
from (
    select
        p.category                                  as category,
        round(sum(o.pay_amount), 2)                 as sales,
        count(1)                                    as cnt
    from dwd.dwd_order o
    join dwd.dim_product p on o.product_id = p.product_id
    where o.status = 'paid'
    group by p.category
) c
cross join (
    select round(sum(pay_amount), 2) as total_sales
    from dwd.dwd_order where status = 'paid'
) t
order by c.sales desc
limit 10;

-- ---------- ADS：按天大盘 KPI（销售日报 / 趋势 / 预测的统一出口） ----------
drop table if exists ads.ads_kpi_day;
create table ads.ads_kpi_day as
select
    order_date,
    round(sum(pay_amount), 2)                                as gmv,
    count(distinct order_id)                                 as orders,
    count(distinct user_id)                                  as active_users,
    round(sum(pay_amount) / count(distinct order_id), 2)     as aov
from dwd.dwd_order
where status = 'paid'
group by order_date;
