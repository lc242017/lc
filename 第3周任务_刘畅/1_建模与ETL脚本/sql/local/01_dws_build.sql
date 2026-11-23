-- 本地执行版（SQLite）：逻辑与 sql/dws/01_dws_build.sql 完全一致，仅去掉库前缀
-- 周起点：date(order_date,'weekday 0','-6 days') 取所在周的周一（与 Hive next_day('MO') 同义）
drop table if exists dws_order_store_day;
create table dws_order_store_day as
select
    store_id,
    order_date,
    sum(pay_amount)          as gmv,
    count(distinct order_id) as orders,
    count(distinct user_id)  as users
from dwd_order
where status = 'paid'
group by store_id, order_date;

drop table if exists dws_category_day;
create table dws_category_day as
select
    p.category,
    o.order_date,
    sum(o.pay_amount)          as gmv,
    count(distinct o.order_id) as orders
from dwd_order o
join dim_product p on o.product_id = p.product_id
where o.status = 'paid'
group by p.category, o.order_date;

drop table if exists dws_channel_day;
create table dws_channel_day as
select
    s.channel,
    o.order_date,
    sum(o.pay_amount)          as gmv,
    count(distinct o.order_id) as orders,
    count(distinct o.user_id)  as users
from dwd_order o
join dim_store s on o.store_id = s.store_id
where o.status = 'paid'
group by s.channel, o.order_date;

drop table if exists dws_order_week;
create table dws_order_week as
select
    date(order_date, 'weekday 0', '-6 days')             as week_start,
    sum(pay_amount)                                      as gmv,
    count(distinct order_id)                             as orders,
    count(distinct user_id)                              as active_users,
    round(sum(pay_amount) / count(distinct order_id), 2) as aov
from dwd_order
where status = 'paid'
group by date(order_date, 'weekday 0', '-6 days');
