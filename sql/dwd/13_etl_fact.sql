-- =====================================================================
-- 13_etl_fact.sql   事实表加载（对应手册「步骤 7」分区表数据加载）
-- ---------------------------------------------------------------------
-- 前置：03 产出 dwd_order_tmp；11 建好 3 张事实表；12 维度表已加载
-- 加载方式：动态分区 insert overwrite（分区由数据自己决定，不写死日期）
--
-- 【动态分区参数必须每次会话重设】beeline 新开连接就是新会话，
--   这也是"本地跑通、脚本跑挂"最常见的原因。
-- =====================================================================

use ydsh_dwd;

set hive.exec.dynamic.partition = true;
set hive.exec.dynamic.partition.mode = nonstrict;
-- 【参数说明】动态分区上限不能按"分区数 < 1000"来设。Tez 下 pernode 是
--   按容器（JVM）累计计数，不是按单个 task 计数；本作业 366 个分区会被
--   多个容器重复累加，实测在 1000 处直接抛 Error 20004 并整条 Rollback（数据 0 行）。
--   故统一放大到安全值，仍远小于 max.dynamic.partitions 总上限。
set hive.exec.max.dynamic.partitions = 20000;
set hive.exec.max.dynamic.partitions.pernode = 5000;
set hive.enforce.bucketing = true;
set hive.enforce.sorting = true;


-- ---------------------------------------------------------------------
-- 1. 订单事实表：dwd_order_tmp → dwd_order（按 stat_date 动态分区 + user_id 分桶）
--
-- 【为什么按月拆成 12 条，而不是一条 insert 全量写】
--   本环境 Metastore 为 Derby（嵌入式）。一次 MoveTask 要新增 366 个分区时，
--   Derby 单事务提交失败，报 MetaException: Exception rolling back to savepoint，
--   整条 insert 回滚且分区目录一个都不落地（实测 dwd_order = 0 行）。
--   按月拆分后每次只新增约 30 个分区，提交稳定；12 条语句覆盖的月分区互不重叠，
--   依然可以反复重跑而不产生重复数据（insert overwrite 只覆盖涉及分区）。
--
insert overwrite table ydsh_dwd.dwd_order partition (stat_date)
select
    order_id, user_id, store_id, order_timestamp,
    stat_year, stat_month, stat_hour,
    pay_amount, discount_amount, total_amount,
    pay_type, order_status, channel, is_amount_fixed,
    stat_date
from ydsh_dwd.dwd_order_tmp
where stat_month = '2024-01';

insert overwrite table ydsh_dwd.dwd_order partition (stat_date)
select
    order_id, user_id, store_id, order_timestamp,
    stat_year, stat_month, stat_hour,
    pay_amount, discount_amount, total_amount,
    pay_type, order_status, channel, is_amount_fixed,
    stat_date
from ydsh_dwd.dwd_order_tmp
where stat_month = '2024-02';

insert overwrite table ydsh_dwd.dwd_order partition (stat_date)
select
    order_id, user_id, store_id, order_timestamp,
    stat_year, stat_month, stat_hour,
    pay_amount, discount_amount, total_amount,
    pay_type, order_status, channel, is_amount_fixed,
    stat_date
from ydsh_dwd.dwd_order_tmp
where stat_month = '2024-03';

insert overwrite table ydsh_dwd.dwd_order partition (stat_date)
select
    order_id, user_id, store_id, order_timestamp,
    stat_year, stat_month, stat_hour,
    pay_amount, discount_amount, total_amount,
    pay_type, order_status, channel, is_amount_fixed,
    stat_date
from ydsh_dwd.dwd_order_tmp
where stat_month = '2024-04';

insert overwrite table ydsh_dwd.dwd_order partition (stat_date)
select
    order_id, user_id, store_id, order_timestamp,
    stat_year, stat_month, stat_hour,
    pay_amount, discount_amount, total_amount,
    pay_type, order_status, channel, is_amount_fixed,
    stat_date
from ydsh_dwd.dwd_order_tmp
where stat_month = '2024-05';

insert overwrite table ydsh_dwd.dwd_order partition (stat_date)
select
    order_id, user_id, store_id, order_timestamp,
    stat_year, stat_month, stat_hour,
    pay_amount, discount_amount, total_amount,
    pay_type, order_status, channel, is_amount_fixed,
    stat_date
from ydsh_dwd.dwd_order_tmp
where stat_month = '2024-06';

insert overwrite table ydsh_dwd.dwd_order partition (stat_date)
select
    order_id, user_id, store_id, order_timestamp,
    stat_year, stat_month, stat_hour,
    pay_amount, discount_amount, total_amount,
    pay_type, order_status, channel, is_amount_fixed,
    stat_date
from ydsh_dwd.dwd_order_tmp
where stat_month = '2024-07';

insert overwrite table ydsh_dwd.dwd_order partition (stat_date)
select
    order_id, user_id, store_id, order_timestamp,
    stat_year, stat_month, stat_hour,
    pay_amount, discount_amount, total_amount,
    pay_type, order_status, channel, is_amount_fixed,
    stat_date
from ydsh_dwd.dwd_order_tmp
where stat_month = '2024-08';

insert overwrite table ydsh_dwd.dwd_order partition (stat_date)
select
    order_id, user_id, store_id, order_timestamp,
    stat_year, stat_month, stat_hour,
    pay_amount, discount_amount, total_amount,
    pay_type, order_status, channel, is_amount_fixed,
    stat_date
from ydsh_dwd.dwd_order_tmp
where stat_month = '2024-09';

insert overwrite table ydsh_dwd.dwd_order partition (stat_date)
select
    order_id, user_id, store_id, order_timestamp,
    stat_year, stat_month, stat_hour,
    pay_amount, discount_amount, total_amount,
    pay_type, order_status, channel, is_amount_fixed,
    stat_date
from ydsh_dwd.dwd_order_tmp
where stat_month = '2024-10';

insert overwrite table ydsh_dwd.dwd_order partition (stat_date)
select
    order_id, user_id, store_id, order_timestamp,
    stat_year, stat_month, stat_hour,
    pay_amount, discount_amount, total_amount,
    pay_type, order_status, channel, is_amount_fixed,
    stat_date
from ydsh_dwd.dwd_order_tmp
where stat_month = '2024-11';

insert overwrite table ydsh_dwd.dwd_order partition (stat_date)
select
    order_id, user_id, store_id, order_timestamp,
    stat_year, stat_month, stat_hour,
    pay_amount, discount_amount, total_amount,
    pay_type, order_status, channel, is_amount_fixed,
    stat_date
from ydsh_dwd.dwd_order_tmp
where stat_month = '2024-12';


-- ---------------------------------------------------------------------
-- 2. 订单明细事实表：明细 + 订单的用户/日期（明细表自身不带下单日期）
--    同样按月分批，原因同上。
-- ---------------------------------------------------------------------
insert overwrite table ydsh_dwd.dwd_order_item partition (stat_date)
select
    i.item_id, i.order_id, o.user_id, i.product_id,
    i.quantity, i.price, i.discount, i.item_amount,
    o.stat_date
from ydsh_dwd.v_item_clean i
join ydsh_dwd.dwd_order_tmp o on i.order_id = o.order_id
where o.stat_month = '2024-01';

insert overwrite table ydsh_dwd.dwd_order_item partition (stat_date)
select
    i.item_id, i.order_id, o.user_id, i.product_id,
    i.quantity, i.price, i.discount, i.item_amount,
    o.stat_date
from ydsh_dwd.v_item_clean i
join ydsh_dwd.dwd_order_tmp o on i.order_id = o.order_id
where o.stat_month = '2024-02';

insert overwrite table ydsh_dwd.dwd_order_item partition (stat_date)
select
    i.item_id, i.order_id, o.user_id, i.product_id,
    i.quantity, i.price, i.discount, i.item_amount,
    o.stat_date
from ydsh_dwd.v_item_clean i
join ydsh_dwd.dwd_order_tmp o on i.order_id = o.order_id
where o.stat_month = '2024-03';

insert overwrite table ydsh_dwd.dwd_order_item partition (stat_date)
select
    i.item_id, i.order_id, o.user_id, i.product_id,
    i.quantity, i.price, i.discount, i.item_amount,
    o.stat_date
from ydsh_dwd.v_item_clean i
join ydsh_dwd.dwd_order_tmp o on i.order_id = o.order_id
where o.stat_month = '2024-04';

insert overwrite table ydsh_dwd.dwd_order_item partition (stat_date)
select
    i.item_id, i.order_id, o.user_id, i.product_id,
    i.quantity, i.price, i.discount, i.item_amount,
    o.stat_date
from ydsh_dwd.v_item_clean i
join ydsh_dwd.dwd_order_tmp o on i.order_id = o.order_id
where o.stat_month = '2024-05';

insert overwrite table ydsh_dwd.dwd_order_item partition (stat_date)
select
    i.item_id, i.order_id, o.user_id, i.product_id,
    i.quantity, i.price, i.discount, i.item_amount,
    o.stat_date
from ydsh_dwd.v_item_clean i
join ydsh_dwd.dwd_order_tmp o on i.order_id = o.order_id
where o.stat_month = '2024-06';

insert overwrite table ydsh_dwd.dwd_order_item partition (stat_date)
select
    i.item_id, i.order_id, o.user_id, i.product_id,
    i.quantity, i.price, i.discount, i.item_amount,
    o.stat_date
from ydsh_dwd.v_item_clean i
join ydsh_dwd.dwd_order_tmp o on i.order_id = o.order_id
where o.stat_month = '2024-07';

insert overwrite table ydsh_dwd.dwd_order_item partition (stat_date)
select
    i.item_id, i.order_id, o.user_id, i.product_id,
    i.quantity, i.price, i.discount, i.item_amount,
    o.stat_date
from ydsh_dwd.v_item_clean i
join ydsh_dwd.dwd_order_tmp o on i.order_id = o.order_id
where o.stat_month = '2024-08';

insert overwrite table ydsh_dwd.dwd_order_item partition (stat_date)
select
    i.item_id, i.order_id, o.user_id, i.product_id,
    i.quantity, i.price, i.discount, i.item_amount,
    o.stat_date
from ydsh_dwd.v_item_clean i
join ydsh_dwd.dwd_order_tmp o on i.order_id = o.order_id
where o.stat_month = '2024-09';

insert overwrite table ydsh_dwd.dwd_order_item partition (stat_date)
select
    i.item_id, i.order_id, o.user_id, i.product_id,
    i.quantity, i.price, i.discount, i.item_amount,
    o.stat_date
from ydsh_dwd.v_item_clean i
join ydsh_dwd.dwd_order_tmp o on i.order_id = o.order_id
where o.stat_month = '2024-10';

insert overwrite table ydsh_dwd.dwd_order_item partition (stat_date)
select
    i.item_id, i.order_id, o.user_id, i.product_id,
    i.quantity, i.price, i.discount, i.item_amount,
    o.stat_date
from ydsh_dwd.v_item_clean i
join ydsh_dwd.dwd_order_tmp o on i.order_id = o.order_id
where o.stat_month = '2024-11';

insert overwrite table ydsh_dwd.dwd_order_item partition (stat_date)
select
    i.item_id, i.order_id, o.user_id, i.product_id,
    i.quantity, i.price, i.discount, i.item_amount,
    o.stat_date
from ydsh_dwd.v_item_clean i
join ydsh_dwd.dwd_order_tmp o on i.order_id = o.order_id
where o.stat_month = '2024-12';


-- ---------------------------------------------------------------------
-- 3. 用户行为事实表：行为日期从行为时间截取
--    同样按月分批，保证与 1、2 节口径一致、可重复执行。
-- ---------------------------------------------------------------------
insert overwrite table ydsh_dwd.dwd_user_behavior partition (stat_date)
select
    behavior_id, user_id, product_id, behavior_type, behavior_time,
    substr(behavior_time, 1, 10) as stat_date
from ydsh_dwd.v_behavior_clean
where behavior_time is not null
  and substr(behavior_time, 1, 7) = '2024-01';

insert overwrite table ydsh_dwd.dwd_user_behavior partition (stat_date)
select
    behavior_id, user_id, product_id, behavior_type, behavior_time,
    substr(behavior_time, 1, 10) as stat_date
from ydsh_dwd.v_behavior_clean
where behavior_time is not null
  and substr(behavior_time, 1, 7) = '2024-02';

insert overwrite table ydsh_dwd.dwd_user_behavior partition (stat_date)
select
    behavior_id, user_id, product_id, behavior_type, behavior_time,
    substr(behavior_time, 1, 10) as stat_date
from ydsh_dwd.v_behavior_clean
where behavior_time is not null
  and substr(behavior_time, 1, 7) = '2024-03';

insert overwrite table ydsh_dwd.dwd_user_behavior partition (stat_date)
select
    behavior_id, user_id, product_id, behavior_type, behavior_time,
    substr(behavior_time, 1, 10) as stat_date
from ydsh_dwd.v_behavior_clean
where behavior_time is not null
  and substr(behavior_time, 1, 7) = '2024-04';

insert overwrite table ydsh_dwd.dwd_user_behavior partition (stat_date)
select
    behavior_id, user_id, product_id, behavior_type, behavior_time,
    substr(behavior_time, 1, 10) as stat_date
from ydsh_dwd.v_behavior_clean
where behavior_time is not null
  and substr(behavior_time, 1, 7) = '2024-05';

insert overwrite table ydsh_dwd.dwd_user_behavior partition (stat_date)
select
    behavior_id, user_id, product_id, behavior_type, behavior_time,
    substr(behavior_time, 1, 10) as stat_date
from ydsh_dwd.v_behavior_clean
where behavior_time is not null
  and substr(behavior_time, 1, 7) = '2024-06';

insert overwrite table ydsh_dwd.dwd_user_behavior partition (stat_date)
select
    behavior_id, user_id, product_id, behavior_type, behavior_time,
    substr(behavior_time, 1, 10) as stat_date
from ydsh_dwd.v_behavior_clean
where behavior_time is not null
  and substr(behavior_time, 1, 7) = '2024-07';

insert overwrite table ydsh_dwd.dwd_user_behavior partition (stat_date)
select
    behavior_id, user_id, product_id, behavior_type, behavior_time,
    substr(behavior_time, 1, 10) as stat_date
from ydsh_dwd.v_behavior_clean
where behavior_time is not null
  and substr(behavior_time, 1, 7) = '2024-08';

insert overwrite table ydsh_dwd.dwd_user_behavior partition (stat_date)
select
    behavior_id, user_id, product_id, behavior_type, behavior_time,
    substr(behavior_time, 1, 10) as stat_date
from ydsh_dwd.v_behavior_clean
where behavior_time is not null
  and substr(behavior_time, 1, 7) = '2024-09';

insert overwrite table ydsh_dwd.dwd_user_behavior partition (stat_date)
select
    behavior_id, user_id, product_id, behavior_type, behavior_time,
    substr(behavior_time, 1, 10) as stat_date
from ydsh_dwd.v_behavior_clean
where behavior_time is not null
  and substr(behavior_time, 1, 7) = '2024-10';

insert overwrite table ydsh_dwd.dwd_user_behavior partition (stat_date)
select
    behavior_id, user_id, product_id, behavior_type, behavior_time,
    substr(behavior_time, 1, 10) as stat_date
from ydsh_dwd.v_behavior_clean
where behavior_time is not null
  and substr(behavior_time, 1, 7) = '2024-11';

insert overwrite table ydsh_dwd.dwd_user_behavior partition (stat_date)
select
    behavior_id, user_id, product_id, behavior_type, behavior_time,
    substr(behavior_time, 1, 10) as stat_date
from ydsh_dwd.v_behavior_clean
where behavior_time is not null
  and substr(behavior_time, 1, 7) = '2024-12';


-- 4. 验收（每一条都必须通过，才允许进入 ADS 分析）
-- ---------------------------------------------------------------------

-- 4.1 分区是否生成、每个分区多少行
show partitions ydsh_dwd.dwd_order;
show partitions ydsh_dwd.dwd_order_item;
show partitions ydsh_dwd.dwd_user_behavior;

-- 4.2 行数守恒
select 'dwd_order'          as tbl, count(*) as cnt from ydsh_dwd.dwd_order
union all select 'dwd_order_tmp',   count(*) from ydsh_dwd.dwd_order_tmp
union all select 'dwd_order_item',  count(*) from ydsh_dwd.dwd_order_item
union all select 'dwd_user_behavior', count(*) from ydsh_dwd.dwd_user_behavior;

-- 4.3 度量不丢失：加载前后 GMV 必须一致（这是分区/分桶最容易出错的地方）
select 'tmp' as src, round(sum(pay_amount), 2) as gmv, count(*) as cnt from ydsh_dwd.dwd_order_tmp
union all
select 'dwd',          round(sum(pay_amount), 2),         count(*)          from ydsh_dwd.dwd_order;

-- 4.4 外键完整性：事实表里的 user_id / product_id 必须都能在维度表命中
select 'dwd_order.user_id 未匹配 dim_user' as check_item, count(*) as bad_cnt
  from ydsh_dwd.dwd_order o
  left join ydsh_dwd.dim_user d on o.user_id = d.user_id
 where d.user_id is null
union all
select 'dwd_order.store_id 未匹配 dim_store', count(*)
  from ydsh_dwd.dwd_order o
  left join ydsh_dwd.dim_store d on o.store_id = d.store_id
 where d.store_id is null
union all
select 'dwd_order_item.product_id 未匹配 dim_product', count(*)
  from ydsh_dwd.dwd_order_item i
  left join ydsh_dwd.dim_product d on i.product_id = d.product_id
 where d.product_id is null
union all
select 'dwd_user_behavior.user_id 未匹配 dim_user', count(*)
  from ydsh_dwd.dwd_user_behavior b
  left join ydsh_dwd.dim_user d on b.user_id = d.user_id
 where d.user_id is null;

-- 4.5 一致率：明细汇总额 vs 订单支付额（允许差额，用于识别运费/整单优惠）
--     若差异率 > 5%，说明 order_item 与 order 的金额口径需要业务确认
select
    round(sum(o.pay_amount), 2)                    as order_amount,
    round(sum(i.item_amount), 2)                    as item_amount,
    round((sum(i.item_amount) - sum(o.pay_amount)) * 100.0 / sum(o.pay_amount), 2) as diff_pct
from ydsh_dwd.dwd_order o
join (select order_id, sum(item_amount) as item_amount
        from ydsh_dwd.dwd_order_item group by order_id) i
  on o.order_id = i.order_id;

-- 4.6 分区裁剪验证：带 stat_date 条件应只扫一个分区
--     把下面两条 explain 的 "Partition" 部分对比一下即可
-- explain select count(*) from ydsh_dwd.dwd_order;                                -- 全表
-- explain select count(*) from ydsh_dwd.dwd_order where stat_date = '2025-06-01';  -- 单分区
