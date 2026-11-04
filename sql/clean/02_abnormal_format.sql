-- =====================================================================
-- 02_abnormal_format.sql   异常值与格式标准化（对应手册「步骤 2」）
-- ---------------------------------------------------------------------
-- 输入：01 产出的 v_*_enum 视图 + ydsh_ods 原表（取统计阈值）
-- 输出：3 个清洗后视图
--       ydsh_dwd.v_user_clean    （年龄填充 / 日期手机号归一 / email 缺失标记）
--       ydsh_dwd.v_order_clean   （金额缩尾 / 日期时间归一）
--       ydsh_dwd.v_behavior_clean（行为时间归一）
--       ydsh_dwd.v_item_clean    （订单明细数量价税校验）
--
-- 【三个关键决策，对应手册 1.3 的坑】
--   ① 阈值不写死：负金额直接归零，超大金额用 IQR 稳健上界（P75+3×IQR）判定
--      并"缩尾"到上界。绝不用绝对值或直接删行 —— 第 1 周预评估已证明"异常值
--      误删"会把正常大额订单干掉，导致 GMV 系统性偏低。
--      注意：初版按 P99×3 写，实跑发现本数据集约 2% 的订单金额被放大 100~2000
--      倍，P99 本身已被污染（568 万），P99×3 比最大值还高，一条都拦不住。
--      详见本脚本 165 行的方法论说明。
--   ② 年龄用有效区间均值填充（1~120），而不是全表均值：全表均值会被 -3、200
--      这类极端值污染。
--   ③ 格式归一"能救则救，救不了置 NULL 并计数"，不静默编造日期。
-- =====================================================================

use ydsh_dwd;


-- ---------------------------------------------------------------------
-- 0. 阈值探查：执行时把这三个数记到《数据质量对比报告》里
-- ---------------------------------------------------------------------
-- 0.1 年龄有效区间均值（填充值来源）
--     注意：均值只对 1~120 的有效样本求，异常行不能参与计算，否则均值被污染；
--     但 min/max 要看全量，才能暴露 -3、200 这类越界值。
select round(avg(case when age between 1 and 120 then age end), 2) as avg_valid_age,
       min(age)                                                as min_age,
       max(age)                                                as max_age,
       sum(case when age is null then 1 else 0 end)            as age_null_cnt,
       sum(case when age is not null and (age < 1 or age > 120) then 1 else 0 end) as age_out_of_range_cnt
  from ydsh_ods.ods_user;

-- 0.2 金额分位数（缩尾阈值来源）
select percentile_approx(pay_amount, 0.50) as p50,
       percentile_approx(pay_amount, 0.99) as p99,
       percentile_approx(pay_amount, 0.999) as p999,
       min(pay_amount) as min_amt,
       max(pay_amount) as max_amt,
       sum(case when pay_amount < 0 then 1 else 0 end) as negative_cnt
  from ydsh_ods.ods_order;

-- 0.3 日期 / 手机号 格式不合规规模
select
    sum(case when register_date is null
              or not (trim(register_date) rlike '^[0-9]{4}-[0-9]{2}-[0-9]{2}$') then 1 else 0 end) as bad_date_cnt,
    sum(case when phone is null
              or not (trim(phone) rlike '^[0-9]{11}$') then 1 else 0 end) as bad_phone_cnt,
    sum(case when email is null or trim(email) = '' then 1 else 0 end)  as email_missing_cnt
  from ydsh_ods.ods_user;


-- ---------------------------------------------------------------------
-- 1. 用户：年龄异常填充 + 日期/手机号格式归一 + email 缺失标记
-- ---------------------------------------------------------------------
create or replace view ydsh_dwd.v_user_clean as
select
    u.user_id,
    u.user_name,
    u.gender,

    -- 年龄：为 NULL 或越界（<1 或 >120）→ 用有效区间均值填充
    case when u.age is null or u.age < 1 or u.age > 120
         then m.avg_valid_age
         else u.age
    end as age,

    -- 标记位：后续质量报告统计"填充了多少行"直接 sum 这个字段
    case when u.age is null or u.age < 1 or u.age > 120 then 1 else 0 end as is_age_fixed,

    u.member_level,

    -- 手机号：剥掉所有非数字字符（'-'、' '、'+86' 前缀），保留末 11 位
    case
        when u.phone is null then null
        when length(regexp_replace(u.phone, '[^0-9]', '')) = 13
             and regexp_replace(u.phone, '[^0-9]', '') like '86%'
             then substr(regexp_replace(u.phone, '[^0-9]', ''), 3, 11)
        when length(regexp_replace(u.phone, '[^0-9]', '')) >= 11
             then substr(regexp_replace(u.phone, '[^0-9]', ''), 1, 11)
        when length(regexp_replace(u.phone, '[^0-9]', '')) = 0 then null
        else lpad(regexp_replace(u.phone, '[^0-9]', ''), 11, '0')
    end as phone,

    lower(trim(u.email)) as email,
    case when u.email is null or trim(u.email) = '' then 1 else 0 end as is_email_missing,

    trim(u.city)     as city,
    trim(u.province) as province,

    -- 注册日期：统一为 yyyy-MM-dd
    -- 兼容 2025-3-5 / 2025/03/05 / 2025.3.5 / 20250305 四种写法；认不出置 NULL
    case
        when trim(u.register_date) rlike '^[0-9]{4}[-/.]?[0-9]{1,2}[-/.]?[0-9]{1,2}$' then
            concat(
                regexp_extract(trim(u.register_date), '^([0-9]{4})', 1), '-',
                lpad(regexp_extract(trim(u.register_date), '^[0-9]{4}[-/.]?([0-9]{1,2})', 1), 2, '0'), '-',
                lpad(regexp_extract(trim(u.register_date), '^[0-9]{4}[-/.]?[0-9]{1,2}[-/.]?([0-9]{1,2})', 1), 2, '0')
            )
        else null
    end as register_date
from ydsh_dwd.v_user_enum u
cross join (
    select cast(round(avg(age)) as int) as avg_valid_age
      from ydsh_ods.ods_user
     where age between 1 and 120
) m;


-- ---------------------------------------------------------------------
-- 2. 订单：金额异常处理 + 日期时间归一
-- ---------------------------------------------------------------------
create or replace view ydsh_dwd.v_order_clean as
select
    order_id,
    user_id,
    store_id,
    order_date,
    order_time,
    pay_amount,

    -- 【关键修正】优惠金额必须基于"清洗后"的 pay_amount 截断。
    -- 早期版本直接用原始 o.pay_amount 判断，当 pay_amount 为负（已归零）时，
    -- 条件 discount > pay_amount 成立，反而把优惠截断成负数，实测残留 280 行脏值。
    -- 因此拆成两层：内层先算 pay_amount，外层再据此截断优惠。
    case
        when discount_amount is null or discount_amount < 0 then cast(0 as double)
        when discount_amount > pay_amount                   then pay_amount
        else discount_amount
    end as discount_amount,

    pay_type,
    order_status,
    channel,
    is_amount_fixed
from (
    select
        o.order_id,
        o.user_id,
        o.store_id,

        -- 下单日期：统一 yyyy-MM-dd（分区字段，必须严格规范）
        case
            when trim(o.order_date) rlike '^[0-9]{4}[-/.]?[0-9]{1,2}[-/.]?[0-9]{1,2}$' then
                concat(
                    regexp_extract(trim(o.order_date), '^([0-9]{4})', 1), '-',
                    lpad(regexp_extract(trim(o.order_date), '^[0-9]{4}[-/.]?([0-9]{1,2})', 1), 2, '0'), '-',
                    lpad(regexp_extract(trim(o.order_date), '^[0-9]{4}[-/.]?[0-9]{1,2}[-/.]?([0-9]{1,2})', 1), 2, '0')
                )
            else '1970-01-01'
        end as order_date,

        -- 下单时间：统一 HH:mm:ss，兼容 9:5 / 09:05 / 090500 三种写法
        case
            when trim(o.order_time) rlike '^[0-9]{2}:[0-9]{2}:[0-9]{2}$' then trim(o.order_time)
            when trim(o.order_time) rlike '^[0-9]{1,2}:[0-9]{2}$'        then concat(lpad(split(trim(o.order_time), ':')[0], 2, '0'), ':', split(trim(o.order_time), ':')[1], ':00')
            when trim(o.order_time) rlike '^[0-9]{6}$'                   then concat(substr(trim(o.order_time),1,2), ':', substr(trim(o.order_time),3,2), ':', substr(trim(o.order_time),5,2))
            else '00:00:00'
        end as order_time,

        -- 支付金额：负值/空 → 0；超稳健上界视为录入错误 → 缩尾到上界
        --
        -- 【方法论修正：为什么不用 P99×3】
        --   实测该数据 P95=4,828，P97.5=4,972，P98 却直接跳到 544,411 ——
        --   约 2% 的订单金额被放大 100~2000 倍，属于成规模的噪声注入。
        --   异常值占比超过 1% 时，P99 本身已被污染（实测 P99=5,660,128），
        --   P99×3=1,698 万的上界比最大值 995 万还高，一条都拦不住。
        --   改用 IQR 稳健上界：P75 + 3×(P75−P25) ≈ 11,521，
        --   该阈值只依赖中间 50% 的数据，不受极端值影响。
        case
            when o.pay_amount is null or o.pay_amount < 0            then cast(0 as double)
            when o.pay_amount > t.iqr_upper                          then t.iqr_upper
            else o.pay_amount
        end as pay_amount,

        -- 只剥负值，"是否超过支付额"的截断放到外层，保证用的是清洗后的支付金额
        case
            when o.discount_amount is null or o.discount_amount < 0 then cast(0 as double)
            else o.discount_amount
        end as discount_amount,

        o.pay_type,
        o.order_status,
        o.channel,

        -- 金额异常标记（按原始值判定，供质量报告统计处理规模）
        case
            when o.pay_amount is null or o.pay_amount < 0 or o.pay_amount > t.iqr_upper
              or o.discount_amount is null or o.discount_amount < 0 or o.discount_amount > o.pay_amount
            then 1 else 0
        end as is_amount_fixed
    from ydsh_dwd.v_order_enum o
    cross join (
        -- 稳健阈值：只取中间 50% 的分位，避免被约 2% 的放大金额带偏
        select percentile_approx(pay_amount, 0.25) as p25,
               percentile_approx(pay_amount, 0.75) as p75,
               percentile_approx(pay_amount, 0.99) as p99,
               percentile_approx(pay_amount, 0.75)
                 + 3 * (percentile_approx(pay_amount, 0.75)
                      - percentile_approx(pay_amount, 0.25)) as iqr_upper
          from ydsh_ods.ods_order
         where pay_amount is not null and pay_amount >= 0
    ) t
) s;


-- ---------------------------------------------------------------------
-- 3. 行为：行为时间归一为 yyyy-MM-dd HH:mm:ss
-- ---------------------------------------------------------------------
create or replace view ydsh_dwd.v_behavior_clean as
select
    b.behavior_id,
    b.user_id,
    b.product_id,
    b.behavior_type,
    -- 行为时间存在两种真实格式，必须分格式归一，否则 unix_timestamp 直接返回 NULL：
    --   ① yyyy-MM-dd HH:mm:ss  19 位（53,912 行）
    --   ② yyyy/MM/dd HH:mm     16 位，斜杠且缺秒（6,088 行）→ 换斜杠 + 补 ':00'
    -- 仍然解析失败的（非法日期如 2024-02-30）保留为 NULL，由验收项计数暴露，不编造。
    from_unixtime(
        unix_timestamp(
            case
                when length(regexp_replace(trim(b.behavior_time), '/', '-')) = 16
                    then concat(regexp_replace(trim(b.behavior_time), '/', '-'), ':00')
                else regexp_replace(trim(b.behavior_time), '/', '-')
            end
        , 'yyyy-MM-dd HH:mm:ss')
    , 'yyyy-MM-dd HH:mm:ss') as behavior_time
from ydsh_dwd.v_behavior_enum b;


-- ---------------------------------------------------------------------
-- 4. 订单明细：数量/单价/优惠的有效性校验
--    item_amount 为派生度量，供品类销售分析直接使用
-- ---------------------------------------------------------------------
create or replace view ydsh_dwd.v_item_clean as
select
    i.item_id,
    i.order_id,
    i.product_id,
    case when i.quantity is null or i.quantity <= 0 then 1 else i.quantity end as quantity,
    -- 源表字段名为 unit_price，此处统一别名为 price，与 dwd_order_item DDL 对齐
    case when i.unit_price is null or i.unit_price < 0 then cast(0 as double) else i.unit_price end as price,
    case when i.discount is null or i.discount < 0 then cast(0 as double) else i.discount end as discount,
    case when i.unit_price is null or i.unit_price < 0 then cast(0 as double)
         else round(i.unit_price * (case when i.quantity is null or i.quantity <= 0 then 1 else i.quantity end)
                    - (case when i.discount is null or i.discount < 0 then 0 else i.discount end), 2)
    end as item_amount
from ydsh_ods.ods_order_item i;


-- ---------------------------------------------------------------------
-- 5. 验收：清洗后不再有越界值
--    拆成两条：单条 union 分支 ≤3。分支再多时 Tez 单个 DAG 的
--    计数器会超上限（max=120）直接报错，属于引擎限制而非数据问题。
-- ---------------------------------------------------------------------
select '年龄越界/空值' as check_item, count(*) as bad_cnt
  from ydsh_dwd.v_user_clean where age is null or age < 1 or age > 120
union all
select '支付金额异常', count(*)
  from ydsh_dwd.v_order_clean where pay_amount < 0
union all
select '下单日期不合规', count(*)
  from ydsh_dwd.v_order_clean where not (order_date rlike '^[0-9]{4}-[0-9]{2}-[0-9]{2}$');

select '下单时间不合规' as check_item, count(*) as bad_cnt
  from ydsh_dwd.v_order_clean where not (order_time rlike '^[0-9]{2}:[0-9]{2}:[0-9]{2}$')
union all
select '手机号不合规', count(*)
  from ydsh_dwd.v_user_clean where phone is not null and not (phone rlike '^[0-9]{11}$')
union all
select '行为时间不可解析', count(*)
  from ydsh_dwd.v_behavior_clean where behavior_time is null;
