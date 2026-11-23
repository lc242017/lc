# -*- coding: utf-8 -*-
"""
ADS 指标数据 -> MySQL(ydsh_ads) 同步
让 Superset 通过 pymysql 连接预计算指标表（手册步骤1的 mysql 连接串目标库）。
运行：python3 sync_to_mysql.py
"""
import json
import os
import subprocess

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "echarts", "data")
MYSQL = ["docker", "exec", "-i", "hive-demo-mysql-1", "mysql", "-uroot", "-proot", "ydsh_ads"]


def load(name):
    with open(os.path.join(DATA, name + ".json"), encoding="utf-8") as f:
        return json.load(f)


def esc(v):
    if v is None:
        return "NULL"
    if isinstance(v, str):
        return "'" + v.replace("\\", "\\\\").replace("'", "\\'") + "'"
    return str(v)


DDL = """
DROP TABLE IF EXISTS ads_kpi;
CREATE TABLE ads_kpi(gmv DOUBLE, orders INT, aov DOUBLE, users INT, stores INT, refund_rate DOUBLE) CHARSET utf8mb4;
DROP TABLE IF EXISTS ads_order_overview;
CREATE TABLE ads_order_overview(stat_month VARCHAR(10), gmv DOUBLE, orders INT, aov DOUBLE, discount DOUBLE, refund INT) CHARSET utf8mb4;
DROP TABLE IF EXISTS ads_category_sales;
CREATE TABLE ads_category_sales(category VARCHAR(50), orders INT, qty INT, net_sales DOUBLE) CHARSET utf8mb4;
DROP TABLE IF EXISTS ads_region_sales;
CREATE TABLE ads_region_sales(province VARCHAR(50), orders INT, gmv DOUBLE) CHARSET utf8mb4;
DROP TABLE IF EXISTS ads_paytype_share;
CREATE TABLE ads_paytype_share(pay_type VARCHAR(50), orders INT, gmv DOUBLE) CHARSET utf8mb4;
DROP TABLE IF EXISTS ads_store_rank;
CREATE TABLE ads_store_rank(store_id VARCHAR(20), store_name VARCHAR(100), province VARCHAR(50), orders INT, gmv DOUBLE) CHARSET utf8mb4;
"""


def inserts(table, rows, col_order):
    if not rows:
        return ""
    values = []
    for r in rows:
        values.append("(" + ",".join(esc(r[c]) for c in col_order) + ")")
    return f"INSERT INTO {table} ({','.join(col_order)}) VALUES " + ",".join(values) + ";"


# (表名, 数据文件, [(表列名, JSON键), ...])
TABLES = [
    ("ads_kpi", "kpi", [("gmv", "gmv"), ("orders", "orders"), ("aov", "aov"),
                        ("users", "users"), ("stores", "stores"), ("refund_rate", "refundRate")]),
    ("ads_order_overview", "trend", [("stat_month", "month"), ("gmv", "gmv"),
                        ("orders", "orders"), ("aov", "aov"), ("discount", "discount"), ("refund", "refund")]),
    ("ads_category_sales", "category", [("category", "category"), ("orders", "orders"),
                        ("qty", "qty"), ("net_sales", "netSales")]),
    ("ads_region_sales", "region", [("province", "province"), ("orders", "orders"), ("gmv", "gmv")]),
    ("ads_paytype_share", "paytype", [("pay_type", "payType"), ("orders", "orders"), ("gmv", "gmv")]),
    ("ads_store_rank", "store_rank", [("store_id", "storeId"), ("store_name", "storeName"),
                        ("province", "province"), ("orders", "orders"), ("gmv", "gmv")]),
]


def main():
    stmts = [DDL]
    for table, data_file, colmap in TABLES:
        rows = load(data_file)
        cols = [c for c, _ in colmap]
        values = []
        for r in rows:
            values.append("(" + ",".join(esc(r[jkey]) for _, jkey in colmap) + ")")
        if values:
            stmts.append(f"INSERT INTO {table} ({','.join(cols)}) VALUES " + ",".join(values) + ";")

    sql = "\n".join(s for s in stmts if s)
    proc = subprocess.run(MYSQL, input=sql, capture_output=True, text=True,
                          encoding="utf-8", timeout=60)
    real_err = [l for l in proc.stderr.splitlines() if "ERROR" in l]
    if real_err:
        print("MYSQL ERROR:", "\n".join(real_err[:5]))
    else:
        print("[OK] ADS 指标已同步到 MySQL ydsh_ads 库（6 张表）")

    # 校验
    chk = subprocess.run(
        ["docker", "exec", "hive-demo-mysql-1", "mysql", "-uroot", "-proot",
         "-e", "select table_name,table_rows from information_schema.tables where table_schema='ydsh_ads';"],
        capture_output=True, text=True, encoding="utf-8")
    print(chk.stdout)


if __name__ == "__main__":
    main()
