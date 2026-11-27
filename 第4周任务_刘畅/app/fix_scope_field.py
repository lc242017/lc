import sqlite3, json

DB = "/app/superset_home/superset.db"
c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row
d = c.execute("select id, json_metadata from dashboards where id=1").fetchone()
meta = json.loads(d["json_metadata"] or "{}")
changed = False
for f in meta.get("native_filter_configuration", []):
    scope = f.get("scope", {})
    if "exclude" in scope:
        scope["excluded"] = scope.pop("exclude")
        changed = True
    if "excluded" not in scope:
        scope["excluded"] = []
        changed = True
    print("FILTER", f.get("name"), "-> scope", scope)
if changed:
    c.execute("update dashboards set json_metadata=? where id=1",
              (json.dumps(meta, ensure_ascii=False),))
    c.commit()
    print("UPDATED")
else:
    print("NO CHANGE")
print("RAW:", json.dumps(meta, ensure_ascii=False)[:500])
