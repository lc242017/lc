# -*- coding: utf-8 -*-
"""
NL2SQL 简化引擎（第4周 · 多年度增强版）
把中文经营问题解析为对 ADS 指标层的查询意图，返回 SQL + 结果数据。

年份支持：
  - 可识别“2025年GMV”“23年销售趋势”“去年/今年”等，按年份取数；
  - 不指定年份时聚合全部年份（2022-2026）；
  - 2024 为 Hive ads 库真实数据，其余年份为模拟扩展（界面显式标注）。

降级实现：直接读 data/*.json（预计算的 ADS 指标）；USE_HIVE=1 可切实时 Hive。
"""
import json
import os
import re
import subprocess

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "echarts", "data")
USE_HIVE = os.environ.get("USE_HIVE", "0") == "1"
ALL_YEARS = [2022, 2023, 2024, 2025, 2026]
REAL_YEAR = 2024
YEAR_WORDS = {"今年": 2026, "去年": 2025, "前年": 2024, "明年": 2027}


def _load(name):
    with open(os.path.join(DATA, name + ".json"), encoding="utf-8") as f:
        return json.load(f)


def _multi():
    return _load("multi_year")


def _hive(sql):
    """实时查询 Hive（可选）"""
    proc = subprocess.run(
        ["docker", "exec", "hive-demo-hive-server-1", "beeline",
         "-u", "jdbc:hive2://localhost:10000", "-n", "root", "--silent=true", "-e", sql],
        capture_output=True, text=True, encoding="utf-8", timeout=180)
    lines = [l for l in proc.stdout.splitlines() if l.strip().startswith("|")]
    cells = [[c.strip() for c in l.strip().strip("|").split("|")] for l in lines]
    cells = [r for r in cells if not all(set(c) <= set("- ") for c in r)]
    return cells[0] if cells else [], cells[1:] if len(cells) > 1 else []


def extract_year(question, default=None):
    """从问题抽取年份：2025年 / 25年 / 去年 / 今年；无年份返回 default。"""
    q = str(question)
    for word, y in YEAR_WORDS.items():
        if word in q:
            return y
    m = re.search(r"(20\d{2})\s*年?", q)
    if m and 2020 <= int(m.group(1)) <= 2030:
        return int(m.group(1))
    m = re.search(r"(?<!\d)(\d{2})\s*年", q)
    if m and 2020 <= 2000 + int(m.group(1)) <= 2030:
        return 2000 + int(m.group(1))
    return default


def extract_days(question, default=7):
    """从问题抽取预测天数：'未来30天'、'预测14天'、'7天预测'。"""
    m = re.search(r"(?:未来|接着|往后|预测|预估)?\s*(\d{1,3})\s*(?:天|日|days?|d)",
                  str(question), re.I)
    if m and 1 <= int(m.group(1)) <= 365:
        return int(m.group(1))
    return default


def _rows_for(dataset, year):
    """按年份取数；year=None 表示全部年份（做聚合）。"""
    m = _multi()
    if year in ALL_YEARS:
        return [dict(r) for r in m[dataset].get(str(year), [])]
    rows = []
    for y in ALL_YEARS:
        rows.extend([dict(r) for r in m[dataset].get(str(y), [])])
    if dataset == "kpi":
        gmv = sum(float(r["gmv"]) for r in rows)
        orders = sum(int(r["orders"]) for r in rows)
        last = rows[-1]
        return [{
            "gmv": round(gmv, 2), "orders": orders,
            "aov": round(gmv / orders, 2) if orders else 0,
            "users": max(int(r["users"]) for r in rows),
            "stores": max(int(r["stores"]) for r in rows),
            "refundRate": round(sum(float(r["refundRate"]) for r in rows) / len(rows), 2),
            "year": "全部", "source": "mixed",
        }]
    if dataset == "trend":
        return sorted(rows, key=lambda r: r["month"])
    # 品类/区域/支付/门店：按名称汇总多年
    name_key = {"category": "category", "region": "province",
                "paytype": "payType", "store_rank": "storeName"}[dataset]
    agg = {}
    for r in rows:
        k = r[name_key]
        if k not in agg:
            agg[k] = dict(r)
            agg[k]["_first"] = True
            continue
        for fld, val in r.items():
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                agg[k][fld] = round(agg[k].get(fld, 0) + val, 2) if isinstance(val, float) \
                    else int(agg[k].get(fld, 0) + val)
    return sorted(agg.values(), key=lambda r: float(r.get("gmv") or r.get("netSales") or 0), reverse=True)


def _year_clause(year):
    if year in ALL_YEARS:
        return f" WHERE stat_year = '{year}'"
    return " WHERE stat_year BETWEEN '2022' AND '2026'"


SQL_TPL = {
    "forecast": "SELECT order_date,gmv FROM dws.dws_order_day ORDER BY order_date",
    "kpi": "SELECT gmv,orders,aov,user_cnt,store_cnt,refund_rate FROM ads.ads_kpi",
    "trend": "SELECT stat_month,gmv,orders FROM ads.ads_order_overview ORDER BY stat_month",
    "category": "SELECT category,net_sales FROM ads.ads_category_sales ORDER BY net_sales DESC",
    "region": "SELECT province,gmv FROM ads.ads_region_sales ORDER BY gmv DESC",
    "paytype": "SELECT pay_type,orders FROM ads.ads_paytype_share ORDER BY gmv DESC",
    "store_rank": "SELECT store_name,gmv FROM ads.ads_store_rank ORDER BY gmv DESC LIMIT 10",
}

RULES = [
    (r"(预测|预估|预计|forecast).*(gmv|销售|订单|额)|预测|预估|预计|未来\s*\d{1,3}\s*天",
     "forecast", "forecast", "GMV 趋势预测建模（手册步骤3 · lag1/ma7+线性回归）"),
    (r"(gmv|成交|销售总额|总额|营业额).*(多少|总共|总体|多少)|总体|整体|总览|核心指标|kpi",
     "kpi", "kpi", "核心经营指标"),
    (r"(月度|每月|趋势|走势|各月|月份).*(gmv|销售|订单)|趋势|走势|各月",
     "trend", "line", "月度销售趋势"),
    (r"(品类|类别|产品类).*(排行|销售|排名)|品类|类别",
     "category", "bar", "品类销售排行"),
    (r"(省份|区域|地区|各地).*(销售|gmv)|区域|省份|地区",
     "region", "bar", "区域 GMV 分布"),
    (r"(支付|付款).*(方式|占比|分布)|支付方式|付款方式",
     "paytype", "pie", "支付方式占比"),
    (r"(门店|店铺).*(排行|top|排名|销售)|top10|前十|门店",
     "store_rank", "bar", "门店销售 Top10"),
]

PROVINCE_RE = re.compile(r"([\u4e00-\u9fa5]{2,4}(?:省|市|自治区)).*(销售|gmv|多少|额)")


def parse(question):
    """返回 (sql, dataset, chart, title, preloaded, year)"""
    q = question.strip()
    year = extract_year(q)
    m = PROVINCE_RE.search(q)
    if m:
        province = m.group(1)
        data = _rows_for("region", year)
        hit = [r for r in data if r["province"] == province]
        sql = (f"SELECT province,gmv FROM ads.ads_region_sales "
               f"{_year_clause(year)} AND province='{province}'")
        rows = [[r["province"], r["gmv"]] for r in hit]
        return sql, None, "value", f"{province}销售 GMV", (["province", "gmv"], rows), year
    for pattern, ds, chart, title in RULES:
        if re.search(pattern, q, re.I):
            sql = SQL_TPL[ds] + _year_clause(year)
            if ds == "forecast":
                cols, rows = _trend_history(year)
                return sql, None, "forecast", title, (cols, rows), year
            return sql, ds, chart, title, None, year
    sql = SQL_TPL["kpi"] + _year_clause(year)
    return sql, "kpi", "kpi", "核心经营指标（默认）", None, year


def _trend_history(year):
    rows = _rows_for("trend", year)
    return ["month", "gmv", "series"], [[r["month"], f"{float(r['gmv']):.2f}", "实际"] for r in rows]


def answer(question, future_days=None, year=None):
    """返回 dict: {..., year, model?}；预测时 model 含按年份训练的完整建模结果。"""
    sql, ds, chart, title, preloaded, qyear = parse(question)
    if year is None:
        year = qyear  # 问题里写的年份优先
    model = None
    if preloaded is not None:
        cols, rows = preloaded
        rows = [[str(x) for x in r] for r in rows]
    if chart == "forecast":
        days = future_days if future_days is not None else extract_days(question)
        try:
            from forecast_model import build_forecast
            model = build_forecast(days, year=year)
        except Exception as ex:
            model = {"error": str(ex)}
    elif USE_HIVE:
        cols, rows = _hive(sql)
    elif preloaded is None and ds is not None:
        data = _rows_for(ds, year)
        if ds == "kpi":
            k = data[0]
            # 列名与界面 KPI 卡片保持一致（user_cnt/store_cnt/refund_rate）
            cols = ["gmv", "orders", "aov", "user_cnt", "store_cnt", "refund_rate"]
            rows = [[str(k["gmv"]), str(k["orders"]), str(k["aov"]),
                     str(k["users"]), str(k["stores"]), str(k["refundRate"])]]
        elif ds == "trend":
            cols = ["stat_month", "gmv", "orders"]
            rows = [[r["month"], str(r["gmv"]), str(r["orders"])] for r in data]
        elif ds == "category":
            cols = ["category", "net_sales"]
            rows = [[r["category"], str(r["netSales"])] for r in data]
        elif ds == "region":
            cols = ["province", "gmv"]
            rows = [[r["province"], str(r["gmv"])] for r in data]
        elif ds == "paytype":
            cols = ["pay_type", "orders"]
            rows = [[r["payType"], str(r["orders"])] for r in data]
        elif ds == "store_rank":
            cols = ["store_name", "gmv"]
            rows = [[r["storeName"], str(r["gmv"])] for r in data]
        else:
            cols, rows = [], []
    return {"question": question, "sql": sql, "chart": chart, "title": title,
            "columns": cols, "rows": rows, "year": year, "model": model}


if __name__ == "__main__":
    import sys
    qs = sys.argv[1:] or ["2024年总体GMV", "2025年销售趋势", "预测未来30天GMV"]
    for q in qs:
        r = answer(q)
        m = r.get("model") or {}
        print(f"\nQ: {q}\n年份: {r['year']}\nSQL: {r['sql']}\n图表: {r['chart']} | {r['title']}")
        print(f"行: {r['columns']} / {len(r['rows'])} 行")
        if m:
            print(f"预测天数: {m.get('future_days')} / 行数: {len(m.get('future_rows', []))}")
        for row in r["rows"][:4]:
            print("  ", row)
