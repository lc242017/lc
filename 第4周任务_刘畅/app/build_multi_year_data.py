# -*- coding: utf-8 -*-
"""
多年度 ADS 数据扩展（2022-2026）

- 2024：Hive `ads` 库真实导出数据，原样保留。
- 2022/2023/2025/2026：以 2024 真实数据为基准，按年度增长系数模拟扩展，
  固定随机种子保证可复现；界面显式标注 source=simulated，不与真实口径混用。

用途：让 Streamlit 问答支持“所有年份”查询与按年份预测。

输出：
  ../echarts/data/multi_year.json       各年份 KPI/趋势/品类/区域/支付/门店
  ../echarts/data/daily_gmv_multi.json  2022-2026 每日 GMV（预测模型输入）
"""
import json
import os
import random
from datetime import date

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "echarts", "data")
YEARS = [2022, 2023, 2024, 2025, 2026]
REAL_YEAR = 2024
# GMV 年度增长系数（以 2024 真实值为 1.0）
GROWTH = {2022: 0.74, 2023: 0.86, 2024: 1.0, 2025: 1.15, 2026: 1.31}
AOV = {2022: 2520.0, 2023: 2580.0, 2024: 2647.24, 2025: 2710.0, 2026: 2770.0}


def load(name):
    with open(os.path.join(DATA, name + ".json"), encoding="utf-8") as f:
        return json.load(f)


def dump(name, obj):
    with open(os.path.join(DATA, name + ".json"), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    print(f"[OK] {name}.json")


def main():
    rng = random.Random(20261127)
    kpi_real = load("kpi")[0]
    trend_real = load("trend")
    cat_real = load("category")
    reg_real = load("region")
    pay_real = load("paytype")
    store_real = load("store_rank")
    daily_real = load("daily_gmv")

    out = {
        "meta": {
            "real_year": REAL_YEAR,
            "years": YEARS,
            "simulated_years": [y for y in YEARS if y != REAL_YEAR],
            "note": "2024 为 Hive ads 库真实数据；2022/2023/2025/2026 基于 2024 按年度增长系数模拟扩展，仅供多年度问答演示，不与真实口径混用。",
            "data_source": "Hive ads（2024 真实） + 模拟扩展（其他年份）",
        },
        "kpi": {}, "trend": {}, "category": {}, "region": {},
        "paytype": {}, "store_rank": {},
    }
    daily_multi = []

    for y in YEARS:
        g = GROWTH[y]
        src = "real" if y == REAL_YEAR else "simulated"

        # ---- KPI ----
        if y == REAL_YEAR:
            k = dict(kpi_real)
        else:
            k = {
                "gmv": round(kpi_real["gmv"] * g, 2),
                "orders": int(kpi_real["orders"] * g * 0.97),
                "aov": AOV[y],
                "users": int(kpi_real["users"] * (0.85 + 0.04 * (y - 2022))),
                "stores": int(kpi_real["stores"] * (0.80 + 0.05 * (y - 2022))),
                "refundRate": round(kpi_real["refundRate"] + rng.uniform(-0.4, 0.4), 2),
            }
        k["year"], k["source"] = y, src
        out["kpi"][str(y)] = [k]

        # ---- 月度趋势 ----
        if y == REAL_YEAR:
            trend = [dict(r) for r in trend_real]
        else:
            trend = []
            for r in trend_real:
                mg = r["gmv"] * g * (1 + rng.uniform(-0.06, 0.06))
                mo = int(r["orders"] * g * 0.97 * (1 + rng.uniform(-0.05, 0.05)))
                trend.append({
                    "month": f"{y}-{r['month'][5:]}",
                    "gmv": round(mg, 2),
                    "orders": mo,
                    "aov": round(mg / mo, 2) if mo else AOV[y],
                    "discount": round(r["discount"] * g, 2),
                    "refund": int(r["refund"] * g * 0.97),
                })
        for r in trend:
            r["year"], r["source"] = y, src
        out["trend"][str(y)] = trend

        # ---- 品类 / 区域 / 支付 / 门店（结构占比保持稳定，金额按年缩放）----
        for key, real_rows, val_fields in [
            ("category", cat_real, ["netSales"]),
            ("region", reg_real, ["gmv"]),
            ("paytype", pay_real, ["gmv"]),
            ("store_rank", store_real, ["gmv"]),
        ]:
            if y == REAL_YEAR:
                rows = [dict(r) for r in real_rows]
            else:
                rows = []
                for r in real_rows:
                    nr = dict(r)
                    for fld in val_fields:
                        nr[fld] = round(float(r[fld]) * g * (1 + rng.uniform(-0.04, 0.04)), 2)
                    for fld in ("orders", "qty", "refund"):
                        if fld in nr:
                            nr[fld] = int(float(nr[fld]) * g * 0.97)
                    rows.append(nr)
            for r in rows:
                r["year"], r["source"] = y, src
            out[key][str(y)] = rows

        # ---- 每日 GMV ----
        for r in daily_real:
            d = date.fromisoformat(r["date"])
            if y != REAL_YEAR and d.month == 2 and d.day == 29:
                continue  # 非闰年无 2/29
            ds = f"{y}-{d.month:02d}-{d.day:02d}"
            if y == REAL_YEAR:
                rec = {"date": ds, "gmv": r["gmv"], "orders": r["orders"]}
            else:
                rec = {
                    "date": ds,
                    "gmv": round(float(r["gmv"]) * g * (1 + rng.uniform(-0.07, 0.07)), 2),
                    "orders": int(r["orders"] * g * 0.97 * (1 + rng.uniform(-0.06, 0.06))),
                }
            rec["year"], rec["source"] = y, src
            daily_multi.append(rec)

    dump("multi_year", out)
    dump("daily_gmv_multi", daily_multi)
    print(f"生成完成：{len(YEARS)} 个年份，{len(daily_multi)} 天日 GMV。真实年份={REAL_YEAR}")


if __name__ == "__main__":
    main()
