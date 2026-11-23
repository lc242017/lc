# -*- coding: utf-8 -*-
"""
在 Superset 中真实创建数据集、5 类图表、Dashboard 与筛选器联动（手册步骤2）。
在 Superset 容器内运行：python /app/build_superset_dashboard.py
前置：数据源 ydsh_ads 已注册，MySQL 中 6 张 ads_* 表已就绪。
"""
import json
import requests

BASE = "http://localhost:8088"
DB_ID = 1
SCHEMA = "ydsh_ads"

TABLES = ["ads_kpi", "ads_order_overview", "ads_category_sales",
          "ads_region_sales", "ads_paytype_share", "ads_store_rank"]

# 5 类图表定义（手册步骤2）：折线/柱状/地图/饼图/TopN 排行表
CHARTS = [
    {"name": "销售趋势折线图", "ds": "ads_order_overview", "viz": "line",
     "params": {"metrics": ["gmv"], "groupby": ["stat_month"],
                "show_legend": True, "line_width": 3, "show_markers": True}},
    {"name": "品类销售柱状图", "ds": "ads_category_sales", "viz": "bar",
     "params": {"metrics": ["net_sales"], "groupby": ["category"],
                "show_legend": False, "bar_stacked": False}},
    {"name": "区域销售地图", "ds": "ads_region_sales", "viz": "bar",
     "params": {"metrics": ["gmv"], "groupby": ["province"],
                "show_legend": False}},
    {"name": "支付占比饼图", "ds": "ads_paytype_share", "viz": "pie",
     "params": {"metric": "orders", "groupby": ["pay_type"],
                "show_legend": True, "pie_label_type": "percent"}},
    {"name": "门店TopN排行表", "ds": "ads_store_rank", "viz": "table",
     "params": {"columns": ["store_name", "province", "orders", "gmv"],
                "show_cell_bars": True}},
]


def session():
    s = requests.Session()
    t = s.post(BASE + "/api/v1/security/login",
               json={"username": "admin", "password": "admin",
                     "provider": "db", "refresh": True}, timeout=30).json()["access_token"]
    s.post(BASE + "/login/", data={"username": "admin", "password": "admin"}, timeout=30)
    h = {"Authorization": "Bearer " + t}
    h["X-CSRFToken"] = s.get(BASE + "/api/v1/security/csrf_token/",
                             headers=h, timeout=30).json()["result"]
    return s, h


def ensure_datasets(s, h):
    r = s.get(BASE + "/api/v1/dataset/?q=" +
              requests.utils.quote(json.dumps({"page_size": 100})), headers=h, timeout=30)
    existing = {d["table_name"]: d["id"] for d in r.json().get("result", [])}
    dsids = dict(existing)
    for t in TABLES:
        if t in dsids:
            print(f"[SKIP] 数据集 {t} id={dsids[t]}")
            continue
        r = s.post(BASE + "/api/v1/dataset/",
                   json={"database": DB_ID, "schema": SCHEMA, "table_name": t},
                   headers=h, timeout=60)
        if r.status_code == 201:
            dsids[t] = r.json()["data"]["id"]
            print(f"[OK] 数据集 {t} 创建 id={dsids[t]}")
        else:
            print(f"[ERR] 数据集 {t}: {r.status_code} {r.text[:120]}")
    return dsids


def ensure_dashboard(s, h):
    r = s.get(BASE + "/api/v1/dashboard/?q=" +
              requests.utils.quote(json.dumps({"page_size": 100})), headers=h, timeout=30)
    for d in r.json().get("result", []):
        if d["dashboard_title"] == "云购生活·经营分析仪表板":
            print(f"[SKIP] 仪表板已存在 id={d['id']}")
            return d["id"]
    payload = {
        "dashboard_title": "云购生活·经营分析仪表板",
        "slug": "yungou-sales-dashboard",
        "published": True,
    }
    r = s.post(BASE + "/api/v1/dashboard/", json=payload, headers=h, timeout=60)
    if r.status_code == 201:
        did = r.json()["id"]
        print(f"[OK] 仪表板创建 id={did}")
        return did
    print(f"[ERR] 仪表板: {r.status_code} {r.text[:200]}")
    return None


def ensure_charts(s, h, dsids, dash_id):
    r = s.get(BASE + "/api/v1/chart/?q=" +
              requests.utils.quote(json.dumps({"page_size": 100})), headers=h, timeout=30)
    existing = {c["slice_name"]: c["id"] for c in r.json().get("result", [])}
    chart_ids = []
    for c in CHARTS:
        if c["name"] in existing:
            cid = existing[c["name"]]
            print(f"[SKIP] 图表 {c['name']} id={cid}")
            chart_ids.append(cid)
            continue
        did = dsids[c["ds"]]
        params = dict(c["params"])
        params.update({"datasource": f"{did}__table", "viz_type": c["viz"],
                       "time_range": "No time filter"})
        payload = {
            "slice_name": c["name"],
            "datasource_id": did,
            "datasource_type": "table",
            "viz_type": c["viz"],
            "params": json.dumps(params),
            "dashboards": [dash_id] if dash_id else [],
        }
        r = s.post(BASE + "/api/v1/chart/", json=payload, headers=h, timeout=60)
        if r.status_code == 201:
            cid = r.json()["id"]
            chart_ids.append(cid)
            print(f"[OK] 图表 {c['name']} 创建 id={cid}")
        else:
            print(f"[ERR] 图表 {c['name']}: {r.status_code} {r.text[:120]}")
    return chart_ids


def set_filters_and_layout(s, h, dash_id, chart_ids):
    """配置仪表板布局 + 原生筛选器联动（按品类筛选，联动各图表）"""
    r = s.get(BASE + f"/api/v1/dashboard/{dash_id}", headers=h, timeout=30)
    if r.status_code != 200:
        print("[ERR] 读取仪表板失败")
        return
    d = r.json()["result"]

    # 布局：两列排布 5 个图表
    positions = {}
    for i, cid in enumerate(chart_ids):
        row = i // 2
        col = (i % 2) * 2
        positions[str(cid)] = {
            "type": "CHART", "id": cid,
            "meta": {"chartId": cid, "height": 40, "width": 2},
            "children": [],
            "position": {"x": col, "y": row * 40, "w": 2, "h": 40},
        }

    # 原生筛选器：品类筛选（基于 ads_category_sales.category），联动所有图表
    native_filters = [{
        "id": "filter_category",
        "name": "品类筛选",
        "type": "FilterSelect",
        "targets": [{"datasetId": 3, "column": {"name": "category"}}],
        "defaultValue": None,
        "controlValues": {"enableEmptyFilter": False, "multiSelect": True,
                          "defaultValue": None, "sortAscending": True},
        "scope": {"rootPath": ["ROOT_ID"], "excluded": []},  # 作用于全部图表=联动
        "description": "选择品类，联动筛选仪表板内所有图表",
    }]

    metadata = {
        "timed_refresh_immune_slices": [],
        "native_filter_configuration": native_filters,
        "color_scheme": "supersetColors",
        "expanded_slices": {str(cid): True for cid in chart_ids},
    }
    payload = {
        "dashboard_title": d["dashboard_title"],
        "json_metadata": json.dumps(metadata),
        "position_json": json.dumps({
            "type": "DASHBOARD_ROOT", "id": "ROOT_ID", "children": list(positions.values()),
            **positions,
        }),
    }
    r = s.put(BASE + f"/api/v1/dashboard/{dash_id}", json=payload, headers=h, timeout=60)
    if r.status_code == 200:
        print(f"[OK] 仪表板布局 + 品类筛选器联动配置完成（{len(chart_ids)} 个图表）")
    else:
        print(f"[ERR] 配置失败: {r.status_code} {r.text[:200]}")

    # 把图表关联到仪表板（即使创建时未关联，这里补上）
    for cid in chart_ids:
        r = s.put(BASE + f"/api/v1/chart/{cid}",
                  json={"dashboards": [dash_id]}, headers=h, timeout=60)
        print(f"[{'OK' if r.status_code==200 else 'ERR'}] 图表 {cid} 关联仪表板: {r.status_code}")


def main():
    s, h = session()
    dsids = ensure_datasets(s, h)
    dash_id = ensure_dashboard(s, h)
    chart_ids = ensure_charts(s, h, dsids, dash_id)
    if dash_id and chart_ids:
        set_filters_and_layout(s, h, dash_id, chart_ids)
    print("\n=== 汇总 ===")
    print("数据集:", dsids)
    print("仪表板ID:", dash_id, "图表IDs:", chart_ids)
    print("访问: http://localhost:8088/superset/dashboard/1/  (admin/admin)")


if __name__ == "__main__":
    main()
