-- ============================================
-- ODS 数据导入脚本
-- 前提：CSV 已位于 Hive 所在容器/机器的 /data/ 目录
-- ============================================

load data local inpath '/data/ods_user.csv' into table ydsh_ods.ods_user;
load data local inpath '/data/ods_product.csv' into table ydsh_ods.ods_product;
load data local inpath '/data/ods_store.csv' into table ydsh_ods.ods_store;
load data local inpath '/data/ods_order.csv' into table ydsh_ods.ods_order;
load data local inpath '/data/ods_order_item.csv' into table ydsh_ods.ods_order_item;
load data local inpath '/data/ods_user_behavior.csv' into table ydsh_ods.ods_user_behavior;

-- 行数校验
select 'ods_user' t, count(*) c from ydsh_ods.ods_user
union all select 'ods_product', count(*) from ydsh_ods.ods_product
union all select 'ods_store', count(*) from ydsh_ods.ods_store
union all select 'ods_order', count(*) from ydsh_ods.ods_order
union all select 'ods_order_item', count(*) from ydsh_ods.ods_order_item
union all select 'ods_user_behavior', count(*) from ydsh_ods.ods_user_behavior;
