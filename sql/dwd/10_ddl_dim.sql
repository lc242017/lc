-- =====================================================================
-- 10_ddl_dim.sql   维度表 DDL（对应手册「步骤 6」维度部分）
-- ---------------------------------------------------------------------
-- 维度建模采用星型模型：1 张订单事实表 + 4 张维度表
--   dim_user / dim_product / dim_store / dim_date
--
-- 【设计说明】
--   ① 每张维度表都加代理键 xxx_sk：业务主键（user_id 等）在源系统可能变更，
--      事实表只存代理键，维度属性变化不影响事实表。
--   ② 统一加 etl_time，便于回溯"这一行是哪次跑批写进来的"。
--   ③ dim_date 由脚本生成（2024-01-01 ~ 2026-12-31），不依赖业务系统，
--      日期维度的节假日/周末标记是 ADS 层做同比环比的基础。
-- =====================================================================

use ydsh_dwd;


-- ---------------------------------------------------------------------
-- 1. 用户维度
-- ---------------------------------------------------------------------
drop table if exists ydsh_dwd.dim_user;
create table ydsh_dwd.dim_user (
    user_sk         int     comment '代理键',
    user_id         string  comment '业务主键',
    user_name       string  comment '用户名',
    gender          string  comment '性别：男/女/未知',
    age             int     comment '年龄（已填充异常值）',
    age_group       string  comment '年龄段分箱',
    member_level    string  comment '会员等级：钻石/金卡/银卡/普通',
    city            string  comment '城市',
    province        string  comment '省份',
    register_date   string  comment '注册日期 yyyy-MM-dd',
    is_email_missing int    comment '1=邮箱缺失（已标记未填充）',
    etl_time        string  comment 'ETL 写入时间'
)
stored as orc
tblproperties ('orc.compress' = 'SNAPPY');


-- ---------------------------------------------------------------------
-- 2. 商品维度
-- ---------------------------------------------------------------------
drop table if exists ydsh_dwd.dim_product;
create table ydsh_dwd.dim_product (
    product_sk      int     comment '代理键',
    product_id      string  comment '业务主键',
    product_name    string  comment '商品名称',
    category        string  comment '一级品类',
    sub_category    string  comment '二级品类',
    brand           string  comment '品牌',
    price           double  comment '标价',
    price_band      string  comment '价格带分箱',
    status          string  comment '状态：在售/下架/缺货',
    launch_date     string  comment '上架日期（缺失已按品类众数补全）',
    is_launch_date_fixed int comment '1=上架日期为补全值',
    etl_time        string  comment 'ETL 写入时间'
)
stored as orc
tblproperties ('orc.compress' = 'SNAPPY');


-- ---------------------------------------------------------------------
-- 3. 门店维度
-- ---------------------------------------------------------------------
drop table if exists ydsh_dwd.dim_store;
create table ydsh_dwd.dim_store (
    store_sk        int     comment '代理键',
    store_id        string  comment '业务主键',
    store_name      string  comment '门店名称',
    city            string  comment '城市',
    province        string  comment '省份',
    open_date       string  comment '开业日期 yyyy-MM-dd',
    etl_time        string  comment 'ETL 写入时间'
)
stored as orc
tblproperties ('orc.compress' = 'SNAPPY');


-- ---------------------------------------------------------------------
-- 4. 日期维度（无业务源表，由序列生成）
-- ---------------------------------------------------------------------
drop table if exists ydsh_dwd.dim_date;
create table ydsh_dwd.dim_date (
    date_id         string  comment '日期主键 yyyy-MM-dd',
    date_sk         int     comment '日期代理键 yyyyMMdd',
    year            int     comment '年',
    quarter         int     comment '季度 1~4',
    month           int     comment '月 1~12',
    day             int     comment '日',
    week_of_year    int     comment '年内第几周',
    day_of_week     int     comment '星期几（1=周日 … 7=周六）',
    day_name        string  comment '星期中文名',
    is_weekend      int     comment '1=周末',
    year_month      string  comment '年月 yyyy-MM',
    year_quarter    string  comment '年季度 yyyy-Qn'
)
stored as orc
tblproperties ('orc.compress' = 'SNAPPY');
