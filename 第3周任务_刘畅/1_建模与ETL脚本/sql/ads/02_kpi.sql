-- =====================================================================
-- 02_kpi.sql  步骤 2：核心 KPI 计算（Hive 正式口径）
-- 口径来源：config/metrics.md（先定口径，再算数）
-- =====================================================================

-- ---------- 大盘 KPI 总表（期末口径） ----------
drop table if exists ads.ads_kpi_overall;
create table ads.ads_kpi_overall as
select
    round(sum(pay_amount), 2)                              as gmv,
    count(distinct order_id)                               as orders,
    round(sum(pay_amount) / count(distinct order_id), 2)   as aov,
    count(distinct user_id)                                as active_users,
    round(rep.user_cnt_2plus / base.user_cnt, 4)           as repurchase_rate
from dwd.dwd_order o
cross join (
    select count(distinct user_id) as user_cnt
    from dwd.dwd_order where status = 'paid'
) base
cross join (
    select count(1) as user_cnt_2plus from (
        select user_id
        from dwd.dwd_order
        where status = 'paid'
        group by user_id
        having count(distinct order_id) >= 2
    ) t
) rep
where o.status = 'paid';

-- ---------- 按月 KPI（趋势观察用） ----------
drop table if exists ads.ads_kpi_month;
create table ads.ads_kpi_month as
select
    substr(order_date, 1, 7)                               as month,
    round(sum(pay_amount), 2)                              as gmv,
    count(distinct order_id)                               as orders,
    round(sum(pay_amount) / count(distinct order_id), 2)   as aov,
    count(distinct user_id)                                as active_users
from dwd.dwd_order
where status = 'paid'
group by substr(order_date, 1, 7);

-- ---------- 复购率分月（月度复购用户 / 月度下单用户） ----------
drop table if exists ads.ads_repurchase_month;
create table ads.ads_repurchase_month as
select
    mon as month,
    count(distinct user_id)                                as buyers,
    count(distinct case when cnt >= 2 then user_id end)    as repeat_users,
    round(count(distinct case when cnt >= 2 then user_id end)
          / count(distinct user_id), 4)                    as repurchase_rate
from (
    select
        user_id,
        substr(order_date, 1, 7) as mon,
        count(distinct order_id) as cnt
    from dwd.dwd_order
    where status = 'paid'
    group by user_id, substr(order_date, 1, 7)
) u
group by mon;

-- ---------- 用户价值分层（RFM 简化版：按 GMV 四分位分层） ----------
-- ntile(4)：GMV 前 25% 为高价值，其后依次为成长/一般/低频；并列值切分随机，属可接受近似
drop table if exists ads.ads_user_value;
create table ads.ads_user_value as
select
    user_id,
    orders,
    gmv,
    last_order_date,
    case quartile when 1 then '高价值' when 2 then '成长' when 3 then '一般' else '低频' end as value_tier
from (
    select
        user_id,
        count(distinct order_id)              as orders,
        sum(pay_amount)                       as gmv,
        max(order_date)                       as last_order_date,
        ntile(4) over (order by sum(pay_amount) desc) as quartile
    from dwd.dwd_order
    where status = 'paid'
    group by user_id
) u;

-- ---------- 用户分层汇总（各层人数、GMV、GMV 占比，供运营看板） ----------
drop table if exists ads.ads_user_tier_summary;
create table ads.ads_user_tier_summary as
select
    t.value_tier,
    t.users,
    round(t.gmv, 2)                    as gmv,
    round(t.gmv / b.total_gmv, 4)      as gmv_share
from (
    select value_tier, count(1) as users, sum(gmv) as gmv
    from ads.ads_user_value
    group by value_tier
) t
cross join (
    select sum(pay_amount) as total_gmv from dwd.dwd_order where status = 'paid'
) b
order by t.gmv desc;

-- ---------- 口径一致性复核（四条链路必须相等） ----------
-- 1) DWD 直算  ==  2) DWS 门店日汇总  ==  3) DWS 周汇总  ==  4) ADS 日 KPI 汇总
select
    (select round(sum(pay_amount), 2) from dwd.dwd_order where status = 'paid')        as gmv_from_dwd,
    (select round(sum(gmv), 2)        from dws.dws_order_store_day)                    as gmv_from_dws,
    (select round(sum(gmv), 2)        from dws.dws_order_week)                         as gmv_from_week,
    (select round(sum(gmv), 2)        from ads.ads_kpi_day)                            as gmv_from_ads;
