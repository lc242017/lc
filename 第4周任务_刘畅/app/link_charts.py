# -*- coding: utf-8 -*-
"""用 Superset API 把 5 张图表正确关联到仪表板（确保 slices 关系生效）。"""
import requests

BASE = "http://127.0.0.1:8088"
s = requests.Session()
tok = s.post(BASE + "/api/v1/security/login",
             json={"username": "admin", "password": "admin", "provider": "db", "refresh": True},
             timeout=10).json()["access_token"]
h = {"Authorization": "Bearer " + tok, "Content-Type": "application/json"}
csrf = s.get(BASE + "/api/v1/security/csrf_token/", headers=h, timeout=10).json()["result"]
h["X-CSRFToken"] = csrf
s.cookies.set("csrf_token", csrf)

for cid in range(1, 6):
    r = s.put(BASE + f"/api/v1/chart/{cid}",
              json={"dashboards": [1]}, headers=h, timeout=30)
    print(f"chart {cid} -> dashboard 1: {r.status_code}")

# 验证
d = s.get(BASE + "/api/v1/dashboard/1", headers=h, timeout=10).json()["result"]
print("after: slices count =", len(d.get("slices", [])))
for sl in d.get("slices", []):
    print("  ", sl.get("id"), sl.get("slice_name"))
