-- ============================================
-- ODS 层建表脚本（云购生活新零售数仓）
-- 6 张表，字段与 CSV 一致，逗号分隔，跳过表头
-- ============================================

create database if not exists ydsh_ods;

-- 1. 用户表
create table if not exists ydsh_ods.ods_user (
  user_id string,
  user_name string,
  gender string,
  age int,
  city string,
  province string,
  register_date string,
  member_level string,
  phone string,
  email string
)
row format delimited fields terminated by ','
tblproperties ('skip.header.line.count' = '1');

-- 2. 商品表
create table if not exists ydsh_ods.ods_product (
  product_id string,
  product_name string,
  category string,
  sub_category string,
  brand string,
  price double,
  cost double,
  stock int,
  status string,
  launch_date string
)
row format delimited fields terminated by ','
tblproperties ('skip.header.line.count' = '1');

-- 3. 门店表
create table if not exists ydsh_ods.ods_store (
  store_id string,
  store_name string,
  province string,
  city string,
  district string,
  address string,
  open_date string,
  area int,
  manager string
)
row format delimited fields terminated by ','
tblproperties ('skip.header.line.count' = '1');

-- 4. 订单表
create table if not exists ydsh_ods.ods_order (
  order_id string,
  user_id string,
  store_id string,
  order_date string,
  order_time string,
  pay_amount double,
  discount_amount double,
  pay_type string,
  order_status string,
  channel string
)
row format delimited fields terminated by ','
tblproperties ('skip.header.line.count' = '1');

-- 5. 订单明细表
create table if not exists ydsh_ods.ods_order_item (
  item_id string,
  order_id string,
  product_id string,
  quantity int,
  unit_price double,
  discount double
)
row format delimited fields terminated by ','
tblproperties ('skip.header.line.count' = '1');

-- 6. 用户行为表
create table if not exists ydsh_ods.ods_user_behavior (
  behavior_id string,
  user_id string,
  product_id string,
  behavior_type string,
  behavior_time string,
  session_id string
)
row format delimited fields terminated by ','
tblproperties ('skip.header.line.count' = '1');
