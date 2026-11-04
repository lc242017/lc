-- =====================================================================
-- 12_etl_dim.sql   维度表加载（对应手册「步骤 6」维度部分）
-- ---------------------------------------------------------------------
-- 前置：03 已产出 dwd_user；10 已建好 4 张维度表
-- 加载方式：insert overwrite（幂等，可反复重跑，不会产生重复数据）
-- =====================================================================

use ydsh_dwd;

-- 关掉小文件合并和严格模式，避免空分区写入时报错
set hive.exec.dynamic.partition = true;
set hive.exec.dynamic.partition.mode = nonstrict;


-- ---------------------------------------------------------------------
-- 1. dim_user：来自清洗后的 dwd_user
-- ---------------------------------------------------------------------
insert overwrite table ydsh_dwd.dim_user
select
    row_number() over (order by user_id) as user_sk,
    user_id,
    user_name,
    gender,
    age,
    age_group,
    member_level,
    city,
    province,
    register_date,
    is_email_missing,
    current_timestamp() as etl_time
from ydsh_dwd.dwd_user;


-- ---------------------------------------------------------------------
-- 2. dim_product：价格带分箱 + 上架日期按品类众数补全
--    手册只要求"同分类众数日期补全"，这里把众数先算出来再 left join 回填，
--    避免在 select 里写相关子查询（Hive 不支持相关子查询）。
-- ---------------------------------------------------------------------
insert overwrite table ydsh_dwd.dim_product
select
    row_number() over (order by p.product_id) as product_sk,
    p.product_id,
    p.product_name,
    p.category,
    p.sub_category,
    p.brand,
    p.price,
    case when p.price is null or p.price < 50  then '50元以下'
         when p.price < 200                    then '50-199元'
         when p.price < 500                    then '200-499元'
         else '500元及以上'
    end as price_band,
    p.status,
    case when p.launch_date is null or trim(p.launch_date) = '' then m.mode_date
         else p.launch_date
    end as launch_date,
    case when p.launch_date is null or trim(p.launch_date) = '' then 1 else 0 end as is_launch_date_fixed,
    current_timestamp() as etl_time
from ydsh_dwd.v_product_enum p
left join (
    select category, launch_date as mode_date
      from (
        select category, launch_date,
               row_number() over (partition by category order by cnt desc, launch_date) as rn
          from (
                select category, launch_date, count(*) as cnt
                  from ydsh_ods.ods_product
                 where launch_date is not null and trim(launch_date) <> ''
                 group by category, launch_date
               ) a
      ) b
     where rn = 1
) m
  on p.category = m.category;


-- ---------------------------------------------------------------------
-- 3. dim_store：门店表无脏值，直接标准化
--    注：store_name 字段名以第 1 周数据字典为准；若 ODS 表中该列叫
--    shop_name / store_nm，请同步修改此处与 10_ddl_dim.sql 的列名。
-- ---------------------------------------------------------------------
insert overwrite table ydsh_dwd.dim_store
select
    row_number() over (order by store_id) as store_sk,
    store_id,
    store_name,
    city,
    province,
    open_date,
    current_timestamp() as etl_time
from ydsh_ods.ods_store;


-- ---------------------------------------------------------------------
-- 4. dim_date：序列生成 2024-01-01 ~ 2026-12-31 共 1096 天
-- ---------------------------------------------------------------------
insert overwrite table ydsh_dwd.dim_date
select
    date_format(d, 'yyyy-MM-dd')            as date_id,
    cast(date_format(d, 'yyyyMMdd') as int) as date_sk,
    year(d)                                 as year,
    quarter(d)                              as quarter,
    month(d)                                as month,
    day(d)                                  as day,
    weekofyear(d)                           as week_of_year,
    dayofweek(d)                            as day_of_week,
    case dayofweek(d) when 1 then '周日' when 2 then '周一' when 3 then '周二'
                       when 4 then '周三' when 5 then '周四' when 6 then '周五'
                       when 7 then '周六' end as day_name,
    case when dayofweek(d) in (1, 7) then 1 else 0 end as is_weekend,
    date_format(d, 'yyyy-MM')               as year_month,
    concat(cast(year(d) as string), '-Q', cast(quarter(d) as string)) as year_quarter
from (
    -- 【与手册/常见写法的差异】Hive 没有 sequence()（那是 Spark 函数），
    -- 直接写 explode(sequence(0,1095)) 会报 Invalid function sequence。
    -- 用 repeat(',',n) + split 造等长序列：n 个逗号切成 n+1 段，
    -- 再以日期上界过滤，多给几个不影响结果。
    select date_add(to_date('2024-01-01'), i) as d
      from (select posexplode(split(repeat(',', 1200), ',')) as (i, x)) s
     where date_add(to_date('2024-01-01'), i) <= to_date('2026-12-31')
) t;


-- ---------------------------------------------------------------------
-- 5. 验收
-- ---------------------------------------------------------------------
select 'dim_user'    as tbl, count(*) as cnt from ydsh_dwd.dim_user
union all select 'dim_product', count(*) from ydsh_dwd.dim_product
union all select 'dim_store',   count(*) from ydsh_dwd.dim_store
union all select 'dim_date',    count(*) from ydsh_dwd.dim_date;

-- 5.1 维度表主键唯一性
select 'dim_user.user_id' as pk, count(*) - count(distinct user_id) as dup_cnt from ydsh_dwd.dim_user
union all select 'dim_product.product_id', count(*) - count(distinct product_id) from ydsh_dwd.dim_product
union all select 'dim_store.store_id',     count(*) - count(distinct store_id)   from ydsh_dwd.dim_store
union all select 'dim_date.date_id',       count(*) - count(distinct date_id)    from ydsh_dwd.dim_date;

-- 5.2 补全效果：上架日期补了几行
select sum(is_launch_date_fixed) as launch_date_fixed_cnt from ydsh_dwd.dim_product;
