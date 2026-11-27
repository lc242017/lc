import sqlite3, json

DB = "/app/superset_home/superset.db"
charts = [
    (1, "销售趋势折线图", "CHART-trend"),
    (2, "品类销售柱状图", "CHART-category"),
    (3, "区域销售地图", "CHART-region"),
    (4, "支付占比饼图", "CHART-pay"),
    (5, "门店TopN排行表", "CHART-store"),
]

layout = {
    "DASHBOARD_VERSION_KEY": "v2",
    "ROOT_ID": {"children": ["GRID_ID"], "id": "ROOT_ID", "type": "ROOT"},
    "GRID_ID": {"children": ["ROW-1", "ROW-2"], "id": "GRID_ID",
                "parents": ["ROOT_ID"], "type": "GRID"},
    "ROW-1": {"children": ["CHART-trend", "CHART-category", "CHART-region"],
              "id": "ROW-1", "meta": {"background": "BACKGROUND_TRANSPARENT"},
              "parents": ["ROOT_ID", "GRID_ID"], "type": "ROW"},
    "ROW-2": {"children": ["CHART-pay", "CHART-store"],
              "id": "ROW-2", "meta": {"background": "BACKGROUND_TRANSPARENT"},
              "parents": ["ROOT_ID", "GRID_ID"], "type": "ROW"},
}
for chart_id, name, cid in charts:
    row = "ROW-1" if cid in ("CHART-trend", "CHART-category", "CHART-region") else "ROW-2"
    width = 4 if row == "ROW-1" else 6
    layout[cid] = {
        "children": [], "id": cid,
        "meta": {"chartId": chart_id, "height": 40, "sliceName": name, "width": width},
        "parents": ["ROOT_ID", "GRID_ID", row], "type": "CHART",
    }

c = sqlite3.connect(DB)
c.execute("update dashboards set position_json=? where id=1",
          (json.dumps(layout, ensure_ascii=False),))
c.commit()
print("LAYOUT UPDATED, keys:", list(layout.keys()))
