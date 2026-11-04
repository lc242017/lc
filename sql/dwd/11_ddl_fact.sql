-- =====================================================================
-- 11_ddl_fact.sql   事实表 DDL（对应手册「步骤 6」事实表部分）
-- ---------------------------------------------------------------------
-- 三张事实表：
--   dwd_order          订单事实表（主体）—— 按 stat_date 分区、按 user_id 分桶
--   dwd_order_item     订单明细事实表 —— 品类/商品分析的唯一正确入口
--   dwd_user_behavior  用户行为事实表 —— 行为漏斗分析
--
-- 【为什么事实表必须分区 + 分桶】
--   分区：订单表随日期线性增长，ADS 层 90% 查询都带时间范围，按天分区后
--         分区裁剪直接把扫描量从全表降到 1 天（手册 1.3「分区查询慢」）。
--   分桶：按 user_id 分 8 桶，用户维度关联时同桶必然同机，避免全表 shuffle；
--         同时支持 TABLESAMPLE(BUCKET x OUT OF 8) 快速抽样。
--
-- 【与手册的重要差异】
--   手册步骤 8 写的是 `dwd_order o join dim_product p on o.product_id = p.product_id`，
--   但手册自己给出的 dwd_order 建表语句里根本没有 product_id 字段 —— 订单粒度
--   （一行一单）与商品粒度（一行一单品）不是一个粒度，强行加字段会造成订单行
--   膨胀、GMV 重复计算。正确做法是新增 dwd_order_item 明细事实表承载商品粒度，
--   品类分析走 dwd_order_item join dim_product。详见架构文档第 8 节。
-- =====================================================================

use ydsh_dwd;


-- ---------------------------------------------------------------------
-- 1. 订单事实表（分区 + 分桶）
-- ---------------------------------------------------------------------
drop table if exists ydsh_dwd.dwd_order;
create table ydsh_dwd.dwd_order (
    order_id        string  comment '订单号',
    user_id         string  comment '用户 ID（外键 → dim_user.user_id）',
    store_id        string  comment '门店 ID（外键 → dim_store.store_id）',
    order_timestamp string  comment '下单时间 yyyy-MM-dd HH:mm:ss',
    stat_year       string  comment '年（冗余，便于年度聚合）',
    stat_month      string  comment '年月（冗余，便于月度聚合）',
    stat_hour       string  comment '下单小时，用于分时段分析',
    pay_amount      double  comment '实付金额（度量，已做异常值缩尾）',
    discount_amount double  comment '优惠金额（度量）',
    total_amount    double  comment '应收总额 = 实付 + 优惠（度量）',
    pay_type        string  comment '支付方式',
    order_status    string  comment '订单状态',
    channel         string  comment '下单渠道',
    is_amount_fixed int     comment '1=金额经过异常值处理'
)
partitioned by (stat_date string comment '下单日期 yyyy-MM-dd，分区字段')
clustered by (user_id) into 8 buckets
stored as orc
tblproperties ('orc.compress' = 'SNAPPY');


-- ---------------------------------------------------------------------
-- 2. 订单明细事实表（商品粒度，分区）
-- ---------------------------------------------------------------------
drop table if exists ydsh_dwd.dwd_order_item;
create table ydsh_dwd.dwd_order_item (
    item_id      string  comment '明细行号',
    order_id     string  comment '订单号（外键 → dwd_order.order_id）',
    user_id      string  comment '用户 ID（冗余，避免明细表再回关订单表）',
    product_id   string  comment '商品 ID（外键 → dim_product.product_id）',
    quantity     int     comment '购买数量（度量）',
    price        double  comment '成交单价（度量）',
    discount     double  comment '行级优惠（度量）',
    item_amount  double  comment '行成交额 = 单价 × 数量 - 行优惠（度量）'
)
partitioned by (stat_date string comment '所属订单的下单日期')
stored as orc
tblproperties ('orc.compress' = 'SNAPPY');


-- ---------------------------------------------------------------------
-- 3. 用户行为事实表（分区）
-- ---------------------------------------------------------------------
drop table if exists ydsh_dwd.dwd_user_behavior;
create table ydsh_dwd.dwd_user_behavior (
    behavior_id   string  comment '行为 ID',
    user_id       string  comment '用户 ID',
    product_id    string  comment '商品 ID',
    behavior_type string  comment '行为类型：浏览/加购/收藏/购买',
    behavior_time string  comment '行为时间 yyyy-MM-dd HH:mm:ss'
)
partitioned by (stat_date string comment '行为日期 yyyy-MM-dd')
stored as orc
tblproperties ('orc.compress' = 'SNAPPY');
