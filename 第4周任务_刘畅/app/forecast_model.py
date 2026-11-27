# -*- coding: utf-8 -*-
"""
GMV 预测模型（第3周部署操作手册 · 步骤3 规范实现 · 多年度增强）

流程严格对齐手册步骤3：
  1. 读取每日 GMV：2022-2026 多年度数据（2024 真实，其余模拟扩展）
  2. 特征工程：lag1、ma7、is_weekend、is_promo、is_pre_promo
  3. 训练/测试拆分：末 TEST_DAYS 天作测试集
  4. 多元线性回归（最小二乘，纯 Python，零第三方依赖）
  5. 评估：MAE / RMSE / MAPE + lag1/ma7 基线 + 分段评估
  6. 滚动预测未来 N 天（N 由界面输入）

年份语义：
  - year=None：用全部历史（2022-2026）训练，预测序列末尾之后 N 天；
  - year=2024：仅用该年历史训练，预测该年末之后 N 天（历史截取到该年 12-31）；
  - 数据标注 data_source 显式说明真实/模拟来源。
"""
import json
import math
import os
from datetime import date, timedelta

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "echarts", "data")
TEST_DAYS = 14
FUTURE_DAYS = 7
ALL_YEARS = [2022, 2023, 2024, 2025, 2026]
REAL_YEAR = 2024


def _load_daily(year=None):
    path = os.path.join(DATA, "daily_gmv_multi.json")
    if not os.path.exists(path):
        path = os.path.join(DATA, "daily_gmv.json")
    with open(path, encoding="utf-8") as f:
        rows = json.load(f)
    if year in ALL_YEARS:
        rows = [r for r in rows if int(str(r["date"])[:4]) <= year]
    return rows


def _is_promo(d):
    """会员日模拟：每月 8/18/28 号"""
    return d.day in (8, 18, 28)


def _features(series, i):
    d = date.fromisoformat(series[i]["date"])
    lag1 = series[i - 1]["gmv"] if i >= 1 else series[i]["gmv"]
    win = series[max(0, i - 6):i + 1]
    ma7 = sum(r["gmv"] for r in win) / len(win)
    is_weekend = 1 if d.weekday() >= 5 else 0
    is_promo = 1 if _is_promo(d) else 0
    yesterday = d - timedelta(days=1)
    is_pre_promo = 1 if _is_promo(yesterday) else 0
    return [lag1, ma7, is_weekend, is_promo, is_pre_promo]


def _solve(A, b):
    """高斯-约当消元求解正规方程，带岭正则防奇异"""
    n = len(A)
    lam = 1e-6
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for i in range(n):
        M[i][i] += lam
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(M[r][col]))
        M[col], M[piv] = M[piv], M[col]
        pv = M[col][col]
        if abs(pv) < 1e-12:
            continue
        M[col] = [x / pv for x in M[col]]
        for r in range(n):
            if r == col:
                continue
            f = M[r][col]
            if f:
                M[r] = [a - f * c for a, c in zip(M[r], M[col])]
    return [M[i][n] for i in range(n)]


def _fit(X, y):
    k = len(X[0])
    XtX = [[sum(row[a] * row[b] for row in X) for b in range(k)] for a in range(k)]
    Xty = [sum(row[a] * yy for row, yy in zip(X, y)) for a in range(k)]
    return _solve(XtX, Xty)


def _predict(w, x):
    return sum(wi * xi for wi, xi in zip(w, x))


def _metrics(actual, pred):
    n = len(actual)
    if not n:
        return {"MAE": 0.0, "RMSE": 0.0, "MAPE(%)": 0.0, "样本数": 0}
    errs = [a - p for a, p in zip(actual, pred)]
    mae = sum(abs(e) for e in errs) / n
    rmse = math.sqrt(sum(e * e for e in errs) / n)
    mape = sum(abs(e) / a for e, a in zip(errs, actual) if a) / n * 100
    return {"MAE": round(mae, 2), "RMSE": round(rmse, 2),
            "MAPE(%)": round(mape, 2), "样本数": n}


def build_forecast(future_days=FUTURE_DAYS, year=None):
    """按手册步骤3完整跑一遍，返回结构化结果 dict。

    future_days: 自动输出的未来预测天数（1~365）。
    year: 预测基准年份（None=全部历史）。
    """
    future_days = max(1, min(int(future_days), 365))
    series = _load_daily(year)
    n = len(series)
    split = max(n - TEST_DAYS, 1)

    X_all, y_all = [], []
    for i in range(n):
        f = _features(series, i)
        X_all.append([1.0] + f)
        y_all.append(series[i]["gmv"])

    X_train, y_train = X_all[:split], y_all[:split]
    X_test, y_test = X_all[split:], y_all[split:]
    w = _fit(X_train, y_train)

    pred_test = [_predict(w, x) for x in X_test]
    model_metrics = _metrics(y_test, pred_test)
    baseline_lag1 = _metrics(y_test, [x[1] for x in X_test])
    baseline_ma7 = _metrics(y_test, [x[2] for x in X_test])

    actual_rows = []
    for i, idx in enumerate(range(split, n)):
        actual_rows.append({
            "date": series[idx]["date"],
            "actual": round(y_test[i], 2),
            "pred": round(pred_test[i], 2),
            "is_weekend": X_test[i][3],
            "is_promo": X_test[i][4],
        })

    def seg_metrics(names):
        act, pre = [], []
        for r in actual_rows:
            typ = "大促日" if r["is_promo"] else ("周末" if r["is_weekend"] else "普通日")
            if typ in names:
                act.append(r["actual"]); pre.append(r["pred"])
        return _metrics(act, pre)

    segments = {
        "普通日": seg_metrics({"普通日"}),
        "周末": seg_metrics({"周末"}),
        "会员日/大促": seg_metrics({"大促日"}),
        "剔除大促日": seg_metrics({"普通日", "周末"}),
    }

    # ---- 滚动预测未来 N 天 ----
    work = [dict(r) for r in series]
    future_rows = []
    last_date = date.fromisoformat(series[-1]["date"])
    for step in range(1, future_days + 1):
        idx = len(work)
        f = _features(work, idx - 1)
        pred = _predict(w, [1.0] + f)
        d = last_date + timedelta(days=step)
        pred = max(0.0, pred)
        work.append({"date": d.isoformat(), "gmv": pred, "orders": 0})
        future_rows.append({
            "date": d.isoformat(),
            "year": d.year,
            "pred": round(pred, 2),
            "is_weekend": 1 if d.weekday() >= 5 else 0,
            "is_promo": 1 if _is_promo(d) else 0,
        })

    coef_names = ["截距", "lag1", "ma7", "is_weekend", "is_promo", "is_pre_promo"]
    source_note = (f"{year} 年历史（{'真实' if year == REAL_YEAR else '模拟扩展'}）"
                   if year in ALL_YEARS else "2022-2026 全部历史（2024 真实，其余模拟扩展）")
    return {
        "data_source": f"{source_note} · 每日 GMV 离线快照",
        "year": year,
        "year_label": str(year) if year in ALL_YEARS else "全部年份",
        "train_days": split,
        "test_days": n - split,
        "test_range": [actual_rows[0]["date"], actual_rows[-1]["date"]],
        "future_days": future_days,
        "features": ["lag1", "ma7", "is_weekend", "is_promo", "is_pre_promo"],
        "model": model_metrics,
        "baseline_lag1": baseline_lag1,
        "baseline_ma7": baseline_ma7,
        "segments": segments,
        "coef": {name: round(c, 4) for name, c in zip(coef_names, w)},
        "actual_rows": actual_rows,
        "future_rows": future_rows,
        "future_avg": round(sum(r["pred"] for r in future_rows) / len(future_rows), 2),
        "history": [{"date": r["date"], "gmv": r["gmv"]} for r in series],
    }


if __name__ == "__main__":
    res = build_forecast()
    print("数据源:", res["data_source"])
    print("训练/测试:", res["train_days"], "/", res["test_days"], res["test_range"])
    print("模型指标:", res["model"])
    print("基线lag1:", res["baseline_lag1"])
    print("基线ma7 :", res["baseline_ma7"])
    print(f"未来{res['future_days']}天:")
    for r in res["future_rows"][:10]:
        print("  ", r["date"], r["pred"])
    print("回归系数:", json.dumps(res["coef"], ensure_ascii=False))
