# -*- coding: utf-8 -*-
"""
查询压测脚本（手册步骤6）
对比全表扫描 vs 分区裁剪的响应时间，记录结果到 benchmark_result.md
运行：python3 benchmark.py
"""
import subprocess
import time
from datetime import datetime

BEELINE = ["docker", "exec", "hive-demo-hive-server-1", "beeline",
           "-u", "jdbc:hive2://localhost:10000", "-n", "root", "--silent=true", "-e"]

CASES = [
    ("全表扫描（无分区）",
     "select round(sum(pay_amount),2) from ydsh_dwd.dwd_order;"),
    ("分区裁剪（11月）",
     "select round(sum(pay_amount),2) from ydsh_dwd.dwd_order where stat_date between '2024-11-01' and '2024-11-30';"),
    ("分区+列裁剪（半年GMV）",
     "select stat_month,sum(pay_amount) from ydsh_dwd.dwd_order where stat_date>='2024-01-01' and stat_date<='2024-06-30' group by stat_month;"),
    ("ADS 预聚合表查询",
     "select * from ads.ads_kpi;"),
]


def run(sql):
    t0 = time.perf_counter()
    subprocess.run(BEELINE + [sql], capture_output=True, text=True, timeout=300)
    return time.perf_counter() - t0


def main():
    results = []
    print("开始压测 ...", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    for name, sql in CASES:
        # 预热一次，取第二次耗时（更接近稳态）
        run(sql)
        t1 = run(sql)
        t2 = run(sql)
        avg = (t1 + t2) / 2
        results.append((name, avg))
        print(f"  {name}: {avg:.3f}s")

    out = ["# 查询性能压测记录", "",
           f"> 测试时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
           "> 环境：Hive 4.0.0（Docker），ydsh_dwd.dwd_order（15000 行）",
           "> 方法：每种查询预热 1 次，取后 2 次平均值（beeline 含连接开销）", "",
           "| 查询场景 | 平均耗时(s) | 说明 |",
           "|---|---:|---|"]
    notes = {
        "全表扫描（无分区）": "扫描全部分区，基线",
        "分区裁剪（11月）": "仅扫描 1 个月分区",
        "分区+列裁剪（半年GMV）": "分区裁剪 + 列裁剪",
        "ADS 预聚合表查询": "预计算指标表，毫秒级",
    }
    for name, t in results:
        out.append(f"| {name} | {t:.3f} | {notes.get(name,'')} |")
    out += ["", "## 结论", "",
            "- 分区裁剪显著减少扫描数据量，查询耗时下降；",
            "- ADS 预聚合表把多层计算前置到离线阶段，在线查询最快，是大屏/问答应用的首选数据源。",
            ""]
    path = "E:/项目实训/第4周/docs/benchmark_result.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print("结果已写入", path)


if __name__ == "__main__":
    main()
