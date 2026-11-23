-- 本地执行版（SQLite）：逻辑与 sql/ads/01_ads_build.sql 完全一致，仅去掉库前缀
drop table if exists ads_channel_share;
create table ads_channel_share as
select
    channel,
    round(sum(gmv), 2)                                             as gmv,
    sum(orders)                                                    as orders,
    round(sum(gmv) * 1.0 / t.total_gmv, 4)                         as gmv_share
from dws_channel_day
cross join (select sum(gmv) as total_gmv from dws_channel_day) t
group by channel, t.total_gmv
order by gmv desc;

drop table if exists ads_category_top10;
create table ads_category_top10 as
select
    c.category,
    c.sales,
    c.cnt,
    round(c.sales * 1.0 / t.total_sales, 4)                        as sales_share
from (
    select
        p.category                     as category,
        round(sum(o.pay_amount), 2)    as sales,
        count(1)                       as cnt
    from dwd_order o
    join dim_product p on o.product_id = p.product_id
    where o.status = 'paid'
    group by p.category
) c
cross join (
    select round(sum(pay_amount), 2) as total_sales
    from dwd_order where status = 'paid'
) t
order by c.sales desc
limit 10;

drop table if exists ads_kpi_day;
create table ads_kpi_day as
select
    order_date,
    round(sum(pay_amount), 2)                            as gmv,
    count(distinct order_id)                             as orders,
    count(distinct user_id)                              as active_users,
    round(sum(pay_amount) / count(distinct order_id), 2) as aov
from dwd_order
where status = 'paid'
group by order_date;
