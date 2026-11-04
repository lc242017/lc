-- =====================================================================
-- 20_eda.sql   探索性数据分析（对应手册「步骤 8」）
-- ---------------------------------------------------------------------
-- 前置：12 / 13 已完成，dwd_order / dwd_order_item / dwd_user_behavior
--       / dim_user / dim_product / dim_store / dim_date 均可查
--
-- 【口径先定义，再取数 —— 否则同一份数据能算出三个不同的 GMV】
--   GMV       = order_status ∈ ('已支付','已完成') 的 pay_amount 合计
--               （已取消/退款中不计入，符合经营口径；预评估口径含全状态，两者不可混用）
--   订单量    = 上述口径下 count(distinct order_id)
--   客单价    = GMV / 订单量
--   下单用户数= 上述口径下 count(distinct user_id)
--   复购率    = 下单 ≥2 次的用户数 / 下单用户数
--
-- 【执行建议】每条查询单独跑，把结果直接填进《探索性分析简报》对应小节；
--   本脚本不做落表，ADS 层的固化表在第 3 周完成。
-- =====================================================================

use ydsh_dwd;

-- 统一状态过滤，后文都复用这段条件
--   where order_status in ('已支付', '已完成')


-- ---------------------------------------------------------------------
-- 1. 核心 KPI 总览
-- ---------------------------------------------------------------------
select
    round(sum(pay_amount), 2)                        as gmv,
    count(distinct order_id)                         as order_cnt,
    round(sum(pay_amount) / count(distinct order_id), 2) as aov,
    count(distinct user_id)                          as buyer_cnt,
    round(count(distinct order_id) * 1.0 / count(distinct user_id), 2) as orders_per_user,
    round(sum(discount_amount), 2)                   as total_discount,
    round(sum(discount_amount) * 100.0 / sum(pay_amount + discount_amount), 2) as discount_rate_pct
from ydsh_dwd.dwd_order
where order_status in ('已支付', '已完成');

-- 1.1 全状态订单结构（看清被排除掉多少）
select order_status,
       count(*)                        as order_cnt,
       round(sum(pay_amount), 2)       as amount,
       round(count(*) * 100.0 / sum(count(*)) over (), 2) as cnt_pct
from ydsh_dwd.dwd_order
group by order_status
order by order_cnt desc;


-- ---------------------------------------------------------------------
-- 2. 月度 GMV 趋势 + 环比（窗口函数 lag）
-- ---------------------------------------------------------------------
select
    stat_month,
    round(sum(pay_amount), 2)                                     as gmv,
    count(distinct order_id)                                      as order_cnt,
    round(sum(pay_amount) / count(distinct order_id), 2)          as aov,
    round(sum(pay_amount) - lag(sum(pay_amount)) over (order by stat_month), 2) as gmv_mom_diff,
    round((sum(pay_amount) - lag(sum(pay_amount)) over (order by stat_month))
          * 100.0 / lag(sum(pay_amount)) over (order by stat_month), 2)          as gmv_mom_pct
from ydsh_dwd.dwd_order
where order_status in ('已支付', '已完成')
group by stat_month
order by stat_month;


-- ---------------------------------------------------------------------
-- 3. 品类销售排行（注意：走 dwd_order_item，不是 dwd_order）
--    —— 手册步骤 8 用 dwd_order join dim_product 是行不通的，原因见 11_ddl_fact.sql 注释
-- ---------------------------------------------------------------------
select
    p.category,
    round(sum(i.item_amount), 2)                             as sales,
    sum(i.quantity)                                          as qty,
    count(distinct i.order_id)                               as order_cnt,
    round(sum(i.item_amount) * 100.0 / sum(sum(i.item_amount)) over (), 2) as sales_pct
from ydsh_dwd.dwd_order_item i
join ydsh_dwd.dim_product   p on i.product_id = p.product_id
join ydsh_dwd.dwd_order     o on i.order_id   = o.order_id
where o.order_status in ('已支付', '已完成')
group by p.category
order by sales desc;

-- 3.1 二级品类 Top 15
select
    p.category, p.sub_category,
    round(sum(i.item_amount), 2) as sales,
    sum(i.quantity)              as qty
from ydsh_dwd.dwd_order_item i
join ydsh_dwd.dim_product   p on i.product_id = p.product_id
join ydsh_dwd.dwd_order     o on i.order_id   = o.order_id
where o.order_status in ('已支付', '已完成')
group by p.category, p.sub_category
order by sales desc
limit 15;

-- 3.2 单品销量 Top 20
select
    p.product_name, p.category, p.brand,
    sum(i.quantity)              as qty,
    round(sum(i.item_amount), 2) as sales
from ydsh_dwd.dwd_order_item i
join ydsh_dwd.dim_product   p on i.product_id = p.product_id
join ydsh_dwd.dwd_order     o on i.order_id   = o.order_id
where o.order_status in ('已支付', '已完成')
group by p.product_name, p.category, p.brand
order by qty desc
limit 20;


-- ---------------------------------------------------------------------
-- 4. 渠道分析：规模 + 客单价 + 折扣力度
-- ---------------------------------------------------------------------
select
    channel,
    count(distinct order_id)                                      as order_cnt,
    round(sum(pay_amount), 2)                                     as gmv,
    round(sum(pay_amount) / count(distinct order_id), 2)           as aov,
    round(sum(pay_amount) * 100.0 / sum(sum(pay_amount)) over (), 2) as gmv_pct,
    round(sum(discount_amount) * 100.0 / sum(pay_amount + discount_amount), 2) as discount_rate_pct
from ydsh_dwd.dwd_order
where order_status in ('已支付', '已完成')
group by channel
order by gmv desc;


-- ---------------------------------------------------------------------
-- 5. 会员等级贡献：人数 × 频次 × 客单价 拆解
-- ---------------------------------------------------------------------
select
    u.member_level,
    count(distinct o.user_id)                                     as buyer_cnt,
    count(distinct o.order_id)                                    as order_cnt,
    round(sum(o.pay_amount), 2)                                   as gmv,
    round(sum(o.pay_amount) / count(distinct o.user_id), 2)        as arpu,
    round(sum(o.pay_amount) / count(distinct o.order_id), 2)       as aov,
    round(sum(o.pay_amount) * 100.0 / sum(sum(o.pay_amount)) over (), 2) as gmv_pct
from ydsh_dwd.dwd_order o
join ydsh_dwd.dim_user  u on o.user_id = u.user_id
where o.order_status in ('已支付', '已完成')
group by u.member_level
order by gmv desc;

-- 5.1 年龄段 × 性别交叉分布（看主力客群）
select
    u.age_group, u.gender,
    count(distinct o.user_id)              as buyer_cnt,
    round(sum(o.pay_amount), 2)            as gmv
from ydsh_dwd.dwd_order o
join ydsh_dwd.dim_user  u on o.user_id = u.user_id
where o.order_status in ('已支付', '已完成')
group by u.age_group, u.gender
order by gmv desc;


-- ---------------------------------------------------------------------
-- 6. 门店 Top 10 与地域分布
-- ---------------------------------------------------------------------
select
    s.store_name, s.city, s.province,
    count(distinct o.order_id)      as order_cnt,
    round(sum(o.pay_amount), 2)     as gmv,
    round(sum(o.pay_amount) / count(distinct o.order_id), 2) as aov
from ydsh_dwd.dwd_order o
join ydsh_dwd.dim_store s on o.store_id = s.store_id
where o.order_status in ('已支付', '已完成')
group by s.store_name, s.city, s.province
order by gmv desc
limit 10;

-- 6.1 省份 GMV 分布
select
    s.province,
    count(distinct o.order_id)  as order_cnt,
    round(sum(o.pay_amount), 2) as gmv,
    round(sum(o.pay_amount) * 100.0 / sum(sum(o.pay_amount)) over (), 2) as gmv_pct
from ydsh_dwd.dwd_order o
join ydsh_dwd.dim_store s on o.store_id = s.store_id
where o.order_status in ('已支付', '已完成')
group by s.province
order by gmv desc;


-- ---------------------------------------------------------------------
-- 7. 支付方式与分时段下单分布
-- ---------------------------------------------------------------------
select
    pay_type,
    count(distinct order_id)      as order_cnt,
    round(sum(pay_amount), 2)     as gmv,
    round(count(*) * 100.0 / sum(count(*)) over (), 2) as cnt_pct
from ydsh_dwd.dwd_order
where order_status in ('已支付', '已完成')
group by pay_type
order by order_cnt desc;

select
    stat_hour,
    count(*)                  as order_cnt,
    round(sum(pay_amount), 2) as gmv
from ydsh_dwd.dwd_order
where order_status in ('已支付', '已完成')
group by stat_hour
order by stat_hour;


-- ---------------------------------------------------------------------
-- 8. 用户复购分析
-- ---------------------------------------------------------------------
-- 8.1 下单次数分布
select
    case when c = 1 then '1 次'
         when c = 2 then '2 次'
         when c between 3 and 5 then '3-5 次'
         else '6 次及以上' end as order_cnt_bucket,
    count(*) as user_cnt,
    sum(c)   as order_total
from (
    select user_id, count(*) as c
      from ydsh_dwd.dwd_order
     where order_status in ('已支付', '已完成')
     group by user_id
) t
group by case when c = 1 then '1 次'
              when c = 2 then '2 次'
              when c between 3 and 5 then '3-5 次'
              else '6 次及以上' end
order by user_cnt desc;

-- 8.2 复购率（核心指标）
select
    count(*)                                          as buyer_cnt,
    sum(case when c >= 2 then 1 else 0 end)            as repeat_buyer_cnt,
    round(sum(case when c >= 2 then 1 else 0 end) * 100.0 / count(*), 2) as repeat_rate_pct,
    round(avg(c), 2)                                   as avg_orders_per_buyer
from (
    select user_id, count(*) as c
      from ydsh_dwd.dwd_order
     where order_status in ('已支付', '已完成')
     group by user_id
) t;


-- ---------------------------------------------------------------------
-- 9. 行为漏斗：浏览 → 加购 → 收藏 → 购买（用户级去重）
-- ---------------------------------------------------------------------
select
    count(distinct case when behavior_type = '浏览' then user_id end) as pv_user_cnt,
    count(distinct case when behavior_type = '加购' then user_id end) as cart_user_cnt,
    count(distinct case when behavior_type = '收藏' then user_id end) as fav_user_cnt,
    count(distinct case when behavior_type = '购买' then user_id end) as buy_user_cnt,
    round(count(distinct case when behavior_type = '加购' then user_id end) * 100.0
        / count(distinct case when behavior_type = '浏览' then user_id end), 2) as pv_to_cart_pct,
    round(count(distinct case when behavior_type = '购买' then user_id end) * 100.0
        / count(distinct case when behavior_type = '浏览' then user_id end), 2) as pv_to_buy_pct
from ydsh_dwd.dwd_user_behavior;

-- 9.1 事件级漏斗（带各环节转化率）
select
    behavior_type,
    count(*) as event_cnt,
    round(count(*) * 100.0 / sum(count(*)) over (), 2) as event_pct
from ydsh_dwd.dwd_user_behavior
group by behavior_type
order by event_cnt desc;


-- ---------------------------------------------------------------------
-- 10. 价格带销量分布（判断价格敏感度）
-- ---------------------------------------------------------------------
select
    p.price_band,
    sum(i.quantity)              as qty,
    round(sum(i.item_amount), 2) as sales,
    count(distinct i.order_id)   as order_cnt
from ydsh_dwd.dwd_order_item i
join ydsh_dwd.dim_product   p on i.product_id = p.product_id
join ydsh_dwd.dwd_order     o on i.order_id   = o.order_id
where o.order_status in ('已支付', '已完成')
group by p.price_band
order by sales desc;


-- ---------------------------------------------------------------------
-- 11. 时间维度联动：工作日 vs 周末
-- ---------------------------------------------------------------------
select
    case when d.is_weekend = 1 then '周末' else '工作日' end as day_type,
    count(distinct o.order_id)  as order_cnt,
    round(sum(o.pay_amount), 2) as gmv,
    round(sum(o.pay_amount) / count(distinct o.order_id), 2) as aov
from ydsh_dwd.dwd_order o
join ydsh_dwd.dim_date   d on o.stat_date = d.date_id
where o.order_status in ('已支付', '已完成')
group by case when d.is_weekend = 1 then '周末' else '工作日' end;


-- ---------------------------------------------------------------------
-- 12. 月度折扣率与 GMV：验证假设 H5「折扣率与 GMV 无正相关」
--     折扣率 = 优惠总额 / (实付 + 优惠)，与 GMV 同口径（已支付 + 已完成）
--     拿到 12 个点后看两者是否同向变动；同向 = 打折换来了增长，反向/无关 = 促销未奏效
-- ---------------------------------------------------------------------
select
    stat_month                                                  as ym,
    count(distinct order_id)                                    as order_cnt,
    round(sum(pay_amount), 2)                                   as gmv,
    round(sum(discount_amount), 2)                              as discount_amt,
    round(sum(discount_amount) * 100.0
          / nullif(sum(pay_amount) + sum(discount_amount), 0), 2) as discount_rate_pct,
    round(sum(pay_amount) / count(distinct order_id), 2)        as aov
from ydsh_dwd.dwd_order
where order_status in ('已支付', '已完成')
group by stat_month
order by stat_month;
