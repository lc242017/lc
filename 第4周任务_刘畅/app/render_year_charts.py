# -*- coding: utf-8 -*-
"""把多年度问答的关键结果渲染为静态 PNG，便于直接查看/答辩。"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

# 中文字体
for fp in ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"]:
    if os.path.exists(fp):
        font_manager.fontManager.addfont(fp)
        plt.rcParams["font.sans-serif"] = [font_manager.FontProperties(fname=fp).get_name()]
        break
plt.rcParams["axes.unicode_minus"] = False

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "echarts", "data")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "..", "..", "..", "..", "第5周任务_刘畅", "0_端到端联调")
os.makedirs(OUT, exist_ok=True)

YEARS = [2022, 2023, 2024, 2025, 2026]
REAL = 2024
m = json.load(open(os.path.join(BASE, "multi_year.json"), encoding="utf-8"))
trends = json.load(open(os.path.join(BASE, "daily_gmv_multi.json"), encoding="utf-8"))

# 图1：各年份 KPI 对比（GMV + 订单）
yk = [m["kpi"][str(y)][0] for y in YEARS]
fig, ax1 = plt.subplots(figsize=(10, 5.5))
colors = ["#ff7a45" if y == REAL else "#4fd1ff" for y in YEARS]
bars = ax1.bar([str(y) for y in YEARS], [k["gmv"] / 10000 for k in yk], color=colors)
ax1.set_ylabel("GMV（万元）", color="#333")
ax1.set_xlabel("年份")
ax1.set_title("各年份 GMV 与订单数对比（橙色=2024真实，蓝色=模拟扩展）")
for b, k in zip(bars, yk):
    ax1.text(b.get_x() + b.get_width() / 2, b.get_height(),
             f"{k['gmv']/10000:.0f}", ha="center", va="bottom", fontsize=9)
ax2 = ax1.twinx()
ax2.plot([str(y) for y in YEARS], [k["orders"] for k in yk],
         color="#ff7a45", marker="o", linewidth=2, label="订单数")
ax2.set_ylabel("订单数", color="#ff7a45")
fig.tight_layout()
p1 = os.path.join(OUT, "问答_各年份KPI对比.png")
fig.savefig(p1, dpi=130)
plt.close(fig)
print("saved", p1)

# 图2：各年份月度 GMV 趋势（按年折线）
fig, ax = plt.subplots(figsize=(11, 5.5))
for y in YEARS:
    months = [r for r in m["trend"][str(y)]]
    xs = [int(r["month"][5:]) for r in months]
    ys = [r["gmv"] / 10000 for r in months]
    ax.plot(xs, ys, marker="o", linewidth=2.2 if y == REAL else 1.4,
            alpha=1 if y == REAL else 0.7,
            label=f"{y}{'（真实）' if y == REAL else '（模拟）'}")
ax.set_xlabel("月份")
ax.set_ylabel("GMV（万元）")
ax.set_title("各年份月度 GMV 趋势")
ax.legend(fontsize=8, ncol=2)
ax.grid(alpha=0.3)
fig.tight_layout()
p2 = os.path.join(OUT, "问答_各年份月度趋势.png")
fig.savefig(p2, dpi=130)
plt.close(fig)
print("saved", p2)

# 图3：预测示例——以全部历史滚动预测未来30天
from forecast_model import build_forecast
res = build_forecast(30, year=None)
fut = res["future_rows"]
fig, ax = plt.subplots(figsize=(11, 5.5))
hist = res["history"][-90:]
ax.plot([h["date"] for h in hist], [h["gmv"] for h in hist],
        color="#4fd1ff", label="历史实际（近90天）")
ax.plot([f["date"] for f in fut], [f["pred"] for f in fut],
        color="#ff7a45", linestyle="--", marker="o", markersize=3, label="未来30天预测")
ax.axvline(x=fut[0]["date"], color="#888", linestyle=":", linewidth=1)
ax.set_title(f"预测示例：输入30天 → 自动输出未来30天预测值（日均 {res['future_avg']:,.0f} 元）")
ax.set_ylabel("GMV（元）")
ax.legend()
ax.grid(alpha=0.3)
# X 轴按每 10 天显示一个刻度，避免标签重叠
all_dates = [h["date"] for h in hist] + [f["date"] for f in fut]
tick_idx = list(range(0, len(all_dates), 10))
ax.set_xticks([all_dates[i] for i in tick_idx if i < len(all_dates)])
plt.setp(ax.get_xticklabels(), rotation=45, ha="right", fontsize=8)
fig.tight_layout()
p3 = os.path.join(OUT, "问答_预测30天示例.png")
fig.savefig(p3, dpi=130)
plt.close(fig)
print("saved", p3)
