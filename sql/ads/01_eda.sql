-- ============================================
-- 步骤 8：探索性数据分析（基于 DWD 层）
-- ============================================

-- 1. 总体核心指标：总 GMV、订单量、客单价 AOV
select round(sum(pay_amount), 2) as gmv,
       count(distinct order_id) as orders,
       round(sum(pay_amount) / count(distinct order_id), 2) as aov
from dwd.dwd_order_fact;

-- 2. 品类销售排行（订单明细事实 × 商品维度，含折扣后净销售额）
select p.category,
       count(distinct i.order_id) as orders,
       sum(i.quantity) as total_qty,
       round(sum(i.quantity * i.unit_price), 2) as sales,
       round(sum(i.quantity * i.unit_price * (1 - i.discount)), 2) as net_sales
from dwd.dwd_order_item_fact i
join dwd.dim_product p on i.product_id = p.product_id
group by p.category
order by net_sales desc;

-- 3. 月度 GMV 趋势（分区裁剪演示：全表但按月聚合）
select substr(order_date, 1, 7) as month,
       count(distinct order_id) as orders,
       round(sum(pay_amount), 2) as gmv
from dwd.dwd_order_fact
group by substr(order_date, 1, 7)
order by month;

-- 4. 订单状态分布
select order_status, count(*) as cnt, round(sum(pay_amount), 2) as amount
from dwd.dwd_order_fact
group by order_status
order by cnt desc;

-- 5. 渠道分布
select channel, count(*) as cnt, round(sum(pay_amount), 2) as amount
from dwd.dwd_order_fact
group by channel
order by cnt desc;

-- 6. 会员等级 × 消费（订单事实 × 用户维度）
select u.member_level,
       count(distinct o.order_id) as orders,
       round(sum(o.pay_amount) / count(distinct o.order_id), 2) as aov
from dwd.dwd_order_fact o
join dwd.dim_user u on o.user_id = u.user_id
group by u.member_level
order by aov desc;

-- 7. 用户行为转化（浏览→加购→收藏→购买）
select behavior_type, count(*) as cnt
from dwd.ods_user_behavior_s1
group by behavior_type
order by cnt desc;
