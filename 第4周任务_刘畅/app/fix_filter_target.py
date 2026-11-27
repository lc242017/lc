import sqlite3, json

c = sqlite3.connect("/app/superset_home/superset.db")
row = c.execute("select json_metadata from dashboards where id=1").fetchone()
meta = json.loads(row[0] or "{}")
for f in meta.get("native_filter_configuration", []):
    f["id"] = "NATIVE_FILTER-month"
    f.pop("key", None)
    f["cascadeParentIds"] = []
    f["scope"] = {"rootPath": ["ROOT_ID"], "excluded": []}
    f["type"] = "NATIVE_FILTER"
    f["filterType"] = "filter_select"
    f["targets"] = [{"column": {"name": "stat_month"}, "datasetId": 2}]
    f["defaultDataMask"] = {"extraFormData": {}, "filterState": {"value": None}}
    f["controlValues"] = {
        "enableEmptyFilter": False, "multiSelect": True,
        "defaultValue": None, "inverseSelection": False,
        "searchAllOptions": True,
    }
    f.pop("subtype", None)
c.execute("update dashboards set json_metadata=? where id=1",
          (json.dumps(meta, ensure_ascii=False),))
c.commit()
print(json.dumps(meta, ensure_ascii=False)[:900])
