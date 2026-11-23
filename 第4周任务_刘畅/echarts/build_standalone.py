# -*- coding: utf-8 -*-
"""
将 index.html 中的 fetch('data/xxx.json') 替换为内嵌 JSON，
生成可直接双击打开的 index_standalone.html（无需 HTTP 服务）。
运行：python3 build_standalone.py
"""
import json
import os
import re

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")

with open(os.path.join(BASE, "index.html"), encoding="utf-8") as f:
    html = f.read()

# 读取所有数据
datasets = {}
for fn in os.listdir(DATA):
    if fn.endswith(".json"):
        with open(os.path.join(DATA, fn), encoding="utf-8") as f:
            datasets[fn[:-5]] = json.load(f)

# 注入数据字典
inject = "<script>\nconst DATA = " + json.dumps(datasets, ensure_ascii=False) + ";\n</script>\n"
html = html.replace("</head>", inject + "</head>", 1)

# 替换 load 函数：优先用内嵌 DATA
old = """function load(name, cb){
  fetch('data/'+name+'.json').then(r=>r.json()).then(cb)
    .catch(e=>console.error('load '+name+' failed:', e));
}"""
new = """function load(name, cb){
  if (typeof DATA !== 'undefined' && DATA[name]) { cb(DATA[name]); return; }
  fetch('data/'+name+'.json').then(r=>r.json()).then(cb)
    .catch(e=>console.error('load '+name+' failed:', e));
}"""
assert old in html, "load function not found"
html = html.replace(old, new, 1)

out = os.path.join(BASE, "index_standalone.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(html)

print(f"[OK] 生成 {out} ({len(datasets)} 个数据集内嵌)")
