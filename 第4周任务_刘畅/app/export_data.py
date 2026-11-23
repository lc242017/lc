# -*- coding: utf-8 -*-
"""
ADS 指标层 -> JSON 数据导出
从 Hive 查询 ads 库指标表，导出为 Web 应用（ECharts 大屏 / Streamlit）可直接读取的 JSON。
运行：python3 export_data.py
"""
import json
import os
import re
import subprocess
from datetime import datetime

HIVE_URL = "jdbc:hive2://localhost:10000"
HIVE_BIN = ["docker"]
HIVE_ARGS = ["exec", "hive-demo-hive-server-1", "beeline",
             "-u", HIVE_URL, "-n", "root", "--silent=true", "-e"]

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "echarts", "data")
os.makedirs(OUT_DIR, exist_ok=True)


def query(sql):
    """执行 Hive SQL，返回 (columns, rows)"""
    proc = subprocess.run(
        HIVE_BIN + HIVE_ARGS + [sql],
        capture_output=True, text=True, encoding="utf-8", timeout=180
    )
    lines = [l for l in proc.stdout.splitlines() if l.strip().startswith("|")]
    if not lines:
        return [], []
    cells = [[c.strip() for c in l.strip().strip("|").split("|")] for l in lines]
    # 去掉分隔线行（+---+---+）
    cells = [r for r in cells if not all(set(c) <= set("- ") for c in r)]
    if not cells:
        return [], []
    header, rows = cells[0], cells[1:]
    return header, rows


def to_number(s):
    """Hive 数字字符串（含科学计数法）转 float/int"""
    try:
        if re.fullmatch(r"-?\d+", s):
            return int(s)
        return round(float(s), 2)
    except (ValueError, TypeError):
        return s


def export(sql, cols, json_path, numeric_cols=()):
    header, rows = query(sql)
    result = []
    for r in rows:
        if len(r) != len(cols):
            continue
        item = {}
        for name, val in zip(cols, r):
            item[name] = to_number(val) if name in numeric_cols else val
        result.append(item)
    full = os.path.join(OUT_DIR, json_path)
    with open(full, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[OK] {json_path}: {len(result)} 行")
    return result


def main():
    print("开始导出 ADS 指标数据 ...", datetime.now().strftime("%H:%M:%S"))

    export("select stat_month,gmv,orders,aov,discount_total,refund_orders "
           "from ads.ads_order_overview order by stat_month",
           ["month", "gmv", "orders", "aov", "discount", "refund"],
           "trend.json", {"gmv", "orders", "aov", "discount", "refund"})

    export("select category,orders,total_qty,net_sales from ads.ads_category_sales order by net_sales desc",
           ["category", "orders", "qty", "netSales"],
           "category.json", {"orders", "qty", "netSales"})

    export("select province,orders,gmv from ads.ads_region_sales order by gmv desc",
           ["province", "orders", "gmv"],
           "region.json", {"orders", "gmv"})

    export("select pay_type,orders,gmv from ads.ads_paytype_share order by gmv desc",
           ["payType", "orders", "gmv"],
           "paytype.json", {"orders", "gmv"})

    export("select store_id,store_name,province,orders,gmv from ads.ads_store_rank order by gmv desc limit 10",
           ["storeId", "storeName", "province", "orders", "gmv"],
           "store_rank.json", {"orders", "gmv"})

    export("select gmv,orders,aov,user_cnt,store_cnt,refund_rate from ads.ads_kpi",
           ["gmv", "orders", "aov", "users", "stores", "refundRate"],
           "kpi.json", {"gmv", "orders", "aov", "users", "stores", "refundRate"})

    print("全部导出完成 ->", OUT_DIR)


if __name__ == "__main__":
    main()
