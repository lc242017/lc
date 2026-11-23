-- ============================================
-- 第4周 步骤6：查询优化示例
-- 对比：全表扫描 vs 分区裁剪；ORC 列存优势；大 key 加盐
-- ============================================

-- 【优化前】全表扫描（无分区条件）—— 手册指出会导致查询慢
-- select sum(pay_amount) from ydsh_dwd.dwd_order;

-- 【优化后】带分区裁剪条件，只扫描 11 月分区
SELECT round(sum(pay_amount), 2) AS gmv_nov
FROM ydsh_dwd.dwd_order
WHERE stat_date BETWEEN '2024-11-01' AND '2024-11-30';

-- 分区裁剪 + 列裁剪（只取需要的列，ORC 列存优势）
SELECT stat_month, sum(pay_amount) AS gmv
FROM ydsh_dwd.dwd_order
WHERE stat_date >= '2024-01-01' AND stat_date <= '2024-06-30'
GROUP BY stat_month;

-- 【数据倾斜处理】高基数 key 加盐打散（手册应对策略：大 key 加盐）
-- 场景：按门店统计时个别门店数据量过大，用盐值打散两阶段聚合
WITH salted AS (
  SELECT store_id,
         concat(store_id, '_', cast(floor(rand() * 10) AS int)) AS salted_key,
         pay_amount
  FROM ydsh_dwd.dwd_order
  WHERE stat_date >= '2024-01-01'
),
stage1 AS (
  SELECT salted_key, sum(pay_amount) AS partial_gmv FROM salted GROUP BY salted_key
)
SELECT split(salted_key, '_')[0] AS store_id,
       round(sum(partial_gmv), 2) AS gmv
FROM stage1
GROUP BY split(salted_key, '_')[0]
ORDER BY gmv DESC
LIMIT 10;
