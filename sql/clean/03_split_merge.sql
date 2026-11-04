-- =====================================================================
-- 03_split_merge.sql   字段拆分合并 + 清洗结果落地（对应手册「步骤 3」）
-- ---------------------------------------------------------------------
-- 输入：02 产出的 v_user_clean / v_order_clean / v_behavior_clean / v_item_clean
-- 输出：
--   ydsh_dwd.dwd_user        用户清洗结果（供 dim_user 派生，也即手册步骤 4 的 dwd_user）
--   ydsh_dwd.dwd_order_tmp   订单清洗结果 + 完整时间戳（手册步骤 3 的 dwd_order_tmp）
--
-- 【与手册的差异】手册步骤 3 写作 `create table dwd_order_tmp as ... from dwd_order`，
--   但 dwd_order（分区表）要到步骤 6 才建，存在先读后建的顺序矛盾。本实现改为
--   从 v_order_clean 直接生成 tmp 表，链路单向、可重复执行，详见架构文档第 8 节。
-- =====================================================================

use ydsh_dwd;

-- ---------------------------------------------------------------------
-- 1. 用户明细：落地 + 派生分析用字段（年龄段、注册年月）
-- ---------------------------------------------------------------------
drop table if exists ydsh_dwd.dwd_user;

create table ydsh_dwd.dwd_user
stored as orc
tblproperties ('orc.compress' = 'SNAPPY')
as
select
    user_id,
    user_name,
    gender,
    age,
    case when age < 20 then '20岁以下'
         when age < 30 then '20-29岁'
         when age < 40 then '30-39岁'
         when age < 50 then '40-49岁'
         else '50岁及以上'
    end as age_group,
    member_level,
    phone,
    email,
    is_email_missing,
    city,
    province,
    register_date,
    substr(register_date, 1, 7) as register_month,
    is_age_fixed
from ydsh_dwd.v_user_clean;


-- ---------------------------------------------------------------------
-- 2. 订单：合并 order_date + order_time 为完整时间戳（手册步骤 3 核心动作）
--    并派生 年/月/日/小时，为时间维度与分时段分析做准备
-- ---------------------------------------------------------------------
drop table if exists ydsh_dwd.dwd_order_tmp;

create table ydsh_dwd.dwd_order_tmp
stored as orc
tblproperties ('orc.compress' = 'SNAPPY')
as
select
    order_id, user_id, store_id, order_timestamp,
    stat_date, stat_year, stat_month, stat_hour,
    pay_amount, discount_amount, total_amount,
    pay_type, order_status, channel, is_amount_fixed
from (
    select
        t.*,
        -- 行级去重：同一 order_id 保留"时间最晚 + 金额最大"的一条
        -- （第 1 周预评估：586 个主键重复、600 行冗余，去重后 15600 → 15000）
        row_number() over (
            partition by order_id
            order by order_timestamp desc, pay_amount desc
        ) as rn
    from (
        select
            order_id,
            user_id,
            store_id,

            -- 核心：拆分的日期 + 时间 → 合成为标准时间戳
            concat(order_date, ' ', order_time) as order_timestamp,

            -- 衍生时间维度字段
            order_date                            as stat_date,
            substr(order_date, 1, 4)              as stat_year,
            substr(order_date, 1, 7)              as stat_month,
            substr(order_time, 1, 2)              as stat_hour,

            pay_amount,
            discount_amount,
            round(pay_amount + discount_amount, 2) as total_amount,   -- 应收总额 = 实付 + 优惠
            pay_type,
            order_status,
            channel,
            is_amount_fixed
        from ydsh_dwd.v_order_clean
    ) t
) s
where s.rn = 1;


-- ---------------------------------------------------------------------
-- 3. 验收
-- ---------------------------------------------------------------------
-- 3.1 行数守恒：dwd_user 应 = ods_user（1000）；
--     dwd_order_tmp 应 = 15600 - 600 = 15000（与第 1 周预评估的 600 行冗余一致）
select 'ods.ods_user'        as tbl, 1000 as expect_cnt, count(*) as real_cnt from ydsh_ods.ods_user
union all select 'dwd.dwd_user',      1000, count(*) from ydsh_dwd.dwd_user
union all select 'ods.ods_order',    15600, count(*) from ydsh_ods.ods_order
union all select 'dwd.dwd_order_tmp', 15000, count(*) from ydsh_dwd.dwd_order_tmp;

-- 3.1.1 去重后主键必须唯一
select count(*) as dup_order_id_cnt
  from (select order_id from ydsh_dwd.dwd_order_tmp group by order_id having count(*) > 1) d;

-- 3.2 时间戳格式必须严格为 yyyy-MM-dd HH:mm:ss
select count(*) as bad_timestamp_cnt
  from ydsh_dwd.dwd_order_tmp
 where not (order_timestamp rlike '^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}$');

-- 3.3 日期跨度（确认分区范围合理，避免 1970-01-01 兜底值过多）
select min(stat_date) as min_date, max(stat_date) as max_date,
       count(distinct stat_date) as date_cnt,
       sum(case when stat_date = '1970-01-01' then 1 else 0 end) as fallback_date_cnt
  from ydsh_dwd.dwd_order_tmp;

-- 3.4 枚举收敛复核（每个字段 distinct 应为 2~5）
select 'gender' as field, count(distinct gender) as distinct_cnt from ydsh_dwd.dwd_user
union all select 'member_level', count(distinct member_level) from ydsh_dwd.dwd_user
union all select 'pay_type',     count(distinct pay_type)     from ydsh_dwd.dwd_order_tmp
union all select 'order_status', count(distinct order_status) from ydsh_dwd.dwd_order_tmp
union all select 'channel',      count(distinct channel)      from ydsh_dwd.dwd_order_tmp;
