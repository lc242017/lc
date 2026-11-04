-- ============================================
-- 步骤 1：枚举字段标准化
-- 依据第 1 周《数据质量预评估表》扫描出的全部脏取值逐一映射
-- 映射原则：中英文/大小写归一；空值归入语义最近或最保守的规范值
-- 说明：order_status 数字代码按行业惯例映射（1待支付 2已支付 3已完成 4已取消）
-- ============================================

create database if not exists dwd;

-- 1. 用户表：gender + member_level
create table if not exists dwd.ods_user_s1 as
select
  user_id,
  user_name,
  case when gender in ('男','M','male','Male') then '男'
       when gender in ('女','F','female','Female') then '女'
       else '未知' end as gender,
  age,
  city,
  province,
  register_date,
  case when member_level in ('金卡会员','金卡','gold','Gold') then '金卡会员'
       when member_level in ('银卡会员','银卡','silver','Silver') then '银卡会员'
       when member_level in ('钻石会员','钻石','diamond','Diamond') then '钻石会员'
       when member_level in ('普通会员','普通','normal','Normal') then '普通会员'
       else '普通会员' end as member_level,
  phone,
  email
from ydsh_ods.ods_user;

-- 2. 订单表：pay_type + order_status + channel
create table if not exists dwd.ods_order_s1 as
select
  order_id,
  user_id,
  store_id,
  order_date,
  order_time,
  pay_amount,
  discount_amount,
  case when pay_type in ('微信支付','微信','wechat','WeChat') then '微信支付'
       when pay_type in ('支付宝','alipay','Alipay') then '支付宝'
       when pay_type = '货到付款' then '货到付款'
       when pay_type = '银行卡' then '银行卡'
       else pay_type end as pay_type,
  case when order_status in ('待支付','1') then '待支付'
       when order_status in ('已支付','已付款','2') then '已支付'
       when order_status in ('已完成','完成','3') then '已完成'
       when order_status in ('已取消','cancelled','4') then '已取消'
       when order_status = '退款中' then '退款中'
       else order_status end as order_status,
  case when channel in ('APP','app') then 'APP'
       when channel in ('PC官网','pc','PC') then 'PC官网'
       when channel = '小程序' then '小程序'
       when channel = '门店' then '门店'
       else channel end as channel
from ydsh_ods.ods_order;

-- 3. 用户行为表：behavior_type
create table if not exists dwd.ods_user_behavior_s1 as
select
  behavior_id,
  user_id,
  product_id,
  case when behavior_type in ('pv','PV','浏览') then '浏览'
       when behavior_type in ('cart','Cart','加购') then '加购'
       when behavior_type in ('fav','Fav','收藏') then '收藏'
       when behavior_type in ('buy','Buy','购买') then '购买'
       else behavior_type end as behavior_type,
  behavior_time,
  session_id
from ydsh_ods.ods_user_behavior;

-- 4. 验证：distinct 收敛
select 'user.gender' f, count(distinct gender) vals from dwd.ods_user_s1
union all select 'user.member_level', count(distinct member_level) from dwd.ods_user_s1
union all select 'order.pay_type', count(distinct pay_type) from dwd.ods_order_s1
union all select 'order.order_status', count(distinct order_status) from dwd.ods_order_s1
union all select 'order.channel', count(distinct channel) from dwd.ods_order_s1
union all select 'behavior.behavior_type', count(distinct behavior_type) from dwd.ods_user_behavior_s1;
