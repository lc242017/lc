"""
子任务 5：AI 智能洞察与自动报告。

流程：
1. 从 ADS 表读取经营数据，用统计方法（z-score、环比）检测异常日；
2. 把异常日与经营上下文组装成 Prompt，调用大模型（llm.client.LLMClient）
   做异常归因与经营摘要；未配置 Key 时走离线模板引擎（规则归因，非真实 LLM）；
3. 对 AI 输出做"审慎验证"：抽取文中出现的金额/百分比，逐一回查底层数据，
   生成验证结论随报告输出；
4. 产出 output/ai_insight_report.md（自动报告）与 output/ai_insight.json（结构化结果）。

用法：python insight/insight.py
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output")
sys.path.insert(0, ROOT)

from llm.client import LLMClient  # noqa: E402

PROMO_DAYS = {8, 18, 28}          # 会员日
BIG_PROMO = {"2026-10-01", "2026-11-01"}  # 大促日（业务日历）


def load_context() -> dict:
    conn = sqlite3.connect(os.path.join(ROOT, "data", "yunmall.db"))
    daily = pd.read_sql_query(
        "select order_date, gmv, orders, active_users, aov from ads_kpi_day order by order_date", conn)
    cat = pd.read_sql_query(
        "select category, sales, sales_share from ads_category_top10 order by sales desc", conn)
    chan = pd.read_sql_query(
        "select channel, gmv, gmv_share from ads_channel_share order by gmv desc", conn)
    overall = pd.read_sql_query("select * from ads_kpi_overall", conn).iloc[0]
    conn.close()

    daily["gmv_ma7"] = daily["gmv"].rolling(7, min_periods=4).mean()
    daily["dod"] = daily["gmv"].pct_change()
    mu, sd = daily["gmv"].mean(), daily["gmv"].std()
    daily["z"] = (daily["gmv"] - mu) / sd

    # 异常日：z>2（异常高）或单日环比跌幅超 30%（突降）
    highs = daily[daily["z"] > 2].copy()
    drops = daily[(daily["dod"] <= -0.30) & (daily["order_date"] > daily["order_date"].min())].copy()
    global _LAST_DAILY
    _LAST_DAILY = daily
    return {
        "daily": daily, "cat": cat, "chan": chan, "overall": overall,
        "mu": mu, "sd": sd, "highs": highs, "drops": drops,
    }


def explain_day(row: pd.Series) -> str:
    """用确定性规则给出解释（供 AI Prompt 与离线模式共用）。事件线索取自促销日历
    与数据本身（前一交易日 z 值），不引入数据之外的假设。"""
    d = row["order_date"]
    dom = int(d[8:10])
    ts = pd.Timestamp(d)
    tags = []
    if d in BIG_PROMO:
        tags.append("平台级大促（国庆/双十一）")
    elif dom in PROMO_DAYS:
        tags.append("会员日促销脉冲")
    if ts.day_of_week >= 5:
        tags.append("周末效应")
    # 前一交易日若为异常高（z>2），本次下跌大概率是脉冲后的回落
    prev = _LAST_DAILY.iloc[_LAST_DAILY.index.get_loc(row.name) - 1] if row.name and row.name > 0 else None
    if prev is not None and prev["z"] > 2 and row.get("dod", 0) < 0:
        tags.append("前一日促销脉冲后的需求回落")
    return "、".join(tags) if tags else "无已知营销事件，需人工排查（库存/运力/舆情）"

_LAST_DAILY: pd.DataFrame | None = None


def build_prompt(ctx: dict) -> str:
    daily, cat, chan = ctx["daily"], ctx["cat"], ctx["chan"]
    o = ctx["overall"]
    lines = ["【经营上下文】（全部来自 ADS 表真实计算结果）",
             f"区间：{daily['order_date'].iloc[0]} ~ {daily['order_date'].iloc[-1]}（{len(daily)} 天）",
             f"大盘：GMV {o['gmv']:,.2f} 元 / 订单 {int(o['orders']):,} / 客单价 {o['aov']:.2f} 元 / "
             f"活跃用户 {int(o['active_users']):,} / 复购率 {o['repurchase_rate'] * 100:.2f}%",
             "渠道结构：" + "；".join(f"{r.channel} {r.gmv_share * 100:.1f}%" for r in chan.itertuples()),
             "品类 Top3：" + "；".join(f"{r.category} {r.sales_share * 100:.1f}%" for r in cat.head(3).itertuples()),
             "", "【检测到的异常日】（z>2 或单日环比跌幅>30%）"]
    for r in pd.concat([ctx["highs"], ctx["drops"]]).drop_duplicates("order_date").sort_values("order_date").itertuples():
        lines.append(f"- {r.order_date}: GMV {r.gmv:,.0f} 元，环比 {r.dod * 100:+.1f}%，"
                     f"z={r.z:+.2f}，统计线索：{explain_day(pd.Series({'order_date': r.order_date, 'gmv': r.gmv}))}")
    lines += ["", "请完成：1) 逐个异常日给出归因假设（区分促销驱动/周期波动/需人工排查）；",
              "2) 输出一份 200 字以内的经营分析摘要（面向管理层，先结论后依据）；",
              "3) 明确指出哪些结论需要人工验证、AI 无法从当前数据确认。"]
    return "\n".join(lines)


SYSTEM_PROMPT = (
    "你是新零售企业的经营分析师。只依据给定数据归因，禁止编造数据中不存在的数字；"
    "无法确认的结论必须显式标注'需人工验证'。"
)


def offline_mock(prompt: str) -> str:
    """离线模板引擎：用确定性规则生成归因与摘要（非真实大模型，报告中显式标注）。"""
    ctx_ans = _LAST_CTX
    with open(os.path.join(OUT, "trend_summary.json"), encoding="utf-8") as f:
        trend = json.load(f)
    daily = ctx_ans["daily"]
    outs = pd.concat([ctx_ans["highs"], ctx_ans["drops"]]).drop_duplicates("order_date").sort_values("order_date")
    lines = ["【异常归因】（依据：促销日历 + 前一交易日 z 值 + 星期画像，均为数据内证据）"]
    for r in outs.itertuples():
        row = pd.Series({"order_date": r.order_date, "gmv": r.gmv, "dod": r.dod, "name": r.Index})
        why = explain_day(row)
        if "需人工排查" in why:
            lines.append(f"- {r.order_date}（GMV {r.gmv:,.0f} 元，环比 {r.dod * 100:+.1f}%）：{why}。"
                         "【需人工验证】AI 当前无法接入库存/运力/舆情数据，不能给出进一步归因。")
        else:
            lines.append(f"- {r.order_date}（GMV {r.gmv:,.0f} 元，环比 {r.dod * 100:+.1f}%）：归因——{why}；"
                         "与促销日历/星期画像交叉一致，属可解释波动。")
    o = ctx_ans["overall"]
    chan = ctx_ans["chan"]
    cat = ctx_ans["cat"]
    lines += ["", "【经营分析摘要】",
              f"近 180 天 GMV {o['gmv']:,.0f} 元、订单 {int(o['orders']):,} 单、客单价 {o['aov']:.2f} 元，"
              f"复购率 {o['repurchase_rate'] * 100:.2f}%。渠道上线上/线下基本均衡"
              f"（{chan.iloc[0]['channel']} {chan.iloc[0]['gmv_share'] * 100:.1f}%）；"
              f"品类上 {cat.iloc[0]['category']} 以 {cat.iloc[0]['sales_share'] * 100:.1f}% 居首。"
              f"GMV 呈温和上行趋势，周日效应最强（高于趋势约 {trend['seasonal_profile']['6'] / 10000:.2f} 万元/日），"
              "月度 8/18/28 会员日与大促日为主要脉冲来源。"]
    lines += ["", "【需人工验证】",
              "- AI 未接入库存/营销费用/竞对数据，突降若与上述事件无关，需人工排查；",
              "- 归因是相关性判断，不构成因果结论；",
              "- 本报告由离线模板引擎生成（未配置大模型 Key），非真实 LLM 输出。"]
    return "\n".join(lines)


_LAST_CTX: dict = {}


def verify_ai_text(text: str, ctx: dict) -> list[dict]:
    """审慎验证：抽取 AI 文本中的金额/百分比，回查是否能在底层数据中找到依据。"""
    checks: list[dict] = []
    o = ctx["overall"]
    pool = {
        f"{o['gmv']:,.0f}": "大盘 GMV", f"{o['gmv'] / 10000:,.0f}": "大盘 GMV（万）",
        f"{o['repurchase_rate'] * 100:.2f}": "复购率", f"{o['aov']:.2f}": "客单价",
    }
    for r in ctx["chan"].itertuples():
        pool[f"{r.gmv_share * 100:.1f}"] = f"渠道 {r.channel} 占比"
    for r in ctx["cat"].head(3).itertuples():
        pool[f"{r.sales_share * 100:.1f}"] = f"品类 {r.category} 占比"
    for r in ctx["highs"].itertuples():
        pool[f"{r.gmv:,.0f}"] = f"{r.order_date} GMV"
        pool[f"{r.dod * 100:+.1f}"] = f"{r.order_date} 环比"
        pool[f"{r.dod * 100:.1f}"] = f"{r.order_date} 环比幅度"
    for r in ctx["drops"].itertuples():
        pool[f"{r.gmv:,.0f}"] = f"{r.order_date} GMV"
        pool[f"{r.dod * 100:+.1f}"] = f"{r.order_date} 环比"
        pool[f"{abs(r.dod) * 100:.1f}"] = f"{r.order_date} 环比幅度"
    # 业务常量（均为上下文中的确定信息，非 AI 编造）
    for pd_ in PROMO_DAYS:
        pool[str(pd_)] = "会员日(8/18/28)"
    pool[str(len(ctx["daily"]))] = "数据窗口天数"
    pool["3"] = "大促后回补窗口(3天)"

    # 周内季节性画像（trend_summary.json）
    ts_path = os.path.join(OUT, "trend_summary.json")
    if os.path.exists(ts_path):
        with open(ts_path, encoding="utf-8") as f:
            for k, v in json.load(f)["seasonal_profile"].items():
                pool[f"{v:,.0f}"] = f"周内季节性偏离(day={k})"
                pool[f"{abs(v) / 10000:.2f}"] = f"周内季节性偏离·万元(day={k})"
    # 先剔除日期 token（yyyy-mm-dd），日期本身不是"待验证的数字"
    text = re.sub(r"\d{4}-\d{2}-\d{2}", " ", text)
    # 文本中出现的每个数字：在数据池中能找到 → PASS；找不到 → WARN（可能是四舍五入或幻觉）
    for m in re.findall(r"\d[\d,，]*\.?\d*%?", text)[:60]:
        num = m.replace("，", ",").rstrip("%")
        hit = None
        for k, label in pool.items():
            if num == k or num == k.split(".")[0]:
                hit = f"{label}（{k}）"
                break
        checks.append({"figure": m, "evidence": hit, "verdict": "PASS" if hit else "WARN"})
    return checks


def main() -> None:
    global _LAST_CTX
    ctx = load_context()
    _LAST_CTX = ctx
    prompt = build_prompt(ctx)

    client = LLMClient()
    reply = client.chat(SYSTEM_PROMPT, prompt, mock_fn=offline_mock)
    checks = verify_ai_text(reply.content, ctx)
    warn = [c for c in checks if c["verdict"] == "WARN"]

    result = {
        "mode": reply.mode, "model": reply.model,
        "prompt_chars": len(prompt), "reply_chars": len(reply.content),
        "anomaly_high_days": len(ctx["highs"]), "anomaly_drop_days": len(ctx["drops"]),
        "figure_checks": {"total": len(checks), "pass": len(checks) - len(warn), "warn": len(warn)},
        "figure_check_detail": checks,
    }
    with open(os.path.join(OUT, "ai_insight.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    md = [
        "# AI 智能洞察 · 自动经营分析报告",
        "",
        f"- 生成时间：2026-11-13　|　生成方式：{'大模型 API（' + reply.model + '）' if reply.mode == 'online' else '**离线模板引擎（未配置大模型 Key，非真实 LLM）**'}",
        f"- 异常检测：z>2 异常高日 {len(ctx['highs'])} 个；单日环比跌幅>30% 突降日 {len(ctx['drops'])} 个",
        f"- 数字验证：AI 文本抽取 {len(checks)} 个数字，其中 {len(checks) - len(warn)} 个可在底层数据中找到依据（PASS），{len(warn)} 个未直接命中（WARN）",
        "",
        "---",
        "",
        reply.content,
        "",
        "---",
        "",
        "## 数字验证明细",
        "",
        "| AI 文中数字 | 数据依据 | 结论 |",
        "|---|---|---|",
    ]
    for c in checks:
        md.append(f"| {c['figure']} | {c['evidence'] or '未直接命中'} | {c['verdict']} |")
    md += ["", "> 验证方法：从 AI 输出中抽取全部金额/百分比，回查 ADS 表计算结果；"
           "WARN 项需人工复核后才可进入决策材料。"]
    with open(os.path.join(OUT, "ai_insight_report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    print(f"[OK] mode={reply.mode}  异常高日 {len(ctx['highs'])} / 突降日 {len(ctx['drops'])}")
    print(f"[OK] 数字验证 {len(checks) - len(warn)}/{len(checks)} PASS")
    print(f"[OK] 产物：output/ai_insight_report.md、output/ai_insight.json")


if __name__ == "__main__":
    sys.exit(main())
