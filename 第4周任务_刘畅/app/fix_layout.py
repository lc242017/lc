# -*- coding: utf-8 -*-
"""重建 Superset 4.x 合法的仪表板 position_json。
标准结构：DASHBOARD_VERSION_KEY=v2 -> ROOT_ID -> GRID_ID -> CHART 组件。
"""
import json
import sqlite3

DB = "/app/superset_home/superset.db"
CHART_IDS = [1, 2, 3, 4, 5]

position = {
    "DASHBOARD_VERSION_KEY": "v2",
    "ROOT_ID": {
        "type": "ROOT",
        "id": "ROOT_ID",
        "children": ["GRID_ID"],
        "root": True,
    },
    "GRID_ID": {
        "type": "GRID",
        "id": "GRID_ID",
        "children": [],
    },
}

for cid in CHART_IDS:
    key = f"CHART-{cid}"
    position["GRID_ID"]["children"].append(key)
    position[key] = {
        "type": "CHART",
        "id": key,
        "children": [],
        "meta": {
            "chartId": cid,
            "width": 6,
            "height": 40,
        },
    }

c = sqlite3.connect(DB)
c.execute("update dashboards set position_json=? where id=1",
          (json.dumps(position, ensure_ascii=False),))
c.commit()
c.close()
print("position_json 已重建（v2 标准结构）")
print(json.dumps(position, ensure_ascii=False, indent=2))
