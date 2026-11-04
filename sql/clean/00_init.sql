-- =====================================================================
-- 00_init.sql  第 2 周清洗与建模：库、参数、会话初始化
-- 项目：云购生活新零售企业 · 企业级数据仓库与经营分析可视化系统
-- 环境：Hive 4.0.0（Tez 引擎） + Derby Metastore（容器内置），Docker 部署
-- 执行方式：beeline -u jdbc:hive2://localhost:10000 -f 00_init.sql
-- ---------------------------------------------------------------------
-- 前置依赖：第 1 周已完成 ydsh_ods 库 6 张外部表建表与数据导入
--           （ods_user 1000 / ods_product 600 / ods_store 60
--             ods_order 15600 / ods_order_item 37549 / ods_user_behavior 60000）
-- =====================================================================

-- 1. 建 DWD 库（第 2 周所有产出落在 ydsh_dwd）
create database if not exists ydsh_dwd
comment '云购生活数仓 DWD 明细层，第 2 周清洗与建模产出';

-- 2. 会话级参数（每个 beeline 会话都要重设，脚本内自带一份，保证可独立执行）
set hive.exec.dynamic.partition = true;
set hive.exec.dynamic.partition.mode = nonstrict;
set hive.exec.max.dynamic.partitions = 10000;
set hive.exec.max.dynamic.partitions.pernode = 1000;
set hive.auto.convert.join = true;
set hive.mapjoin.smalltable.filesize = 25000000;
set hive.exec.compress.output = true;
set mapreduce.output.fileoutputformat.compress.codec = org.apache.hadoop.io.compress.SnappyCodec;

-- 3. 确认 ODS 层就绪（行数应与第 1 周记录一致，不一致就不要往下跑）
select 'ods_user'          as tbl, count(*) as cnt from ydsh_ods.ods_user
union all select 'ods_product',        count(*) from ydsh_ods.ods_product
union all select 'ods_store',          count(*) from ydsh_ods.ods_store
union all select 'ods_order',          count(*) from ydsh_ods.ods_order
union all select 'ods_order_item',     count(*) from ydsh_ods.ods_order_item
union all select 'ods_user_behavior',  count(*) from ydsh_ods.ods_user_behavior;
