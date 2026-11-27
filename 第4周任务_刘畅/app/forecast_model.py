# -*- coding: utf-8 -*-
"""
GMV 预测模型（第3周部署操作手册 · 步骤3 规范实现）

流程严格对齐手册步骤3「Python 读取 Hive 数据并预测建模」：
  1. 读取每日 GMV（数据源：Hive dws.dws_order_day，已导出为 daily_gmv.json 供离线运行）
  2. 特征工程：lag1（前一日 GMV）、ma7（7 日移动平均）、is_weekend、is_promo、is_pre_promo
  3. 训练/测试拆分：最后 TEST_DAYS 天作测试集
  4. 多元线性回归（最小二乘，纯 Python 实现，零第三方依赖）
  5. 评估：MAE / RMSE / MAPE + lag1/ma7 基线对比 + 分段评估
  6. 滚动预测未来 N 天

口径说明：数据源为 DWS「有效订单」口径（GMV 合计约 2642 万 / 9992 单），
与 ADS 全量口径（3970 万 / 15000 单）分开，预测仅用于趋势参考。
"""
import json
import math
import os
from datetime import date, timedelta

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "echarts", "data")
TEST_DAYS = 14          # 测试集天数（手册：留出末段做真实值对比）
FUTURE_DAYS = 7         # 未来预测天数


def _load_daily():
    with open(os.path.join(DATA, "daily_gmv.json"), encoding="utf-8") as f:
        return json.load(f)


def _is_promo(d):
    """会员日模拟：每月 8/18/28 号（与第3周预测口径一致）"""
    return d.day in (8, 18, 28)


def _features(series, i):
    """构造第 i 天的特征向量；series 为 [{date,gmv,orders}, ...]"""
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
    """高斯-约当消元求解正规方程 (X'X)w = X'y，带岭正则防奇异"""
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
    """最小二乘多元线性回归，返回权重 w（含截距项，X 首列已置 1）"""
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


def build_forecast():
    """按手册步骤3完整跑一遍，返回结构化结果 dict"""
    series = _load_daily()
    n = len(series)
    split = n - TEST_DAYS

    # ---- 特征矩阵（首列=1 作为截距）----
    X_all, y_all = [], []
    for i in range(n):
        f = _features(series, i)
        X_all.append([1.0] + f)
        y_all.append(series[i]["gmv"])

    X_train, y_train = X_all[:split], y_all[:split]
    X_test, y_test = X_all[split:], y_all[split:]
    w = _fit(X_train, y_train)

    # ---- 测试集：模型预测 vs 真实 ----
    pred_test = [_predict(w, x) for x in X_test]
    model_metrics = _metrics(y_test, pred_test)

    # ---- 基线对比（lag1 / ma7）----
    lag1_pred = [x[1] for x in X_test]
    ma7_pred = [x[2] for x in X_test]
    baseline_lag1 = _metrics(y_test, lag1_pred)
    baseline_ma7 = _metrics(y_test, ma7_pred)

    # ---- 预测 vs 真实明细 ----
    actual_rows = []
    for i, idx in enumerate(range(split, n)):
        d = series[idx]["date"]
        actual_rows.append({
            "date": d,
            "actual": round(y_test[i], 2),
            "pred": round(pred_test[i], 2),
            "is_weekend": X_test[i][3],
            "is_promo": X_test[i][4],
        })

    # ---- 分段评估：普通日 / 周末 / 会员日 / 剔除大促 ----
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
    # 用最后已知窗口递推：每日预测值回填进序列，再构造次日特征
    work = [dict(r) for r in series]
    future_rows = []
    last_date = date.fromisoformat(series[-1]["date"])
    for step in range(1, FUTURE_DAYS + 1):
        idx = len(work)
        f = _features(work, idx - 1)  # 基于已有序列末位构造特征
        # _features(work, idx-1) 用的是 work[idx-1] 的 lag1/ma7，正是最新可得
        pred = _predict(w, [1.0] + f)
        d = last_date + timedelta(days=step)
        pred = max(0.0, pred)
        work.append({"date": d.isoformat(), "gmv": pred, "orders": 0})
        future_rows.append({
            "date": d.isoformat(),
            "pred": round(pred, 2),
            "is_weekend": 1 if d.weekday() >= 5 else 0,
            "is_promo": 1 if _is_promo(d) else 0,
        })

    coef_names = ["截距", "lag1", "ma7", "is_weekend", "is_promo", "is_pre_promo"]
    return {
        "data_source": "Hive dws.dws_order_day（366天，有效订单口径，离线快照）",
        "train_days": split,
        "test_days": TEST_DAYS,
        "test_range": [actual_rows[0]["date"], actual_rows[-1]["date"]],
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
    print("分段:", json.dumps(res["segments"], ensure_ascii=False))
    print("未来7天:")
    for r in res["future_rows"]:
        print("  ", r["date"], r["pred"])
    print("回归系数:", json.dumps(res["coef"], ensure_ascii=False))
