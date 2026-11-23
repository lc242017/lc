"""
步骤 5-①：Schema 抽取。

把给 NL2SQL 用的表结构收敛为一份「带口径注释」的上下文，
直接注入 Prompt（对应手册难点 3：把 Schema 注入 Prompt 约束生成结果）。
字段口径与 config/metrics.md 保持一致，避免模型自创口径。
"""

from __future__ import annotations

TABLES: dict[str, str] = {
    "dwd_order": (
        "订单明细事实表（一行一个订单，一单一品）："
        "order_id 订单号, user_id 用户ID, store_id 门店ID, product_id 商品ID, "
        "order_date 下单日期(格式 yyyy-MM-dd), order_ts 下单时间, quantity 购买件数, "
        "pay_amount 实付金额(元), status 订单状态(仅 status='paid' 是有效订单，"
        "金额类指标必须过滤 status='paid')"
    ),
    "dim_product": (
        "商品维度表：product_id 商品ID, product_name 商品名称, category 一级品类, "
        "brand 品牌, price 标准售价(元)"
    ),
    "dim_store": (
        "门店维度表：store_id 门店ID, store_name 门店名称, province 省份, "
        "city 城市, channel 渠道(线上/线下), open_date 开店日期"
    ),
    "dim_user": (
        "用户维度表：user_id 用户ID, register_date 注册日期, province 注册省份, "
        "member_level 会员等级"
    ),
    "ads_kpi_day": (
        "每日大盘指标结果表（已按口径算好，优先用它回答大盘问题）："
        "order_date 日期, gmv 当日GMV, orders 当日订单量, active_users 当日活跃用户数, aov 当日客单价"
    ),
}

# 常用口径提示：明确易错点，减少模型“数出多门”
METRIC_HINTS = """
常用口径约定（必须遵守）：
1. 金额类指标一律先过滤 status='paid'（有效订单），否则会把退款单算进 GMV；
2. 客单价 = sum(pay_amount) / count(distinct order_id)，不是 avg(pay_amount)；
3. 复购率 = 下单≥2次用户数 / 下单用户数（窗口内）；
4. 「上月」指自然月，用 substr(order_date,1,7) 比较；
5. 门店归属按 dim_store.province（履约门店），不按用户注册地；
6. 金额结果保留 2 位小数：round(...,2)。
"""


DIALECT_NOTE = """
SQL 方言：本地执行环境为 SQLite 兼容方言（支持 substr / date('now',...) / LIMIT 等）；
同一个查询上 Hive 时仅需把日期函数替换为 Hive 语法（如 add_months、from_unixtime），其余逻辑不变。
"""


def schema_desc(tables: list[str] | None = None) -> str:
    """生成注入 Prompt 的 Schema 描述；tables 为 None 时给全部表。"""
    names = tables or list(TABLES)
    lines = [f"- {t}: {TABLES[t]}" for t in names if t in TABLES]
    return "可用表：\n" + "\n".join(lines) + "\n" + METRIC_HINTS + DIALECT_NOTE


if __name__ == "__main__":
    print(schema_desc())
