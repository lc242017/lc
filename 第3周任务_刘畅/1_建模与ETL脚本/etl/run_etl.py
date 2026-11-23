"""
步骤 1 + 步骤 2 执行器：DWS / ADS 建模 + KPI 指标计算。

本地用 SQLite 执行 sql/local/*.sql（与 Hive 版逻辑一一对应），
跑完做口径一致性复核，并把结果导出到 output/。

用法：
    python etl/run_etl.py
"""

from __future__ import annotations

import json
import os
import sqlite3

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "data", "yunmall.db")
OUT_DIR = os.path.join(ROOT, "output")
SQL_FILES = ["sql/local/01_dws_build.sql", "sql/local/02_ads_build.sql", "sql/local/03_kpi.sql"]


def run_sql_file(conn: sqlite3.Connection, rel_path: str) -> None:
    path = os.path.join(ROOT, rel_path)
    with open(path, "r", encoding="utf-8") as f:
        script = f.read()
    # 去掉注释行后按分号切分，逐条执行
    lines = [ln for ln in script.splitlines() if not ln.strip().startswith("--")]
    stmts = [s.strip() for s in "\n".join(lines).split(";") if s.strip()]
    for stmt in stmts:
        conn.execute(stmt)
    conn.commit()
    print(f"[OK] {rel_path}: 执行 {len(stmts)} 条语句")


def verify_consistency(conn: sqlite3.Connection) -> dict:
    """三条链路算 GMV 必须相等，否则说明口径/关联出错。"""
    q = lambda s: conn.execute(s).fetchone()[0]  # noqa: E731
    check = {
        "gmv_from_dwd": round(q("select sum(pay_amount) from dwd_order where status='paid'"), 2),
        "gmv_from_dws": round(q("select sum(gmv) from dws_order_store_day"), 2),
        "gmv_from_ads": round(q("select sum(gmv) from ads_kpi_day"), 2),
        "gmv_from_channel": round(q("select sum(gmv) from dws_channel_day"), 2),
        "gmv_from_week": round(q("select sum(gmv) from dws_order_week"), 2),
        "orders_from_dwd": q("select count(distinct order_id) from dwd_order where status='paid'"),
        "orders_from_dws": q("select sum(orders) from dws_order_store_day"),
        "orders_from_ads": q("select sum(orders) from ads_kpi_day"),
    }
    check["gmv_consistent"] = (
        check["gmv_from_dwd"] == check["gmv_from_dws"]
        == check["gmv_from_ads"] == check["gmv_from_channel"]
        == check["gmv_from_week"]
    )
    check["orders_consistent"] = (
        check["orders_from_dwd"] == check["orders_from_dws"] == check["orders_from_ads"]
    )
    return check


def main() -> None:
    if not os.path.exists(DB_PATH):
        raise SystemExit("未找到 data/yunmall.db，请先执行：python etl/gen_dwd.py")
    os.makedirs(OUT_DIR, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    for f in SQL_FILES:
        run_sql_file(conn, f)

    check = verify_consistency(conn)
    print("\n=== 口径一致性复核 ===")
    for k, v in check.items():
        print(f"  {k:20s} = {v}")
    assert check["gmv_consistent"] and check["orders_consistent"], "口径不一致，停止出数"
    with open(os.path.join(OUT_DIR, "dws_ads_check.json"), "w", encoding="utf-8") as f:
        json.dump(check, f, ensure_ascii=False, indent=2)

    # ---------- 导出结果表 ----------
    exports = {
        "dws_order_store_day.csv": "select * from dws_order_store_day order by order_date, store_id",
        "dws_channel_day.csv": "select * from dws_channel_day order by order_date, channel",
        "dws_order_week.csv": "select * from dws_order_week order by week_start",
        "ads_user_tier_summary.csv": "select * from ads_user_tier_summary order by gmv desc",
        "ads_user_value.csv": "select * from ads_user_value order by gmv desc",
        "ads_channel_share.csv": "select * from ads_channel_share order by gmv desc",
        "ads_category_top10.csv": "select * from ads_category_top10 order by sales desc",
        "ads_kpi_day.csv": "select * from ads_kpi_day order by order_date",
        "ads_kpi_month.csv": "select * from ads_kpi_month order by month",
        "ads_repurchase_month.csv": "select * from ads_repurchase_month order by month",
    }
    for fname, sql in exports.items():
        df = pd.read_sql_query(sql, conn)
        df.to_csv(os.path.join(OUT_DIR, fname), index=False, encoding="utf-8-sig")
        print(f"[OUT] {fname:28s} {len(df):>6,} 行")

    # ---------- KPI 结果表（长表，便于直接进看板/报告） ----------
    overall = pd.read_sql_query("select * from ads_kpi_overall", conn).iloc[0]
    kpi = pd.DataFrame(
        [
            {"metric": "GMV", "value": round(float(overall["gmv"]), 2), "unit": "元",
             "definition": "所有有效订单实付金额之和"},
            {"metric": "订单量", "value": int(overall["orders"]), "unit": "单",
             "definition": "有效订单去重订单数"},
            {"metric": "客单价 AOV", "value": round(float(overall["aov"]), 2), "unit": "元",
             "definition": "GMV ÷ 订单量"},
            {"metric": "活跃用户数", "value": int(overall["active_users"]), "unit": "人",
             "definition": "有下单行为的去重用户数"},
            {"metric": "复购率", "value": round(float(overall["repurchase_rate"]) * 100, 2), "unit": "%",
             "definition": "下单≥2次用户数 ÷ 下单用户数"},
        ]
    )
    # 品类销售占比（任务书 KPI：品类销售占比）
    cat = pd.read_sql_query(
        "select category, sales, sales_share from ads_category_top10 order by sales desc", conn)
    cat_rows = [
        {"metric": f"品类占比·{r['category']}", "value": round(float(r["sales_share"]) * 100, 2),
         "unit": "%", "definition": "该品类 GMV ÷ 全部 GMV"}
        for _, r in cat.iterrows()
    ]
    kpi = pd.concat([kpi, pd.DataFrame(cat_rows)], ignore_index=True)
    kpi.to_csv(os.path.join(OUT_DIR, "kpi_summary.csv"), index=False, encoding="utf-8-sig")

    print("\n=== 核心 KPI ===")
    for _, r in kpi.iterrows():
        if r["metric"] == "复购率":
            val = f"{r['value']:.2f}%"
        elif r["metric"] in ("订单量", "活跃用户数"):
            val = f"{int(r['value']):,}"
        else:
            val = f"{r['value']:,.2f}"
        unit = "" if r["metric"] == "复购率" else r["unit"]
        print(f"  {r['metric']:<10s} {val:>16s} {unit}   （{r['definition']}）")

    print("\n=== 品类销售额 Top ===")
    top = pd.read_sql_query("select * from ads_category_top10 order by sales desc", conn)
    for _, r in top.iterrows():
        print(f"  {r['category']:<8s} {r['sales']:>14,.2f} 元  {int(r['cnt']):>7,} 单  占比 {r['sales_share'] * 100:>5.2f}%")

    print("\n=== 渠道结构 ===")
    share = pd.read_sql_query("select * from ads_channel_share order by gmv desc", conn)
    for _, r in share.iterrows():
        print(f"  {r['channel']:<4s} GMV {r['gmv']:>14,.2f} 元  占比 {r['gmv_share'] * 100:>5.2f}%  订单 {int(r['orders']):>7,} 单")

    print("\n=== 用户价值分层 ===")
    tiers = pd.read_sql_query("select * from ads_user_tier_summary order by gmv desc", conn)
    for _, r in tiers.iterrows():
        print(f"  {r['value_tier']:<4s} 用户 {int(r['users']):>7,} 人  GMV {r['gmv']:>14,.2f} 元  占比 {r['gmv_share'] * 100:>5.2f}%")

    conn.close()
    print(f"\n[OK] 产物已写入 {OUT_DIR}")


if __name__ == "__main__":
    main()
