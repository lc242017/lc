-- ============================================
-- 缺失值处理（步骤 8）
-- 说明：Hive 非 ACID 表不支持 UPDATE，按 Hive 实际可行方式
--       以 CTAS 生成清洗后明细表，不改动 ODS 原始数据
-- ============================================

create database if not exists ydsh_dwd;

-- 1. 用户表：年龄用 1~120 之间有效值的均值填充；邮箱缺失保留并标记
create table if not exists ydsh_dwd.dwd_user as
select
  u.user_id,
  u.user_name,
  u.gender,
  case when u.age is null or u.age < 1 or u.age > 120
       then a.avg_age else u.age end as age,
  u.city,
  u.province,
  u.register_date,
  u.member_level,
  u.phone,
  u.email,
  if(u.email is null or u.email = '', 1, 0) as is_email_missing
from ydsh_ods.ods_user u
cross join (
  select cast(round(avg(age)) as int) as avg_age
  from ydsh_ods.ods_user
  where age between 1 and 120
) a;

-- 2. 商品表：上架日期缺失用同分类众数日期补全
create table if not exists ydsh_dwd.dwd_product as
select
  p.product_id,
  p.product_name,
  p.category,
  p.sub_category,
  p.brand,
  p.price,
  p.cost,
  p.stock,
  p.status,
  if(p.launch_date is null or p.launch_date = '', m.mode_date, p.launch_date) as launch_date
from ydsh_ods.ods_product p
left join (
  select category, launch_date as mode_date
  from (
    select category, launch_date, count(*) cnt,
           row_number() over (partition by category order by count(*) desc) rn
    from ydsh_ods.ods_product
    where launch_date is not null and launch_date != ''
    group by category, launch_date
  ) t
  where rn = 1
) m on p.category = m.category;

-- 3. 验收：dwd_user 的 age 无空值、无负值、无超 120
select
  sum(case when age is null then 1 else 0 end) age_null,
  sum(case when age < 1 then 1 else 0 end) age_lt1,
  sum(case when age > 120 then 1 else 0 end) age_gt120,
  min(age) mn, max(age) mx
from ydsh_dwd.dwd_user;

-- 4. 验收：dwd_product 的 launch_date 无空值
select sum(case when launch_date is null or launch_date = '' then 1 else 0 end) bad_date
from ydsh_dwd.dwd_product;
