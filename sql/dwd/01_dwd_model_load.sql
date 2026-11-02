-- ============================================
-- 步骤 3：字段拆分合并 —— 订单日期+时间 → order_timestamp
-- 步骤 6：DWD 层维度建模（星型模型，ORC 存储）
-- 步骤 7：分区表数据加载（动态分区，按 order_date）
-- 补充说明：
--   · 手册步骤 8 的品类销售分析需要 product_id，而订单事实表是订单粒度
--     无商品维度，故补充一张订单明细粒度事实表 dwd_order_item 用于品类分析
--   · 手册的 member_level 映射会漏掉"钻石"，dim_user 建模时补全
-- ============================================

-- ========== 步骤 3：dwd_order_tmp ==========
drop table if exists dwd.dwd_order_tmp;
create table dwd.dwd_order_tmp as
select
  order_id,
  user_id,
  store_id,
  concat(order_date, ' ', order_time) as order_timestamp,
  pay_amount,
  discount_amount,
  pay_type,
  order_status,
  channel,
  order_date
from dwd.ods_order_s2;

-- 验证：时间戳格式
select 'order_timestamp 非 yyyy-MM-dd HH:mm:ss' chk, count(*) cnt
from dwd.dwd_order_tmp
where order_timestamp not regexp '^\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}$';

-- ========== 步骤 6：维度表（ORC）==========
drop table if exists dwd.dim_user;
create table dwd.dim_user
stored as orc
as
select
  user_id, user_name, gender, age, city, province, member_level
from dwd.ods_user_s2;

drop table if exists dwd.dim_product;
create table dwd.dim_product
stored as orc
as
select
  product_id,
  trim(product_name) as product_name,
  trim(category) as category,        -- 修复品类隐藏空格脏值
  trim(sub_category) as sub_category,
  trim(brand) as brand,
  price, launch_date
from ydsh_dwd.dwd_product;

drop table if exists dwd.dim_store;
create table dwd.dim_store
stored as orc
as
select
  store_id, store_name, province, city, district, manager
from ydsh_ods.ods_store;

-- ========== 步骤 6：订单事实表（分区 + ORC）==========
drop table if exists dwd.dwd_order_fact;
create table dwd.dwd_order_fact (
  order_id string,
  user_id string,
  store_id string,
  order_timestamp string,
  pay_amount double,
  discount_amount double,
  order_status string,
  channel string
)
partitioned by (order_date string)
stored as orc;

-- 订单明细事实表（商品粒度，供品类销售分析使用，ORC）
drop table if exists dwd.dwd_order_item_fact;
create table dwd.dwd_order_item_fact
stored as orc
as
select
  i.item_id,
  i.order_id,
  i.product_id,
  i.quantity,
  i.unit_price,
  i.discount
from ydsh_ods.ods_order_item i;

-- ========== 步骤 7：动态分区加载 ==========
set hive.exec.dynamic.partition = true;
set hive.exec.dynamic.partition.mode = nonstrict;
set hive.exec.max.dynamic.partitions = 1000;
set hive.exec.max.dynamic.partitions.pernode = 1000;

insert overwrite table dwd.dwd_order_fact partition (order_date)
select
  order_id, user_id, store_id, order_timestamp,
  pay_amount, discount_amount, order_status, channel,
  substr(order_date, 1, 10) as order_date
from dwd.dwd_order_tmp;

show partitions dwd.dwd_order_fact;
