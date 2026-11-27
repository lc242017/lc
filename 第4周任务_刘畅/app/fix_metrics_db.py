# -*- coding: utf-8 -*-
"""直接向 Superset 元数据库补 SUM 指标（图表 params 字符串引用所需）。"""
import sqlite3
from datetime import datetime

DB = "/app/superset_home/superset.db"
METRICS = {
    2: ["gmv"],                 # ads_order_overview
    3: ["net_sales"],           # ads_category_sales
    4: ["gmv"],                 # ads_region_sales
    5: ["orders"],              # ads_paytype_share
    6: ["gmv"],                 # ads_store_rank
}
c = sqlite3.connect(DB)
now = datetime.utcnow().isoformat(sep=" ", timespec="microseconds")
for table_id, names in METRICS.items():
    for name in names:
        exists = c.execute(
            "select 1 from sql_metrics where table_id=? and metric_name=?",
            (table_id, name)).fetchone()
        if exists:
            print(f"[SKIP] table {table_id} {name}")
            continue
        c.execute(
            "insert into sql_metrics (created_on,changed_on,metric_name,verbose_name,"
            "metric_type,table_id,expression,description,d3format,warning_text,extra,currency) "
            "values (?,?,?,?,?,?,?,?,?,?,?,?)",
            (now, now, name, name, "sum", table_id, f"SUM({name})", None, None, None, None, None))
        print(f"[ADD] table {table_id} {name} = SUM({name})")
c.commit()
c.close()
print("DONE")
