# -*- coding: utf-8 -*-
"""
修复 Superset 图表加载失败：
根因：图表 params 用字符串 'gmv'/'net_sales'/'orders' 作 metric 引用，
但数据集 sql_metrics 只有 count -> Superset 4.x 报 "Metric does not exist"。
修复：给每个数据集补同名 SUM 指标，并修正仪表板原生筛选器结构。
"""
import json
import requests

BASE = "http://127.0.0.1:8088"
METRICS = {
    2: ["gmv"],
    3: ["net_sales"],
    4: ["gmv"],
    5: ["orders"],
    6: ["gmv"],
}


def session():
    s = requests.Session()
    tok = s.post(BASE + "/api/v1/security/login",
                 json={"username": "admin", "password": "admin",
                       "provider": "db", "refresh": True}, timeout=30).json()["access_token"]
    h = {"Authorization": "Bearer " + tok, "Content-Type": "application/json"}
    csrf = s.get(BASE + "/api/v1/security/csrf_token/", headers=h, timeout=30).json()["result"]
    h["X-CSRFToken"] = csrf
    s.cookies.set("csrf_token", csrf)
    return s, h


def add_metrics(s, h):
    for ds_id, names in METRICS.items():
        r = s.get(BASE + f"/api/v1/dataset/{ds_id}", headers=h, timeout=30)
        ds = r.json()["result"]
        # PUT 提交时必须去掉只读字段（id/created_on/changed_on），否则 422
        allowed = {"metric_name", "verbose_name", "expression", "metric_type",
                   "description", "d3format", "currency", "warning_text", "extra"}
        new_metrics = []
        for m in (ds.get("metrics") or []):
            new_metrics.append({k: v for k, v in m.items() if k in allowed})
        existing = {m["metric_name"] for m in new_metrics}
        changed = False
        for name in names:
            if name in existing:
                print(f"[SKIP] dataset {ds_id} metric {name} exists")
                continue
            new_metrics.append({
                "metric_name": name,
                "verbose_name": name,
                "expression": f"SUM({name})",
                "metric_type": "null",
            })
            changed = True
            print(f"[ADD] dataset {ds_id} metric {name} = SUM({name})")
        if not changed:
            continue
        r = s.put(BASE + f"/api/v1/dataset/{ds_id}",
                  json={"metrics": new_metrics}, headers=h, timeout=60)
        print(f"   PUT dataset {ds_id}: {r.status_code} {r.text[:120] if r.status_code!=200 else ''}")


def fix_dashboard_filter(s, h):
    r = s.get(BASE + "/api/v1/dashboard/1", headers=h, timeout=30)
    d = r.json()["result"]
    did = d["id"]
    meta = d.get("json_metadata") or {}
    if isinstance(meta, str):
        meta = json.loads(meta)
    meta["native_filter_configuration"] = [{
        "id": "stats_month_filter",
        "type": "NATIVE_FILTER",
        "name": "统计月份",
        "key": "flt_month",
        "filterType": "value",
        "targets": [{"datasetId": 2, "columnName": "stat_month"}],
        "defaultDataMask": {"extra": {}, "formData": None},
        "controlValues": {
            "enableEmptyFilter": False, "multiSelect": True,
            "defaultValue": None, "inverseSelection": False,
            "searchAllOptions": False,
        },
        "cascadeParentIds": [],
        "scope": {"rootPath": ["ROOT_ID"], "exclude": []},
        "subtype": "IN",
        "required": False,
        "description": "按统计月份联动筛选仪表板内所有图表",
    }]
    r = s.put(BASE + f"/api/v1/dashboard/{did}",
              json={"json_metadata": json.dumps(meta, ensure_ascii=False)},
              headers=h, timeout=60)
    print(f"[OK] dashboard filter: {r.status_code}")


def main():
    s, h = session()
    add_metrics(s, h)
    fix_dashboard_filter(s, h)
    print("\nDONE. Hard-refresh dashboard (Ctrl+F5).")


if __name__ == "__main__":
    main()
