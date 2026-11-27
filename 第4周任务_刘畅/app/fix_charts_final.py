import sqlite3, json

DB = "/app/superset_home/superset.db"
c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row

# 1) 筛选器类型修正：value -> filter_select
d = c.execute("select json_metadata from dashboards where id=1").fetchone()
meta = json.loads(d["json_metadata"] or "{}")
for f in meta.get("native_filter_configuration", []):
    if f.get("filterType") in ("value", None):
        f["filterType"] = "filter_select"
c.execute("update dashboards set json_metadata=? where id=1",
          (json.dumps(meta, ensure_ascii=False),))
print("FILTER type ->", [f.get("filterType") for f in meta.get("native_filter_configuration", [])])

# 2) 数据集2的 stat_month 标记为时间列（折线图需要）
c.execute("update table_columns set is_dttm=1 where table_id=2 and column_name='stat_month'")
print("DTTM marked: stat_month")

# 3) 修正图表参数
for r in c.execute("select id, params from slices"):
    sid = r["id"]
    p = json.loads(r["params"])
    if sid == 1:
        p["granularity_sqla"] = "stat_month"
        p["time_grain_sqla"] = None
    if sid in (2, 3):
        # 分类柱状图用非时间序列的 dist_bar
        p["viz_type"] = "dist_bar"
    if sid == 4:
        # 饼图明确关闭时间序列
        p["time_range"] = "No time range"
    c.execute("update slices set params=?, query_context=NULL where id=?",
              (json.dumps(p, ensure_ascii=False), sid))
    print("SLICE", sid, "viz", p.get("viz_type"), "gran", p.get("granularity_sqla"))

c.commit()
print("DONE")
