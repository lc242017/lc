# -*- coding: utf-8 -*-
"""
NL2SQL 简化引擎（第4周）
将中文经营问题解析为对 ADS 指标层的查询意图，返回 SQL 语句 + 结果数据。
降级实现：直接读 data/*.json（预计算的 ADS 指标），保证无 Hive/无第三方依赖也能运行。
完整版可通过 USE_HIVE=True 切换到实时 Hive 查询。
"""
import json
import os
import re
import subprocess

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "echarts", "data")
USE_HIVE = os.environ.get("USE_HIVE", "0") == "1"


def _load(name):
    with open(os.path.join(DATA, name + ".json"), encoding="utf-8") as f:
        return json.load(f)


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


# ---- 预测：只返回历史实际数据，未来预测值由界面手动输入 ----
def _build_forecast_history():
    trend = _load("trend")
    cols = ["month", "gmv", "series"]
    rows = [[r["month"], f"{float(r['gmv']):.2f}", "实际"] for r in trend]
    return cols, rows


# ---- 意图识别规则：关键词 -> 数据集 + SQL 模板 ----
RULES = [
    (r"(预测|预估|预计|forecast).*(gmv|销售|订单|额)|预测|预估|预计",
     "forecast", "SELECT order_date,gmv FROM dws.dws_order_day ORDER BY order_date",
     "forecast", "GMV 趋势预测建模（手册步骤3 · lag1/ma7+线性回归）"),
    (r"(gmv|成交|销售总额|总额|营业额).*(多少|总共|总体|多少)|总体|整体|总览|核心指标|kpi",
     "kpi", "SELECT gmv,orders,aov,user_cnt,store_cnt,refund_rate FROM ads.ads_kpi",
     "kpi", "核心经营指标"),
    (r"(月度|每月|趋势|走势|各月|月份).*(gmv|销售|订单)|趋势|走势|各月",
     "trend", "SELECT stat_month,gmv,orders FROM ads.ads_order_overview ORDER BY stat_month",
     "line", "月度销售趋势"),
    (r"(品类|类别|产品类).*(排行|销售|排名)|品类|类别",
     "category", "SELECT category,net_sales FROM ads.ads_category_sales ORDER BY net_sales DESC",
     "bar", "品类销售排行"),
    (r"(省份|区域|地区|各地).*(销售|gmv)|区域|省份|地区",
     "region", "SELECT province,gmv FROM ads.ads_region_sales ORDER BY gmv DESC",
     "bar", "区域 GMV 分布"),
    (r"(支付|付款).*(方式|占比|分布)|支付方式|付款方式",
     "paytype", "SELECT pay_type,orders FROM ads.ads_paytype_share ORDER BY gmv DESC",
     "pie", "支付方式占比"),
    (r"(门店|店铺).*(排行|top|排名|销售)|top10|前十|门店",
     "store_rank", "SELECT store_name,gmv FROM ads.ads_store_rank ORDER BY gmv DESC LIMIT 10",
     "bar", "门店销售 Top10"),
]

# 省份 -> GMV 单条查询（如"广东省销售额是多少"）
PROVINCE_RE = re.compile(r"([\u4e00-\u9fa5]{2,4}(?:省|市|自治区)).*(销售|gmv|多少|额)")


def parse(question):
    """返回 (sql, dataset_name, chart_type, title, preloaded_data_or_None)"""
    q = question.strip()
    # 单省份查询
    m = PROVINCE_RE.search(q)
    if m:
        province = m.group(1)
        data = _load("region")
        hit = [r for r in data if r["province"] == province]
        sql = (f"SELECT province,gmv FROM ads.ads_region_sales "
               f"WHERE province='{province}'")
        rows = [[r["province"], r["gmv"]] for r in hit]
        return sql, None, "value", f"{province}销售 GMV", (["province", "gmv"], rows)
    # 规则匹配
    for pattern, ds, sql, chart, title in RULES:
        if re.search(pattern, q, re.I):
            if ds == "forecast":
                cols, rows = _build_forecast_history()
                return sql, None, "forecast", title, (cols, rows)
            return sql, ds, chart, title, None
    # 兜底：核心指标
    sql = "SELECT gmv,orders,aov,user_cnt,store_cnt,refund_rate FROM ads.ads_kpi"
    return sql, "kpi", "kpi", "核心经营指标（默认）", None


def answer(question):
    """返回 dict: {question, sql, chart, title, columns, rows, model?}
    chart=='forecast' 时额外携带 model：第3周手册步骤3的完整预测建模结果。"""
    sql, ds, chart, title, preloaded = parse(question)
    model = None
    if preloaded is not None:
        cols, rows = preloaded
        rows = [[str(x) for x in r] for r in rows]
    if chart == "forecast":
        try:
            from forecast_model import build_forecast
            model = build_forecast()
        except Exception as ex:
            model = {"error": str(ex)}
    elif USE_HIVE:
        cols, rows = _hive(sql)
    else:
        data = _load(ds)
        if ds == "kpi":
            k = data[0]
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
    return {"question": question, "sql": sql, "chart": chart,
            "title": title, "columns": cols, "rows": rows, "model": model}


if __name__ == "__main__":
    import sys
    qs = sys.argv[1:] or ["总体GMV是多少", "品类销售排行", "浙江省销售额是多少"]
    for q in qs:
        r = answer(q)
        print(f"\nQ: {q}\nSQL: {r['sql']}\n图表: {r['chart']} | {r['title']}")
        print(f"列: {r['columns']}")
        for row in r["rows"][:6]:
            print("  ", row)
