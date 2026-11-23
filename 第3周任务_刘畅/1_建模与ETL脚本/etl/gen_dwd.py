"""
DWD 明细层数据生成器（本地可跑通版）。

说明：教学环境没有 Hive 集群，本脚本按 Hive DWD 层的表结构生成同构明细数据，
落到本地 SQLite（data/yunmall.db），表名去掉了 Hive 的库前缀：
    dwd.dwd_order     -> dwd_order
    dwd.dim_product   -> dim_product
    dwd.dim_store     -> dim_store
    dwd.dim_user      -> dim_user
字段口径与 sql/01_dwd_ddl.sql 完全一致，后续 DWS/ADS SQL 只需替换库前缀即可上 Hive。

业务口径：
- 有效订单：status='paid'（已支付且未退款），GMV 只统计有效订单的 pay_amount。
- 数据日期区间：最近 180 天（含昨天），用于趋势分析与预测建模。
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date, timedelta

import numpy as np
import pandas as pd

SEED = 20261110
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "yunmall.db")

DAYS = 180
END_DATE = date(2026, 11, 9)  # 业务数据截止日（不含今天）

PROVINCE_CITY = {
    "广东省": ["广州市", "深圳市", "佛山市", "东莞市"],
    "江苏省": ["南京市", "苏州市", "无锡市"],
    "浙江省": ["杭州市", "宁波市", "温州市"],
    "四川省": ["成都市", "绵阳市"],
    "北京市": ["北京市"],
}

CATEGORIES = {
    "生鲜果蔬": (18, 68, 0.28),
    "粮油调味": (25, 120, 0.14),
    "乳品烘焙": (12, 55, 0.16),
    "酒水饮料": (15, 268, 0.12),
    "休闲零食": (8, 45, 0.14),
    "家清日化": (10, 89, 0.07),
    "个护美妆": (29, 399, 0.05),
    "母婴用品": (35, 268, 0.04),
}
BRANDS = ["云购优选", "鲜到家", "每日鲜", "南山", "康润", "初见", "田野记", "轻食说"]


def build_dims(rng: np.random.Generator):
    stores = []
    sid = 0
    for prov, cities in PROVINCE_CITY.items():
        for city in cities:
            for seq in range(1, 3):
                sid += 1
                stores.append(
                    {
                        "store_id": f"S{sid:03d}",
                        "store_name": f"{city}{seq}号店",
                        "province": prov,
                        "city": city,
                        "channel": "线上" if seq == 1 else "线下",
                        "open_date": str(date(2023, 1, 1) + timedelta(days=int(rng.integers(0, 900)))),
                    }
                )
    dim_store = pd.DataFrame(stores)

    products = []
    pid = 0
    for cat, (pmin, pmax, _) in CATEGORIES.items():
        for _ in range(60):
            pid += 1
            price = round(float(rng.uniform(pmin, pmax)), 2)
            products.append(
                {
                    "product_id": f"P{pid:04d}",
                    "product_name": f"{rng.choice(BRANDS)}{cat}{pid:03d}",
                    "category": cat,
                    "brand": str(rng.choice(BRANDS)),
                    "price": price,
                }
            )
    dim_product = pd.DataFrame(products)

    users = []
    for uid in range(1, 60001):
        prov = str(rng.choice(list(PROVINCE_CITY.keys()), p=[0.42, 0.19, 0.19, 0.12, 0.08]))
        users.append(
            {
                "user_id": f"U{uid:05d}",
                "register_date": str(END_DATE - timedelta(days=int(rng.integers(30, 1500)))),
                "province": prov,
                "member_level": str(rng.choice(["普通", "银卡", "金卡", "黑卡"], p=[0.6, 0.25, 0.11, 0.04])),
            }
        )
    dim_user = pd.DataFrame(users)
    return dim_store, dim_product, dim_user


def build_orders(rng: np.random.Generator, dim_store, dim_product, dim_user) -> pd.DataFrame:
    """按「趋势 + 周末效应 + 大促脉冲 + 品类结构」生成订单明细。"""
    dates = [END_DATE - timedelta(days=DAYS - 1 - i) for i in range(DAYS)]
    cat_weight = np.array([w for _, _, w in CATEGORIES.values()])
    cat_weight = cat_weight / cat_weight.sum()

    prod_by_cat = {c: dim_product[dim_product.category == c] for c in CATEGORIES}
    user_ids = dim_user.user_id.to_numpy()
    # 用户活跃度分层：核心用户复购高，长尾用户偶发
    user_weight = rng.gamma(0.5, 1.0, size=len(user_ids))
    user_weight = user_weight / user_weight.sum()

    store_ids = dim_store.store_id.to_numpy()
    store_weight = rng.uniform(0.4, 2.2, size=len(store_ids))
    store_weight = store_weight / store_weight.sum()

    rows = []
    oid = 0
    for i, d in enumerate(dates):
        trend = 1.0 + 0.0035 * i                        # 温和增长
        weekday = 1.0 + (0.28 if d.weekday() >= 5 else 0.0)  # 周末提升
        promo = 1.9 if d.day in (8, 18, 28) else 1.0     # 月度会员日
        big_promo = 2.6 if (d.month, d.day) in {(11, 1), (10, 1)} else 1.0  # 大促
        base = 430 * trend * weekday * promo * big_promo
        n = int(rng.poisson(base))

        order_users = rng.choice(user_ids, size=n, p=user_weight)
        order_stores = rng.choice(store_ids, size=n, p=store_weight)
        order_cats = rng.choice(list(CATEGORIES.keys()), size=n, p=cat_weight)

        for k in range(n):
            oid += 1
            cat = order_cats[k]
            prod = prod_by_cat[cat].sample(1, random_state=int(rng.integers(0, 10**6))).iloc[0]
            qty = int(rng.choice([1, 1, 1, 2, 2, 3], p=[0.5, 0.2, 0.12, 0.1, 0.05, 0.03]))
            discount = float(rng.choice([1.0, 0.95, 0.9, 0.85, 0.8], p=[0.55, 0.2, 0.13, 0.08, 0.04]))
            pay = round(prod.price * qty * discount, 2)
            # 退款率 ~3.5%，闭单率 ~1.5%
            r = rng.random()
            status = "paid" if r > 0.05 else ("refunded" if r > 0.015 else "closed")
            rows.append(
                {
                    "order_id": f"O{oid:08d}",
                    "user_id": order_users[k],
                    "store_id": order_stores[k],
                    "product_id": prod.product_id,
                    "order_date": str(d),
                    "order_ts": f"{d} {int(rng.integers(8, 23)):02d}:{int(rng.integers(0, 60)):02d}:00",
                    "quantity": qty,
                    "pay_amount": pay,
                    "status": status,
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    rng = np.random.default_rng(SEED)
    dim_store, dim_product, dim_user = build_dims(rng)
    dwd_order = build_orders(rng, dim_store, dim_product, dim_user)

    conn = sqlite3.connect(DB_PATH)
    dim_store.to_sql("dim_store", conn, index=False, if_exists="replace")
    dim_product.to_sql("dim_product", conn, index=False, if_exists="replace")
    dim_user.to_sql("dim_user", conn, index=False, if_exists="replace")
    dwd_order.to_sql("dwd_order", conn, index=False, if_exists="replace")
    conn.execute("create index if not exists idx_order_date on dwd_order(order_date)")
    conn.execute("create index if not exists idx_order_store on dwd_order(store_id, order_date)")
    conn.commit()
    conn.close()

    paid = dwd_order[dwd_order.status == "paid"]
    print(f"[OK] DWD 生成完成 -> {DB_PATH}")
    print(f"     订单明细 {len(dwd_order):,} 行（有效 {len(paid):,} 行）")
    print(f"     门店 {len(dim_store)} / 商品 {len(dim_product)} / 用户 {len(dim_user)}")
    print(f"     日期区间 {dwd_order.order_date.min()} ~ {dwd_order.order_date.max()}")
    print(f"     累计 GMV {paid.pay_amount.sum():,.2f} 元")


if __name__ == "__main__":
    main()
