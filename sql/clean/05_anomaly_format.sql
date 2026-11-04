-- ============================================
-- 步骤 2：异常值与格式标准化
-- 说明：s1 层重建为基于第 1 周清洗成果（ydsh_dwd），避免重复劳动：
--       用户表取 dwd_user（年龄已均值填充），订单表取 dwd_order（已去重）
-- 金额策略：负值 → 0；超过 P99 → 截断为 P99（winsorize，不删单，避免误伤正常大额订单）
-- ============================================

-- 0. 重建 s1（改从第 1 周清洗成果出发）
drop table if exists dwd.ods_user_s1;
create table dwd.ods_user_s1 as
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
  email,
  is_email_missing
from ydsh_dwd.dwd_user;

drop table if exists dwd.ods_order_s1;
create table dwd.ods_order_s1 as
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
from ydsh_dwd.dwd_order;

-- 1. 异常值测量（清洗前）
select 'pay_amount<0' chk, count(*) cnt from dwd.ods_order_s1 where pay_amount < 0
union all select 'pay_amount null', count(*) from dwd.ods_order_s1 where pay_amount is null
union all select 'discount<0', count(*) from dwd.ods_order_s1 where discount_amount < 0
union all select 'age 异常', count(*) from dwd.ods_user_s1 where age is null or age<1 or age>120;

-- P99 阈值
select percentile_approx(pay_amount, 0.99) as p99, max(pay_amount) as mx from dwd.ods_order_s1;

-- 2. 格式检查（清洗前）
select 'register_date 非 yyyy-MM-dd' chk, count(*) cnt from dwd.ods_user_s1 where register_date is not null and register_date not regexp '^\\d{4}-\\d{2}-\\d{2}$'
union all select 'order_date 非 yyyy-MM-dd', count(*) from dwd.ods_order_s1 where order_date not regexp '^\\d{4}-\\d{2}-\\d{2}$'
union all select 'phone 非 1 开头 11 位', count(*) from dwd.ods_user_s1 where phone is not null and phone not regexp '^1\\d{10}$'
union all select 'phone 含分隔符', count(*) from dwd.ods_user_s1 where phone regexp '[- ]';

-- 3. 生成标准化后的 s2 表
-- 用户：日期/手机号统一（正则为幂等操作，格式本就规范的行不受影响）
-- register_date 有三种脏格式：yyyy/MM/dd、yyyyMMdd、规范值
drop table if exists dwd.ods_user_s2;
create table dwd.ods_user_s2 as
select
  user_id, user_name, gender, age, city, province,
  case when register_date regexp '^\\d{8}$'
       then concat(substr(register_date,1,4),'-',substr(register_date,5,2),'-',substr(register_date,7,2))
       else regexp_replace(register_date, '/', '-') end as register_date,
  member_level,
  regexp_replace(phone, '[- ]', '') as phone,
  email, is_email_missing
from dwd.ods_user_s1;

-- 订单：金额 winsorize（P99 截断、负值归 0）+ 日期统一 yyyy-MM-dd
drop table if exists dwd.ods_order_s2;
create table dwd.ods_order_s2 as
select
  o.order_id, o.user_id, o.store_id,
  regexp_replace(o.order_date, '/', '-') as order_date, o.order_time,
  case when o.pay_amount < 0 then 0
       when o.pay_amount > t.p99 then t.p99
       else o.pay_amount end as pay_amount,
  case when o.discount_amount < 0 then 0 else o.discount_amount end as discount_amount,
  o.pay_type, o.order_status, o.channel
from dwd.ods_order_s1 o
cross join (select percentile_approx(pay_amount, 0.99) as p99 from dwd.ods_order_s1) t;

-- 4. 验证（清洗后应为 0）
select 'pay_amount<0' chk, count(*) cnt from dwd.ods_order_s2 where pay_amount < 0
union all select 'pay_amount>P99', count(*) from dwd.ods_order_s2 o cross join (select percentile_approx(pay_amount,0.99) p99 from dwd.ods_order_s2) t where o.pay_amount > t.p99
union all select 'age 异常', count(*) from dwd.ods_user_s2 where age is null or age<1 or age>120
union all select 'phone 非 11 位', count(*) from dwd.ods_user_s2 where phone is not null and phone not regexp '^1\\d{10}$'
union all select 'order_date 非 yyyy-MM-dd', count(*) from dwd.ods_order_s2 where order_date not regexp '^\\d{4}-\\d{2}-\\d{2}$'
union all select 'register_date 非 yyyy-MM-dd', count(*) from dwd.ods_user_s2 where register_date not regexp '^\\d{4}-\\d{2}-\\d{2}$';
