-- =====================================================================
-- 04_quality_report.sql   数据质量对比报告（对应手册「步骤 4」）
-- ---------------------------------------------------------------------
-- 前置：01 → 02 → 03 已跑通（依赖 v_*_enum / v_*_clean / dwd_user / dwd_order_tmp）
-- 输出：ydsh_dwd.dwd_data_quality_report   五类脏数据清洗前后对比明细
--
-- 【口径声明 —— 本报告最重要的一段】
--   1) 不做任何"估算"，before/after 全部 SQL 实测：
--        before_cnt = 查 ydsh_ods 原表
--        after_cnt  = 查清洗后的 dwd_user / dwd_order_tmp / v_*_clean
--      fix_rate = (before - after) / before，before = 0 时输出 NULL（无脏数据谈不上修复率）
--   2) 枚举类统一用"值域校验"判定，而不是"清洗前后自比"：
--        不规范 = 字段取值不在规范值域内（含 NULL、'其他'、'未知' 以外的任何脏值）
--      这样 after 才有独立判据，不会出现"自己和自己比必然 100%"的假结论。
--   3) 执行完把 select * 的结果原样贴进《数据质量对比报告》，不要手填。
-- =====================================================================

use ydsh_dwd;

-- ---------------------------------------------------------------------
-- 0. P99 阈值单独落表，供多个分支复用（Hive 不支持 WHERE 内标量子查询）
-- ---------------------------------------------------------------------
drop table if exists ydsh_dwd.tmp_p99;
create table ydsh_dwd.tmp_p99 stored as orc as
select percentile_approx(pay_amount, 0.25)  as p25,
       percentile_approx(pay_amount, 0.75)  as p75,
       percentile_approx(pay_amount, 0.99)  as p99,
       percentile_approx(pay_amount, 0.999) as p999,
       -- 稳健上界：P75 + 3×IQR。约 2% 的订单金额被放大 100~2000 倍，
       -- 异常占比超过 1% 时 P99 本身已被污染，P99×3 完全失效。
       percentile_approx(pay_amount, 0.75)
         + 3 * (percentile_approx(pay_amount, 0.75)
              - percentile_approx(pay_amount, 0.25)) as iqr_upper
  from ydsh_ods.ods_order
 where pay_amount is not null and pay_amount >= 0;

select * from ydsh_dwd.tmp_p99;


-- ---------------------------------------------------------------------
-- 1. 报告表结构
-- ---------------------------------------------------------------------
drop table if exists ydsh_dwd.dwd_data_quality_report;
create table ydsh_dwd.dwd_data_quality_report (
    dirty_type  string  comment '脏数据类别（缺失/重复/枚举/异常/格式）',
    item        string  comment '具体检查项',
    before_cnt  bigint  comment '清洗前行数',
    after_cnt   bigint  comment '清洗后残留行数',
    fix_rate    double  comment '修复率 = (before-after)/before*100',
    note        string  comment '备注：阈值、处理方式、口径说明'
) stored as orc
tblproperties ('orc.compress' = 'SNAPPY');


-- ---------------------------------------------------------------------
-- 2. 灌数：五类脏数据逐项对比
-- ---------------------------------------------------------------------
insert overwrite table ydsh_dwd.dwd_data_quality_report
-- 2.1 ① 缺失值
select '① 缺失值' as dirty_type, '用户 age 为空或越界（非 1~120）' as item,
       b.cnt_1_1 as before_cnt, a.cnt_1_2 as after_cnt,
       case when b.cnt_1_1 = 0 then null else round((b.cnt_1_1 - a.cnt_1_2) * 100.0 / b.cnt_1_1, 2) end as fix_rate,
       concat('有效区间均值填充，修复 ', b.cnt_1_1 - a.cnt_1_2, ' 行') as note
  from (select count(*) as cnt_1_1 from ydsh_ods.ods_user
         where age is null or age < 1 or age > 120) b
 cross join (select count(*) as cnt_1_2 from ydsh_dwd.dwd_user
         where age is null or age < 1 or age > 120) a
union all
select '① 缺失值', '用户 email 为空',
       b.cnt_2_1, a.cnt_2_2,
       case when b.cnt_2_1 = 0 then null else round((b.cnt_2_1 - a.cnt_2_2) * 100.0 / b.cnt_2_1, 2) end,
       '业务上不可推断，不填充；改为 is_email_missing=1 标记保留，故修复率 0% 属预期'
  from (select count(*) as cnt_2_1 from ydsh_ods.ods_user where email is null or trim(email) = '') b
 cross join (select count(*) as cnt_2_2 from ydsh_dwd.dwd_user where is_email_missing = 1) a
;

insert into table ydsh_dwd.dwd_data_quality_report
select '① 缺失值', '订单明细 quantity / price 无效',
       b.cnt_3_1, a.cnt_3_2,
       case when b.cnt_3_1 = 0 then null else round((b.cnt_3_1 - a.cnt_3_2) * 100.0 / b.cnt_3_1, 2) end,
       'quantity<=0 重置为 1；price<0 置 0'
  from (select count(*) as cnt_3_1 from ydsh_ods.ods_order_item
         where quantity is null or quantity <= 0 or unit_price is null or unit_price < 0) b
 cross join (select count(*) as cnt_3_2 from ydsh_dwd.v_item_clean
         where quantity is null or quantity <= 0 or price is null or price < 0) a

-- 2.2 ② 重复值
union all
select '② 重复值', '订单主键 order_id 重复的冗余行数',
       b.cnt_4_1, a.cnt_4_2,
       case when b.cnt_4_1 = 0 then null else round((b.cnt_4_1 - a.cnt_4_2) * 100.0 / b.cnt_4_1, 2) end,
       'row_number() 按时间倒序 + 金额倒序保留 1 条；15600 → 15000'
  from (select count(*) - count(distinct order_id) as cnt_4_1 from ydsh_ods.ods_order) b
 cross join (select count(*) - count(distinct order_id) as cnt_4_2 from ydsh_dwd.dwd_order_tmp) a

-- 2.3 ③ 枚举不规范（值域校验口径）
;

insert into table ydsh_dwd.dwd_data_quality_report
select '③ 枚举不规范', '用户枚举 gender / member_level 不在规范值域',
       b.cnt_5_1, a.cnt_5_2,
       case when b.cnt_5_1 = 0 then null else round((b.cnt_5_1 - a.cnt_5_2) * 100.0 / b.cnt_5_1, 2) end,
       '值域：男/女/未知；钻石会员/金卡会员/银卡会员/普通会员'
  from (select count(*) as cnt_5_1 from ydsh_ods.ods_user
         where nvl(gender, '') not in ('男', '女', '未知')
            or nvl(member_level, '') not in ('钻石会员', '金卡会员', '银卡会员', '普通会员')) b
 cross join (select count(*) as cnt_5_2 from ydsh_dwd.dwd_user
         where nvl(gender, '') not in ('男', '女', '未知')
            or nvl(member_level, '') not in ('钻石会员', '金卡会员', '银卡会员', '普通会员')) a
union all
select '③ 枚举不规范', '订单枚举 pay_type / order_status / channel 不在规范值域',
       b.cnt_6_1, a.cnt_6_2,
       case when b.cnt_6_1 = 0 then null else round((b.cnt_6_1 - a.cnt_6_2) * 100.0 / b.cnt_6_1, 2) end,
       '值域：支付宝/微信支付/银行卡/货到付款；待支付/已支付/已完成/已取消/退款中；APP/PC官网/小程序/门店'
  from (select count(*) as cnt_6_1 from ydsh_ods.ods_order
         where nvl(pay_type, '')     not in ('支付宝', '微信支付', '银行卡', '货到付款')
            or nvl(order_status, '') not in ('待支付', '已支付', '已完成', '已取消', '退款中')
            or nvl(channel, '')      not in ('APP', 'PC官网', '小程序', '门店')) b
 cross join (select count(*) as cnt_6_2 from ydsh_dwd.dwd_order_tmp
         where nvl(pay_type, '')     not in ('支付宝', '微信支付', '银行卡', '货到付款')
            or nvl(order_status, '') not in ('待支付', '已支付', '已完成', '已取消', '退款中')
            or nvl(channel, '')      not in ('APP', 'PC官网', '小程序', '门店')) a
;

insert into table ydsh_dwd.dwd_data_quality_report
select '③ 枚举不规范', '用户行为类型不在规范值域',
       b.cnt_7_1, a.cnt_7_2,
       case when b.cnt_7_1 = 0 then null else round((b.cnt_7_1 - a.cnt_7_2) * 100.0 / b.cnt_7_1, 2) end,
       '值域：浏览/加购/收藏/购买（pv、PV、cart、Cart、fav、buy 等全部归并）'
  from (select count(*) as cnt_7_1 from ydsh_ods.ods_user_behavior
         where nvl(behavior_type, '') not in ('浏览', '加购', '收藏', '购买')) b
 cross join (select count(*) as cnt_7_2 from ydsh_dwd.v_behavior_clean
         where nvl(behavior_type, '') not in ('浏览', '加购', '收藏', '购买')) a

-- 2.4 ④ 异常值
union all
select '④ 异常值', '支付金额为空 / 为负 / 超 IQR 稳健上界',
       b.cnt_8_1, a.cnt_8_2,
       case when b.cnt_8_1 = 0 then null else round((b.cnt_8_1 - a.cnt_8_2) * 100.0 / b.cnt_8_1, 2) end,
       concat('P75=', cast(round(p.p75, 2) as string),
              '，IQR 稳健上界=', cast(round(p.iqr_upper, 2) as string),
              '（P99=', cast(round(p.p99, 2) as string), ' 已被异常值污染，不采用）',
              '；负值归零、超阈值缩尾，不删行')
  from (select count(*) as cnt_8_1
          from ydsh_ods.ods_order o cross join ydsh_dwd.tmp_p99 q
         where o.pay_amount is null or o.pay_amount < 0 or o.pay_amount > q.iqr_upper) b
 cross join (select count(*) as cnt_8_2
          from ydsh_dwd.dwd_order_tmp t cross join ydsh_dwd.tmp_p99 q
         where t.pay_amount < 0 or t.pay_amount > q.iqr_upper) a
 cross join (select p75, p99, iqr_upper from ydsh_dwd.tmp_p99) p
;

insert into table ydsh_dwd.dwd_data_quality_report
select '④ 异常值', '优惠金额为负 / 大于支付金额',
       b.cnt_9_1, a.cnt_9_2,
       case when b.cnt_9_1 = 0 then null else round((b.cnt_9_1 - a.cnt_9_2) * 100.0 / b.cnt_9_1, 2) end,
       '负值归零；超过支付额则截断为支付额，保证实付不为负'
  from (select count(*) as cnt_9_1 from ydsh_ods.ods_order
         where discount_amount is null or discount_amount < 0 or discount_amount > pay_amount) b
 cross join (select count(*) as cnt_9_2 from ydsh_dwd.dwd_order_tmp
         where discount_amount < 0 or discount_amount > pay_amount) a

-- 2.5 ⑤ 格式不规范
union all
select '⑤ 格式不规范', '用户注册日期非 yyyy-MM-dd',
       b.cnt_10_1, a.cnt_10_2,
       case when b.cnt_10_1 = 0 then null else round((b.cnt_10_1 - a.cnt_10_2) * 100.0 / b.cnt_10_1, 2) end,
       '兼容 2025-3-5 / 2025/03/05 / 2025.3.5 / 20250305；认不出置 NULL，不编造'
  from (select count(*) as cnt_10_1 from ydsh_ods.ods_user
         where register_date is null
            or not (trim(register_date) rlike '^[0-9]{4}-[0-9]{2}-[0-9]{2}$')) b
 cross join (select count(*) as cnt_10_2 from ydsh_dwd.dwd_user
         where register_date is null
            or not (register_date rlike '^[0-9]{4}-[0-9]{2}-[0-9]{2}$')) a
;

insert into table ydsh_dwd.dwd_data_quality_report
select '⑤ 格式不规范', '用户手机号含分隔符或非 11 位',
       b.cnt_11_1, a.cnt_11_2,
       case when b.cnt_11_1 = 0 then null else round((b.cnt_11_1 - a.cnt_11_2) * 100.0 / b.cnt_11_1, 2) end,
       '剥除 -、空格等非数字字符，兼容 86 前缀'
  from (select count(*) as cnt_11_1 from ydsh_ods.ods_user
         where phone is null or not (trim(phone) rlike '^[0-9]{11}$')) b
 cross join (select count(*) as cnt_11_2 from ydsh_dwd.dwd_user
         where phone is null or not (phone rlike '^[0-9]{11}$')) a
union all
select '⑤ 格式不规范', '订单时间戳非 yyyy-MM-dd HH:mm:ss',
       b.cnt_12_1, a.cnt_12_2,
       case when b.cnt_12_1 = 0 then null else round((b.cnt_12_1 - a.cnt_12_2) * 100.0 / b.cnt_12_1, 2) end,
       '日期、时间分别归一后 concat 合成，作为分区与时间维度的唯一依据'
  from (select count(*) as cnt_12_1 from ydsh_ods.ods_order
         where order_date is null or order_time is null
            or not (trim(order_date) rlike '^[0-9]{4}-[0-9]{2}-[0-9]{2}$')
            or not (trim(order_time) rlike '^[0-9]{2}:[0-9]{2}:[0-9]{2}$')) b
 cross join (select count(*) as cnt_12_2 from ydsh_dwd.dwd_order_tmp
         where not (order_timestamp rlike '^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}$')) a;


-- ---------------------------------------------------------------------
-- 3. 输出总表（直接作为《数据质量对比报告》第三、四节原始数据）
-- ---------------------------------------------------------------------
select dirty_type, item, before_cnt, after_cnt, fix_rate, note
  from ydsh_dwd.dwd_data_quality_report
 order by dirty_type, item;

-- ---------------------------------------------------------------------
-- 4. 汇总：按五类脏数据聚合，得到"总体修复率"
-- ---------------------------------------------------------------------
select dirty_type,
       sum(before_cnt) as before_total,
       sum(after_cnt)  as after_total,
       round((sum(before_cnt) - sum(after_cnt)) * 100.0 / sum(before_cnt), 2) as fix_rate
  from ydsh_dwd.dwd_data_quality_report
 group by dirty_type
 order by dirty_type
;


