-- ============================================
-- 重复值检测与去重（步骤 9）
-- 用 row_number() 窗口函数对订单表去重，
-- 按下单时间倒序保留每个 order_id 的一条最新记录
-- ============================================

create table if not exists ydsh_dwd.dwd_order as
select
  order_id, user_id, store_id, order_date, order_time,
  pay_amount, discount_amount, pay_type, order_status, channel
from (
  select *,
         row_number() over (partition by order_id order by order_time desc) as rn
  from ydsh_ods.ods_order
) t
where rn = 1;

-- 验收 1：行数应为 15000（15600 - 600 冗余）
select count(*) total, count(distinct order_id) dist_order_id
from ydsh_dwd.dwd_order;

-- 验收 2：不应再有重复 order_id
select order_id, count(*) c
from ydsh_dwd.dwd_order
group by order_id
having count(*) > 1;
