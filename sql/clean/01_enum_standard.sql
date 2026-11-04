-- =====================================================================
-- 01_enum_standard.sql   枚举字段标准化（对应手册「步骤 1」）
-- ---------------------------------------------------------------------
-- 输入：ydsh_ods.ods_user / ods_order / ods_product / ods_user_behavior
-- 输出：4 个标准化视图（不落盘）
--       ydsh_dwd.v_user_enum / v_order_enum / v_product_enum / v_behavior_enum
--
-- 【设计说明：为什么用视图而不是临时表】
--   Hive 不支持 UPDATE，多步清洗每落一次表就多一份全量副本。本周清洗共 3 步，
--   若逐步落表将产生 4 倍冗余存储；改用视图串联，最终在 03 脚本 CTAS 时一次性
--   物化，逻辑完全等价，存储开销为零。手册步骤里的 dwd_order_tmp 属于"必须
--   物化才能接下一步"的场景，保留为实表。
--
-- 【映射原则】
--   1) 先 select distinct 看清全部脏取值，再写 case when，避免漏分支（手册 1.3）
--   2) 一律用 lower(trim(x)) 做归一，兼容大小写/前后空格
--   3) else 分支统一兜到「其他 / 未知」，保证 distinct 收敛且不丢行
--   4) 规范值域统一为中文（手册 1.1 明确要求）
-- =====================================================================

use ydsh_dwd;

-- ---------------------------------------------------------------------
-- 0. 清洗前取值分布基线（先看清数据，再写映射）
--    这一步的产出请截图存档，作为《数据质量对比报告》的"清洗前"证据
-- ---------------------------------------------------------------------
select 'ods_user.gender' as col_name, nvl(gender, '<NULL>') as col_value, count(*) as cnt
  from ydsh_ods.ods_user group by gender
union all
select 'ods_user.member_level', nvl(member_level, '<NULL>'), count(*)
  from ydsh_ods.ods_user group by member_level
union all
select 'ods_order.pay_type', nvl(pay_type, '<NULL>'), count(*)
  from ydsh_ods.ods_order group by pay_type
union all
select 'ods_order.order_status', nvl(order_status, '<NULL>'), count(*)
  from ydsh_ods.ods_order group by order_status
union all
select 'ods_order.channel', nvl(channel, '<NULL>'), count(*)
  from ydsh_ods.ods_order group by channel
union all
select 'ods_product.status', nvl(status, '<NULL>'), count(*)
  from ydsh_ods.ods_product group by status
union all
select 'ods_user_behavior.behavior_type', nvl(behavior_type, '<NULL>'), count(*)
  from ydsh_ods.ods_user_behavior group by behavior_type
order by col_name, cnt desc;


-- ---------------------------------------------------------------------
-- 1. 用户维度枚举：gender（男 / 女 / 未知）、member_level（钻石/金卡/银卡/普通）
-- ---------------------------------------------------------------------
create or replace view ydsh_dwd.v_user_enum as
select
    user_id,
    trim(user_name) as user_name,

    -- gender：中英文 + 大小写 + 单字母缩写全覆盖；空值兜到「未知」
    case
        when lower(trim(gender)) in ('m', 'male', 'man', '1') or trim(gender) = '男' then '男'
        when lower(trim(gender)) in ('f', 'female', 'woman', '0') or trim(gender) = '女' then '女'
        else '未知'
    end as gender,

    age,

    -- member_level：业务方同时存在「金卡」「金卡会员」「gold」三种写法
    case
        when lower(trim(member_level)) in ('gold', 'gold_card')  or trim(member_level) in ('金卡', '金卡会员')   then '金卡会员'
        when lower(trim(member_level)) in ('silver', 'silver_card') or trim(member_level) in ('银卡', '银卡会员') then '银卡会员'
        when lower(trim(member_level)) in ('diamond', 'diamond_card') or trim(member_level) in ('钻石', '钻石会员') then '钻石会员'
        else '普通会员'
    end as member_level,

    phone,
    email,
    city,
    province,
    register_date
from ydsh_ods.ods_user;


-- ---------------------------------------------------------------------
-- 2. 订单枚举：pay_type（4 值）、order_status（5 值）、channel（4 值）
--    注意：第 1 周预评估显示 order_status 同时存在数字代码（1~5）与中英文，
--          映射时必须把数字代码一并归位，否则 distinct 无法收敛。
-- ---------------------------------------------------------------------
create or replace view ydsh_dwd.v_order_enum as
select
    order_id,
    user_id,
    store_id,
    order_date,
    order_time,

    case
        when lower(trim(pay_type)) in ('alipay', 'ali', 'ali_pay') or trim(pay_type) = '支付宝'   then '支付宝'
        when lower(trim(pay_type)) in ('wechat', 'weixin', 'wx', 'wechat_pay') or trim(pay_type) in ('微信支付', '微信') then '微信支付'
        when lower(trim(pay_type)) in ('bank', 'bankcard', 'bank_card', 'unionpay') or trim(pay_type) in ('银行卡', '银联') then '银行卡'
        when lower(trim(pay_type)) in ('cod', 'cash_on_delivery') or trim(pay_type) = '货到付款'   then '货到付款'
        else '其他'
    end as pay_type,

    -- order_status：中文同义词 + 英文 + 数字代码三路归一
    case
        when lower(trim(order_status)) in ('pending', 'unpaid', 'wait_pay') or trim(order_status) in ('待支付', '待付款') or trim(order_status) = '1' then '待支付'
        when lower(trim(order_status)) in ('paid', 'payed')                or trim(order_status) in ('已支付', '已付款') or trim(order_status) = '2' then '已支付'
        when lower(trim(order_status)) in ('completed', 'finished', 'done') or trim(order_status) in ('已完成', '完成')   or trim(order_status) = '3' then '已完成'
        when lower(trim(order_status)) in ('cancelled', 'canceled')         or trim(order_status) = '已取消'             or trim(order_status) = '4' then '已取消'
        when lower(trim(order_status)) in ('refunding', 'refund')           or trim(order_status) = '退款中'             or trim(order_status) = '5' then '退款中'
        else '其他'
    end as order_status,

    case
        when lower(trim(channel)) in ('app', 'android', 'ios') then 'APP'
        when lower(trim(channel)) in ('pc', 'web', 'pcguanwang') or trim(channel) in ('PC官网', '官网') then 'PC官网'
        when lower(trim(channel)) in ('miniapp', 'mini_app', 'mini_program', 'wxapp') or trim(channel) = '小程序' then '小程序'
        when lower(trim(channel)) in ('store', 'offline', 'shop')      or trim(channel) in ('门店', '线下门店') then '门店'
        else '其他'
    end as channel,

    pay_amount,
    discount_amount
from ydsh_ods.ods_order;


-- ---------------------------------------------------------------------
-- 3. 商品枚举：status（在售 / 下架 / 缺货）
--    第 1 周预评估该项三值已规范（在售 510 / 下架 53 / 缺货 37），
--    此处仍保留完整映射，防止后续增量数据再次引入脏值。
-- ---------------------------------------------------------------------
create or replace view ydsh_dwd.v_product_enum as
select
    product_id,
    trim(product_name) as product_name,
    trim(category)     as category,
    trim(sub_category) as sub_category,
    trim(brand)        as brand,
    price,
    launch_date,
    case
        when lower(trim(status)) in ('on_sale', 'onsale', '1') or trim(status) = '在售' then '在售'
        when lower(trim(status)) in ('off_shelf', 'offsale', 'off_sale', '0') or trim(status) = '下架' then '下架'
        when lower(trim(status)) in ('out_of_stock', 'oos', 'sold_out')       or trim(status) = '缺货' then '缺货'
        else '其他'
    end as status
from ydsh_ods.ods_product;


-- ---------------------------------------------------------------------
-- 4. 行为枚举：behavior_type（浏览 / 加购 / 收藏 / 购买）
--    第 1 周预评估：pv 32945 / PV 604 / 浏览 611，合计 60000 行，
--    脏值占 3672 行（约 6.1%），是本表最大的质量问题。
-- ---------------------------------------------------------------------
create or replace view ydsh_dwd.v_behavior_enum as
select
    behavior_id,
    user_id,
    product_id,
    case
        when lower(trim(behavior_type)) in ('pv', 'view', 'browse', 'page_view') or trim(behavior_type) = '浏览' then '浏览'
        when lower(trim(behavior_type)) in ('cart', 'add_cart', 'addcart') or trim(behavior_type) = '加购' then '加购'
        when lower(trim(behavior_type)) in ('fav', 'favorite', 'collect') or trim(behavior_type) = '收藏' then '收藏'
        when lower(trim(behavior_type)) in ('buy', 'purchase', 'order_paid') or trim(behavior_type) = '购买' then '购买'
        else '其他'
    end as behavior_type,
    behavior_time
from ydsh_ods.ods_user_behavior;


-- ---------------------------------------------------------------------
-- 5. 验收：每个枚举字段的 distinct 必须收敛到 2~4 个规范值
--    出现「其他 / 未知」以外的越界值 → 说明映射漏分支，回到第 0 步补
-- ---------------------------------------------------------------------
select 'v_user_enum.gender'       as field, gender          as val, count(*) as cnt from ydsh_dwd.v_user_enum       group by gender
union all
select 'v_user_enum.member_level', member_level, count(*) from ydsh_dwd.v_user_enum       group by member_level
union all
select 'v_order_enum.pay_type',    pay_type,     count(*) from ydsh_dwd.v_order_enum      group by pay_type
union all
select 'v_order_enum.order_status',order_status, count(*) from ydsh_dwd.v_order_enum      group by order_status
union all
select 'v_order_enum.channel',     channel,      count(*) from ydsh_dwd.v_order_enum      group by channel
union all
select 'v_product_enum.status',    status,       count(*) from ydsh_dwd.v_product_enum    group by status
union all
select 'v_behavior_enum.type',     behavior_type,count(*) from ydsh_dwd.v_behavior_enum   group by behavior_type
order by field, cnt desc;
