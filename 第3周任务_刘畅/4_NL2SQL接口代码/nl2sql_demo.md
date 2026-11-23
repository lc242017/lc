# NL2SQL 演示记录

生成时间：2026-11-10　|　模式：offline-mock

## 问：广东省上月销售额是多少

**生成 SQL：**

```sql
SELECT round(sum(o.pay_amount),2) AS sales FROM dwd_order o JOIN dim_store s ON o.store_id=s.store_id WHERE o.status='paid' AND s.province='广东省' AND substr(o.order_date,1,7)=substr(date('now','-1 month'),1,7)
```

口径说明：offline-mock 模板生成（未调用真实大模型）

**返回 1 行：**

| sales |
| --- |
| 565109.92 |

## 问：销量前 5 的品类

**生成 SQL：**

```sql
SELECT p.category, count(1) AS order_cnt FROM dwd_order o JOIN dim_product p ON o.product_id=p.product_id WHERE o.status='paid' GROUP BY p.category ORDER BY order_cnt DESC LIMIT 5
```

口径说明：offline-mock 模板生成（未调用真实大模型）

**返回 5 行：**

| category | order_cnt |
| --- | --- |
| 生鲜果蔬 | 32896 |
| 乳品烘焙 | 18572 |
| 休闲零食 | 16196 |
| 粮油调味 | 16122 |
| 酒水饮料 | 13938 |

## 问：最近 7 天每日 GMV

**生成 SQL：**

```sql
SELECT order_date, gmv, orders, aov FROM ads_kpi_day ORDER BY order_date DESC LIMIT 7
```

口径说明：offline-mock 模板生成（未调用真实大模型）

**返回 7 行：**

| order_date | gmv | orders | aov |
| --- | --- | --- | --- |
| 2026-11-09 | 50237.22 | 679 | 73.99 |
| 2026-11-08 | 133535.91 | 1728 | 77.28 |
| 2026-11-07 | 66798.61 | 850 | 78.59 |
| 2026-11-06 | 49443.55 | 656 | 75.37 |
| 2026-11-05 | 50052.98 | 643 | 77.84 |
| 2026-11-04 | 46572.99 | 629 | 74.04 |
| 2026-11-03 | 52431.08 | 668 | 78.49 |

## 问：客单价最高的前 3 个门店

**生成 SQL：**

```sql
SELECT s.store_name, round(sum(o.pay_amount)*1.0/count(distinct o.order_id),2) AS aov FROM dwd_order o JOIN dim_store s ON o.store_id=s.store_id WHERE o.status='paid' GROUP BY s.store_name ORDER BY aov DESC LIMIT 3
```

口径说明：offline-mock 模板生成（未调用真实大模型）

**返回 3 行：**

| store_name | aov |
| --- | --- |
| 无锡市1号店 | 81.39 |
| 佛山市2号店 | 81.25 |
| 无锡市2号店 | 80.76 |

## 问：近半年的月度复购率

**生成 SQL：**

```sql
SELECT month, buyers, repeat_users, repurchase_rate FROM ads_repurchase_month ORDER BY month
```

口径说明：offline-mock 模板生成（未调用真实大模型）

**返回 7 行：**

| month | buyers | repeat_users | repurchase_rate |
| --- | --- | --- | --- |
| 2026-05 | 7451 | 1335 | 0.18 |
| 2026-06 | 11542 | 3166 | 0.27 |
| 2026-07 | 12569 | 3726 | 0.3 |
| 2026-08 | 13306 | 4264 | 0.32 |
| 2026-09 | 13672 | 4277 | 0.31 |
| 2026-10 | 15212 | 5396 | 0.35 |
| 2026-11 | 7181 | 1247 | 0.17 |
