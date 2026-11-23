-- =====================================================================
-- 01_dwd_ddl.sql  DWD 明细层建表（Hive / 数仓侧正式口径）
-- 说明：本地教学环境用 SQLite 同构表顶替（见 sql/local/），字段与类型保持一致。
-- =====================================================================
create database if not exists dwd  comment '明细数据层';
create database if not exists dws  comment '汇总数据层';
create database if not exists ads  comment '应用数据层';

-- 订单事实表：一行一个订单（当前粒度为一单一品，后续可拆 dwd_order_item）
create table if not exists dwd.dwd_order (
    order_id     string comment '订单号',
    user_id      string comment '用户ID',
    store_id     string comment '门店ID',
    product_id   string comment '商品ID',
    order_date   string comment '下单日期 yyyy-MM-dd',
    order_ts     string comment '下单时间 yyyy-MM-dd HH:mm:ss',
    quantity     int    comment '购买件数',
    pay_amount   double comment '实付金额（元）',
    status       string comment '订单状态 paid/refunded/closed'
)
comment '订单明细事实表'
partitioned by (dt string comment '分区日期=order_date')
stored as parquet
tblproperties ('parquet.compression' = 'snappy');

-- 商品维度
create table if not exists dwd.dim_product (
    product_id   string comment '商品ID',
    product_name string comment '商品名称',
    category     string comment '一级品类',
    brand        string comment '品牌',
    price        double comment '标准售价（元）'
)
comment '商品维度表'
stored as parquet;

-- 门店维度
create table if not exists dwd.dim_store (
    store_id   string comment '门店ID',
    store_name string comment '门店名称',
    province   string comment '省份',
    city       string comment '城市',
    channel    string comment '渠道 线上/线下',
    open_date  string comment '开店日期'
)
comment '门店维度表'
stored as parquet;

-- 用户维度
create table if not exists dwd.dim_user (
    user_id       string comment '用户ID',
    register_date string comment '注册日期',
    province      string comment '注册省份',
    member_level  string comment '会员等级'
)
comment '用户维度表'
stored as parquet;
